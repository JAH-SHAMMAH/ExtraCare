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


async def test_new_modules_invoices_slots_and_bills(http, db, org):
    u = await _setup(db, org)
    org.settings = {**org.settings, "super": {**org.settings["super"], **{f"module_{m}": True for m in ["suppliers", "serviceinvoices", "offlineinvoices", "spa", "storeappointments"]}}}
    flag_modified(org, "settings")
    await db.commit()
    h = _bearer(u)
    c = (await http.post("/api/v1/office/serviceinvoices/clients", headers=h, json={"name": "Acme"})).json()["id"]
    inv = {"client_id": c, "invoice_date": "2026-10-01", "items": [{"name": "Hall", "qty": 2, "price": 1000}]}
    r = (await http.post("/api/v1/office/serviceinvoices/invoices", headers=h, json=inv)).json()
    assert r["total"] == 2000 and r["status"] == "sent"
    r2 = await http.put(f"/api/v1/office/serviceinvoices/invoices/{r['id']}", headers=h, json={"paid": 2500})
    assert r2.status_code == 422
    r3 = (await http.put(f"/api/v1/office/serviceinvoices/invoices/{r['id']}", headers=h, json={"paid": 2000})).json()
    assert r3["status"] == "paid"
    off = (await http.post("/api/v1/office/offlineinvoices/invoices", headers=h, json={"payer": "Mr X", "invoice_date": "2026-10-01", "items": [{"name": "Uniform", "qty": 1, "price": 5000}], "paid": 1000})).json()
    assert off["status"] == "part_paid"
    s = (await http.post("/api/v1/office/spa/services", headers=h, json={"name": "Massage", "price": 3000})).json()["id"]
    a = {"service_id": s, "client": "A", "appt_date": "2026-10-20", "appt_time": "10:00"}
    assert (await http.post("/api/v1/office/spa/appointments", headers=h, json=a)).status_code == 201
    assert (await http.post("/api/v1/office/spa/appointments", headers=h, json={**a, "client": "B"})).status_code == 422
    sup = (await http.post("/api/v1/office/suppliers/directory", headers=h, json={"name": "Bakery"})).json()["id"]
    assert (await http.post("/api/v1/office/suppliers/bills", headers=h, json={"supplier_id": sup, "bill_date": "2026-10-01", "amount": 100, "paid": 500})).status_code == 422
    assert (await http.get("/api/v1/office/suppliers/summary", headers=h)).status_code == 200


async def test_procurement_limits_and_self_approval(http, db, org):
    from app.models.role import SCHOOL_PERMISSION_PRESETS  # noqa: F401
    boss = await _setup(db, org)
    acct = await _preset_user(db, org, "accountant")
    hb, ha = _bearer(boss), _bearer(acct)
    req = (await http.post("/api/v1/office/procurement/requests", headers=ha, json={"title": "Laptops", "items": [{"name": "L", "qty": 2, "price": 500}], "status": "approved"})).json()
    assert req["status"] == "submitted" and req["requested_by"] == acct.email
    # a non-super user may not set limits
    assert (await http.post("/api/v1/office/procurement/limits", headers=ha, json={"role": "accountant", "max_amount": 100})).status_code == 422
    await http.post("/api/v1/office/procurement/limits", headers=hb, json={"role": "accountant", "max_amount": 500})
    other = await _preset_user(db, org, "accountant")
    r = await http.put(f"/api/v1/office/procurement/requests/{req['id']}", headers=_bearer(other), json={"status": "approved"})
    assert r.status_code == 422 and "limit" in r.json()["detail"]
    own = await http.put(f"/api/v1/office/procurement/requests/{req['id']}", headers=ha, json={"status": "approved"})
    assert own.status_code == 422
    ok = await http.put(f"/api/v1/office/procurement/requests/{req['id']}", headers=hb, json={"status": "approved"})
    assert ok.status_code == 200 and ok.json()["approved_by"] == boss.email


async def test_ledger_sync_is_idempotent_and_export_works(http, db, org):
    from datetime import date
    from app.models.modules.finance import Invoice
    u = await _setup(db, org)
    h = _bearer(u)
    db.add(Invoice(org_id=org.id, number="INV-1", customer_name="Mr A", invoice_date=date(2026, 10, 1), status="paid", total=1000))
    await db.commit()
    first = (await http.post("/api/v1/office/ledger/sync", headers=h)).json()
    again = (await http.post("/api/v1/office/ledger/sync", headers=h)).json()
    assert first["journals_added"] == 2 and again["journals_added"] == 0
    tb = (await http.get("/api/v1/office/ledger/summary", headers=h)).json()
    assert tb["total_debit"] == tb["total_credit"] == 2000
    csv_ = await http.get("/api/v1/office/ledger/accounts/export", headers=h)
    assert csv_.status_code == 200 and "Fee Income" in csv_.text and csv_.headers["content-type"].startswith("text/csv")


async def test_report_extras_smoke(http, db, org, school_class, student):
    u = await _setup(db, org)
    h = _bearer(u)
    r = await http.get(f"/api/v1/report-extras/student-history/{student.id}", headers=h)
    assert r.status_code == 200 and r.json()["items"] == [] and r.json()["student"]["id"] == student.id
    b = await http.get("/api/v1/report-extras/backup", headers=h, params={"class_id": school_class.id, "term_id": "x", "sub_term_id": "y"})
    assert b.status_code in (200, 404, 422)
    assert (await http.get("/api/v1/report-extras/backup", headers=_bearer(await _preset_user(db, org, "parent")), params={"class_id": "a", "term_id": "b", "sub_term_id": "c"})).status_code == 403


async def test_multi_level_approval_and_wallet_sync(http, db, org):
    boss = await _setup(db, org)
    hb = _bearer(boss)
    a1 = await _preset_user(db, org, "accountant")
    a2 = await _preset_user(db, org, "accountant")
    maker = await _preset_user(db, org, "accountant")
    admin = await _preset_user(db, org, "head_of_administration")
    a2.roles, maker.roles = [a1.roles[0]], [a1.roles[0]]
    await db.commit()
    # two tiers on the same role is not possible, so use two roles: accountant=500, org_admin=5000
    await http.post("/api/v1/office/procurement/limits", headers=hb, json={"role": a1.roles[0].slug, "max_amount": 500})
    await http.post("/api/v1/office/procurement/limits", headers=hb, json={"role": admin.roles[0].slug, "max_amount": 5000})
    r = (await http.post("/api/v1/office/procurement/requests", headers=_bearer(maker), json={"title": "Bus", "items": [{"name": "Bus", "qty": 1, "price": 3000}], "status": "submitted"})).json()
    rid = r["id"]
    # level 1: an accountant signs, the request stays open
    s1 = (await http.put(f"/api/v1/office/procurement/requests/{rid}", headers=_bearer(a1), json={"status": "approved"})).json()
    assert "status" in s1, s1
    assert s1["status"] == "submitted" and s1["awaiting"] == "Level 2 of 2" and len(s1["approvals"]) == 1
    # an accountant cannot give level 2
    assert (await http.put(f"/api/v1/office/procurement/requests/{rid}", headers=_bearer(a2), json={"status": "approved"})).status_code == 422
    # the same person cannot sign twice
    assert (await http.put(f"/api/v1/office/procurement/requests/{rid}", headers=_bearer(a1), json={"status": "approved"})).status_code == 422
    done = (await http.put(f"/api/v1/office/procurement/requests/{rid}", headers=_bearer(admin), json={"status": "approved"})).json()
    assert done["status"] == "approved" and len(done["approvals"]) == 2 and done["awaiting"] is None


async def _enable(db, org, *mods):
    org.settings = {**(org.settings or {}), "super": {**(org.settings or {}).get("super", {}), **{f"module_{m}": True for m in mods}}}
    flag_modified(org, "settings")
    await db.commit()


async def test_procurement_rfq_po_grn_flow(http, db, org):
    boss = await _setup(db, org)
    h = _bearer(boss)
    clerk = await _preset_user(db, org, "accountant")
    hc = _bearer(clerk)
    P = "/api/v1/office/procurement"
    assert (await http.post(f"{P}/settings", headers=hc, json={"rfq_threshold": 1000})).status_code == 422  # super user only
    await http.post(f"{P}/settings", headers=h, json={"rfq_threshold": 1000, "min_quotes": 2, "po_prefix": "FV-"})
    s1 = (await http.post(f"{P}/suppliers", headers=h, json={"name": "A Ltd"})).json()["id"]
    s2 = (await http.post(f"{P}/suppliers", headers=h, json={"name": "B Ltd"})).json()["id"]
    po = (await http.post(f"{P}/orders", headers=hc, json={"supplier_id": s1, "order_date": "2026-10-01", "items": [{"name": "Desk", "qty": 10, "price": 200}], "status": "approved"})).json()
    assert po["status"] == "draft" and po["po_number"] == "FV-0001" and po["total"] == 2000
    # over the threshold, so it needs a selected quote with at least 2 quotes on the RFQ
    r = await http.put(f"{P}/orders/{po['id']}", headers=hc, json={"status": "pending_approval"})
    assert r.status_code == 422 and "quote" in r.json()["detail"]
    rfq = (await http.post(f"{P}/rfqs", headers=h, json={"title": "Desks", "issued_date": "2026-10-01"})).json()["id"]
    q1 = (await http.post(f"{P}/quotes", headers=h, json={"rfq_id": rfq, "supplier_id": s1, "amount": 1900})).json()["id"]
    q2 = (await http.post(f"{P}/quotes", headers=h, json={"rfq_id": rfq, "supplier_id": s2, "amount": 2100})).json()["id"]
    await http.put(f"{P}/quotes/{q1}", headers=h, json={"status": "selected"})
    assert (await http.put(f"{P}/quotes/{q2}", headers=h, json={"status": "selected"})).status_code == 422
    quotes = {q["id"]: q["status"] for q in (await http.get(f"{P}/quotes", headers=h)).json()["items"]}
    assert quotes[q1] == "selected" and quotes[q2] == "rejected"
    assert (await http.put(f"{P}/orders/{po['id']}", headers=hc, json={"quote_id": q1, "status": "pending_approval"})).status_code == 200
    assert (await http.put(f"{P}/orders/{po['id']}", headers=hc, json={"status": "approved"})).status_code == 422  # own order
    ok = (await http.put(f"{P}/orders/{po['id']}", headers=h, json={"status": "approved"})).json()
    assert ok["status"] == "approved"
    assert (await http.put(f"{P}/orders/{po['id']}", headers=h, json={"status": "received"})).status_code == 422
    g = (await http.post(f"{P}/grns", headers=hc, json={"order_id": po["id"], "received_date": "2026-10-05", "items": [{"name": "Desk", "qty_received": 6}], "status": "pending_approval"})).json()
    assert (await http.put(f"{P}/grns/{g['id']}", headers=hc, json={"status": "approved"})).status_code == 422  # receiver can't approve
    assert (await http.put(f"{P}/grns/{g['id']}", headers=h, json={"status": "approved"})).status_code == 200
    assert (await http.get(f"{P}/orders", headers=h)).json()["items"][0]["status"] == "part_received"
    g2 = (await http.post(f"{P}/grns", headers=hc, json={"order_id": po["id"], "received_date": "2026-10-06", "items": [{"name": "Desk", "qty_received": 6}], "status": "pending_approval"})).json()
    assert (await http.put(f"{P}/grns/{g2['id']}", headers=h, json={"status": "approved"})).status_code == 422  # over-receipt
    g3 = (await http.post(f"{P}/grns", headers=hc, json={"order_id": po["id"], "received_date": "2026-10-06", "items": [{"name": "Desk", "qty_received": 4}], "status": "pending_approval"})).json()
    await http.put(f"{P}/grns/{g3['id']}", headers=h, json={"status": "approved"})
    assert (await http.get(f"{P}/orders", headers=h)).json()["items"][0]["status"] == "received"
    assert (await http.get(f"{P}/summary", headers=h)).json()["spend_by_supplier"][0]["supplier"] == "A Ltd"


async def test_empowerment_budget_and_imprest_topup_cap(http, db, org):
    u = await _setup(db, org)
    await _enable(db, org, "empowerment")
    h = _bearer(u)
    E_ = "/api/v1/office/empowerment"
    prog = (await http.post(f"{E_}/programmes", headers=h, json={"name": "Tailoring", "budget": 1000, "status": "active"})).json()["id"]
    ben = (await http.post(f"{E_}/beneficiaries", headers=h, json={"name": "Ada", "programme_id": prog})).json()["id"]
    assert (await http.post(f"{E_}/support", headers=h, json={"beneficiary_id": ben, "kind": "grant", "support_date": "2026-10-02", "amount": 800})).status_code == 201
    assert (await http.post(f"{E_}/support", headers=h, json={"beneficiary_id": ben, "kind": "grant", "support_date": "2026-10-03", "amount": 300})).status_code == 422
    assert (await http.get(f"{E_}/summary", headers=h)).json()["support_given"] == 800
    f = (await http.post("/api/v1/office/imprest/funds", headers=h, json={"holder": "Bursar", "float_amount": 100})).json()["id"]
    big = {"fund_id": f, "kind": "replenish", "entry_date": "2026-10-02", "description": "Top up", "amount": 50000}
    assert (await http.post("/api/v1/office/imprest/entries", headers=h, json=big)).status_code == 422
    assert (await http.post("/api/v1/office/imprest/entries", headers=h, json={**big, "amount": 20000})).status_code == 201


# ── Customers, WhatsApp, club attendance, communication book, parent side, users ──
from tests.test_parent_report_access import family  # noqa: E402,F401


async def _flags(db, org, *names):
    org.settings = {**(org.settings or {}), "super": {f"module_{m}": True for m in names}}
    flag_modified(org, "settings")
    await db.commit()


async def test_commbook_parent_side_is_scoped_to_own_child(http, db, org, family):
    f = family
    await _flags(db, org, "commbook")
    staff = await _preset_user(db, org, "teacher")
    r = await http.post("/api/v1/office/commbook/entries", headers=_bearer(staff),
                        json={"student_id": f["mine"].id, "entry_date": "2026-10-01", "message": "Homework done", "direction": "home_to_school"})
    assert r.status_code == 201 and r.json()["direction"] == "school_to_home"
    p = _bearer(f["parent"])
    mine = (await http.get("/api/v1/office/commbook/mine", headers=p)).json()
    assert mine["total"] == 1 and mine["items"][0]["student_id_name"] == "Mine Child"
    a = await http.put(f"/api/v1/office/commbook/mine/{mine['items'][0]['id']}/ack", headers=p, json={"reply": "Thanks"})
    assert a.json()["acknowledged"] is True and a.json()["reply"] == "Thanks"
    assert (await http.post("/api/v1/office/commbook/mine", headers=p, json={"student_id": f["theirs"].id, "message": "hi"})).status_code == 403
    assert (await http.post("/api/v1/office/commbook/mine", headers=p, json={"student_id": f["mine"].id, "message": "hi"})).status_code == 201
    assert (await http.get("/api/v1/office/commbook/mine", headers=_bearer(staff))).status_code == 403


async def test_parent_bills_and_store_appointment_booking(http, db, org, family):
    f = family
    p = _bearer(f["parent"])
    bills = await http.get("/api/v1/office/parent/bills", headers=p)
    assert bills.status_code == 200 and [c["name"] for c in bills.json()["children"]] == ["Mine Child"]
    assert (await http.get("/api/v1/office/parent/store-appointments", headers=p)).status_code == 403  # switched off
    await _flags(db, org, "storeappointments")
    body = {"purpose": "Uniform", "appt_date": "2099-01-05", "appt_time": "10:00", "phone": "0801"}
    ok = await http.post("/api/v1/office/parent/store-appointments", headers=p, json=body)
    assert ok.status_code == 201 and ok.json()["status"] == "booked"
    assert (await http.get("/api/v1/office/parent/store-appointments", headers=p)).json()["items"][0]["purpose"] == "Uniform"
    assert (await http.get("/api/v1/office/parent/bills", headers=_bearer(await _preset_user(db, org, "super_user")))).status_code == 403


async def test_whatsapp_customers_and_club_attendance(http, db, org, family):
    f = family
    u = await _preset_user(db, org, "super_user")
    await _flags(db, org, "whatsapp", "customers", "clubattendance")
    h = _bearer(u)
    bad = await http.post("/api/v1/office/whatsapp/messages", headers=h, json={"recipient": "A", "phone": "12", "message": "hi"})
    assert bad.status_code == 422
    ok = await http.post("/api/v1/office/whatsapp/messages", headers=h, json={"recipient": "A", "phone": "+234 801 234 5678", "message": "hi"})
    assert ok.status_code == 201 and ok.json()["phone"] == "2348012345678" and ok.json()["status"] == "queued"
    assert (await http.post("/api/v1/office/customers/directory", headers=h, json={"name": "Mr Bello"})).status_code == 201
    from app.models.modules.school import Club
    import uuid
    club = Club(id=str(uuid.uuid4()), name="Chess", org_id=org.id)
    db.add(club); await db.commit()
    s = await http.post("/api/v1/office/clubattendance/sessions", headers=h, json={"club_id": club.id, "session_date": "2026-10-02"})
    assert s.status_code == 201
    m = {"session_id": s.json()["id"], "student_id": f["mine"].id, "present": True}
    assert (await http.post("/api/v1/office/clubattendance/marks", headers=h, json=m)).status_code == 201
    assert (await http.post("/api/v1/office/clubattendance/marks", headers=h, json=m)).status_code == 422  # no duplicate


async def test_unassigned_students_and_deleted_users_restore(http, db, org, family):
    f = family
    u = await _preset_user(db, org, "super_user")
    h = _bearer(u)
    f["mine"].class_id = None
    await db.commit()
    r = await http.get("/api/v1/school/students", headers=h, params={"unassigned": True})
    assert [s["first_name"] for s in r.json()["items"]] == ["Mine"]
    victim = await _preset_user(db, org, "teacher")
    assert (await http.delete(f"/api/v1/users/{victim.id}", headers=h)).status_code in (200, 204)
    assert victim.id in [x["id"] for x in (await http.get("/api/v1/users/deleted", headers=h)).json()["items"]]
    assert (await http.post(f"/api/v1/users/{victim.id}/restore", headers=h)).status_code == 200
    assert (await http.get("/api/v1/users/deleted", headers=h)).json()["total"] == 0
    assert (await http.get("/api/v1/users/deleted", headers=_bearer(f["parent"]))).status_code == 403
