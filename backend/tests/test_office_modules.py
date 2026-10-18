"""Back-office modules: closed until switched on, permission-gated, and each enforces its own rules."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm.attributes import flag_modified

from app.main import app
from app.database import get_db
from app.models.organization import SubscriptionTier
from tests.test_parent_report_access import _bearer, _preset_user

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def http(db):
    async def _get_db():
        yield db
    app.dependency_overrides[get_db] = _get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


async def _setup(db, org, on=True):
    org.subscription_tier = SubscriptionTier.ENTERPRISE
    admin = await _preset_user(db, org, "super_user")
    if on:
        org.settings = {**(org.settings or {}), "super": {f"module_{m}": True for m in
            ["restaurant", "procurement", "livestock", "rentals", "funfair", "ledger", "imprest", "debtmemo"]}}
        flag_modified(org, "settings")
    await db.commit()
    return admin


async def test_closed_until_super_user_enables(http, db, org):
    u = await _setup(db, org, on=False)
    r = await http.get("/api/v1/office/restaurant/menu", headers=_bearer(u))
    assert r.status_code == 403 and "switched on" in r.json()["detail"]


async def test_restaurant_total_is_computed_and_staff_without_permission_refused(http, db, org):
    u = await _setup(db, org)
    h = _bearer(u)
    r = await http.post("/api/v1/office/restaurant/orders", headers=h, json={"customer": "Staff", "items": [{"name": "Rice", "qty": 2, "price": 500}, {"name": "Water", "qty": 1, "price": 100}]})
    assert r.status_code == 201 and r.json()["total"] == 1100
    t = await _preset_user(db, org, "teacher")
    assert (await http.get("/api/v1/office/restaurant/orders", headers=_bearer(t))).status_code == 403


async def test_ledger_must_balance_and_is_immutable(http, db, org):
    u = await _setup(db, org)
    h = _bearer(u)
    a = (await http.post("/api/v1/office/ledger/accounts", headers=h, json={"code": "1000", "name": "Cash", "type": "asset"})).json()["id"]
    b = (await http.post("/api/v1/office/ledger/accounts", headers=h, json={"code": "4000", "name": "Fees", "type": "income"})).json()["id"]
    bad = await http.post("/api/v1/office/ledger/journals", headers=h, json={"entry_date": "2026-10-01", "memo": "x", "lines": [{"account_id": a, "debit": 100}, {"account_id": b, "credit": 90}]})
    assert bad.status_code == 422
    ok = await http.post("/api/v1/office/ledger/journals", headers=h, json={"entry_date": "2026-10-01", "memo": "Fees", "lines": [{"account_id": a, "debit": 100}, {"account_id": b, "credit": 100}]})
    assert ok.status_code == 201
    tb = (await http.get("/api/v1/office/ledger/summary", headers=h)).json()
    assert tb["total_debit"] == tb["total_credit"] == 100
    assert (await http.delete(f"/api/v1/office/ledger/journals/{ok.json()['id']}", headers=h)).status_code == 405
    assert (await http.delete(f"/api/v1/office/ledger/accounts/{a}", headers=h)).status_code == 409


async def test_imprest_cannot_overspend_and_debt_memo_settles(http, db, org):
    u = await _setup(db, org)
    h = _bearer(u)
    f = (await http.post("/api/v1/office/imprest/funds", headers=h, json={"holder": "Bursar", "float_amount": 1000})).json()["id"]
    assert (await http.post("/api/v1/office/imprest/entries", headers=h, json={"fund_id": f, "kind": "expense", "entry_date": "2026-10-02", "description": "Chalk", "amount": 1500})).status_code == 422
    assert (await http.post("/api/v1/office/imprest/entries", headers=h, json={"fund_id": f, "kind": "expense", "entry_date": "2026-10-02", "description": "Chalk", "amount": 400})).status_code == 201
    assert (await http.get("/api/v1/office/imprest/summary", headers=h)).json()["funds"][0]["balance"] == 600
    m = (await http.post("/api/v1/office/debtmemo/memos", headers=h, json={"debtor": "Mr A", "amount": 500, "reason": "Fees", "memo_date": "2026-10-01"})).json()["id"]
    assert (await http.post("/api/v1/office/debtmemo/payments", headers=h, json={"memo_id": m, "amount": 600, "paid_on": "2026-10-03"})).status_code == 422
    await http.post("/api/v1/office/debtmemo/payments", headers=h, json={"memo_id": m, "amount": 200, "paid_on": "2026-10-03"})
    assert (await http.get("/api/v1/office/debtmemo/summary", headers=h)).json()["memos"][0]["status"] == "partly_paid"
    await http.post("/api/v1/office/debtmemo/payments", headers=h, json={"memo_id": m, "amount": 300, "paid_on": "2026-10-04"})
    s = (await http.get("/api/v1/office/debtmemo/summary", headers=h)).json()
    assert s["memos"][0]["status"] == "settled" and s["outstanding"] == 0


async def test_rentals_clash_and_livestock_sale(http, db, org):
    u = await _setup(db, org)
    h = _bearer(u)
    hall = (await http.post("/api/v1/office/rentals/assets", headers=h, json={"name": "Hall", "rate": 5000})).json()["id"]
    body = {"asset_id": hall, "renter": "X", "start_date": "2026-11-01", "end_date": "2026-11-03", "amount": 15000}
    assert (await http.post("/api/v1/office/rentals/bookings", headers=h, json=body)).status_code == 201
    assert (await http.post("/api/v1/office/rentals/bookings", headers=h, json={**body, "start_date": "2026-11-03", "end_date": "2026-11-04"})).status_code == 422
    cow = (await http.post("/api/v1/office/livestock/animals", headers=h, json={"tag": "C1", "species": "Cow"})).json()["id"]
    await http.post("/api/v1/office/livestock/events", headers=h, json={"animal_id": cow, "kind": "sale", "event_date": "2026-10-05"})
    items = (await http.get("/api/v1/office/livestock/animals", headers=h)).json()["items"]
    assert items[0]["status"] == "sold"
