"""End-to-end: a parent pays their child's Summer-term fee; Finance Broad View catches it.

Real HTTP + real permission checks. Only the payment GATEWAY is stubbed (no network
in tests): it returns a checkout reference, then reports "success" on verify.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.models.modules.finance import LedgerAccount
from app.models.modules.school import ParentGuardian
from tests.test_result_flow_e2e import API, _h, _user, http, world  # noqa: F401  (fixtures)

pytestmark = pytest.mark.asyncio


class _Gateway:
    def __init__(self):
        self.paid = set()

    async def initialize_payment(self, **kw):
        self.last_kw = kw
        ref = f"REF-{uuid.uuid4().hex[:10]}"
        return {"reference": ref, "authorization_url": f"https://pay.test/{ref}", "_raw": {}}

    async def verify_transaction(self, ref):
        return {"status": "success" if ref in self.paid else "pending", "id": "gw-1", "_raw": {}}

    def webhook_signature_valid(self, raw, sig):
        return True


class _Resolver:
    def __init__(self, gw): self.gw = gw
    async def resolve_for_org(self, org_id, db, provider_type=None): return self.gw


async def _acct(db, org, code, name, type_):
    a = LedgerAccount(id=str(uuid.uuid4()), code=code, name=name, type=type_, org_id=org.id)
    db.add(a); await db.commit()
    return a


async def test_parent_pays_summer_fee_and_broad_view_catches_it(http, db, org, world, monkeypatch):
    w = world
    acc = await _user(db, org, "accountant", "Accountant")
    A, P = _h(acc), _h(w["parent"])
    child, sibling = w["studs"][0], w["studs"][1]
    gw = _Gateway()
    import app.routers.fee_payments as fp
    monkeypatch.setattr(fp, "get_payment_resolver", lambda: _Resolver(gw))

    recv = await _acct(db, org, "1100", "Accounts Receivable", "asset")
    inc = await _acct(db, org, "4000", "School Fees", "income")

    # 1. Admin assigns Summer fees (Fee Assignment) to the child and a non-linked pupil.
    fee = dict(term="Summer", session_year="2026/2027", tuition_fee=150000, exam_fee=20000, create_invoices=False)
    for s in (child, sibling):
        r = await http.post(f"{API}/finance/fee-records", headers=A, json=dict(student_id=s.id, **fee))
        assert r.status_code == 201, r.text

    # 2. Admin raises + posts the invoice for each (170,000).
    inv_ids = {}
    for s in (child, sibling):
        r = await http.post(f"{API}/finance/invoices", headers=A, json=dict(
            customer_name=f"{s.first_name} Test", student_id=s.id, receivable_account_id=recv.id,
            invoice_date=str(date.today()),
            lines=[dict(description="Summer tuition + exam", quantity=1, unit_price=170000, income_account_id=inc.id)]))
        assert r.status_code == 201, r.text
        inv_ids[s.id] = r.json()["id"]
        r = await http.post(f"{API}/finance/invoices/{inv_ids[s.id]}/post", headers=A)
        assert r.status_code == 200, r.text

    # 3. Broad View BEFORE payment: 340,000 billed, all owed, nobody paid.
    d0 = (await http.get(f"{API}/finance/broad-view/dashboard", headers=A, params=dict(term="Summer"))).json()
    assert d0["total_revenue"] == 340000 and d0["total_debt"] == 340000 and d0["full_payments"] == 0

    # 4. Parent sees ONLY their own child's invoice.
    r = await http.get(f"{API}/payments/remita/invoices", headers=P)
    assert r.status_code == 200, r.text
    assert [i["id"] for i in r.json()] == [inv_ids[child.id]]

    # 5. Parent cannot pay a sibling's invoice, and cannot read the school's books.
    r = await http.post(f"{API}/payments/fees/initiate", headers=P,
                        json=dict(invoice_id=inv_ids[sibling.id], provider="paystack"))
    assert r.status_code == 404
    assert (await http.get(f"{API}/finance/broad-view/dashboard", headers=P)).status_code == 403
    assert (await http.get(f"{API}/finance/invoices", headers=P)).status_code == 403

    # 6. Parent starts the payment -> hosted checkout link; invoice not yet paid.
    r = await http.post(f"{API}/payments/fees/initiate", headers=P,
                        json=dict(invoice_id=inv_ids[child.id], provider="paystack"))
    assert r.status_code == 200, r.text
    ref = r.json()["reference"]
    assert r.json()["amount_ngn"] == 170000 and r.json()["authorization_url"]
    r = await http.get(f"{API}/payments/fees/verify/{ref}", headers=P)   # gateway says pending
    assert r.json()["status"] == "pending"
    d = (await http.get(f"{API}/finance/broad-view/dashboard", headers=A, params=dict(term="Summer"))).json()
    assert d["total_debt"] == 340000

    # 7. Gateway confirms; parent returns to the callback page -> verify settles it.
    gw.paid.add(ref)
    r = await http.get(f"{API}/payments/fees/verify/{ref}", headers=P)
    assert r.status_code == 200 and r.json()["status"] == "successful", r.text
    # repeated verify / duplicate callback must not double-post
    r = await http.get(f"{API}/payments/fees/verify/{ref}", headers=P)
    assert r.json()["status"] == "successful"

    # 8. Broad View now shows it: one full payment, debt halved, ledger + online log agree.
    d = (await http.get(f"{API}/finance/broad-view/dashboard", headers=A, params=dict(term="Summer"))).json()
    assert d["full_payments"] == 1 and d["total_full_payment"] == 170000
    assert d["total_debt"] == 170000 and d["total_revenue"] == 340000
    led = (await http.get(f"{API}/finance/broad-view/students-ledger", headers=A, params=dict(term="Summer"))).json()
    row = next(x for x in led["items"] if x["student_id"] == child.id)
    assert (row["total_invoiced"], row["total_paid"], row["balance"]) == (170000, 170000, 0)
    tx = (await http.get(f"{API}/finance/broad-view/payment-transactions", headers=A)).json()
    assert tx["successful_amount"] == 170000 and tx["count"] == 1
    inv = (await http.get(f"{API}/finance/invoices/{inv_ids[child.id]}", headers=A)).json()
    assert inv["status"] == "paid"
    # the parent's list is now empty (nothing left to pay)
    assert (await http.get(f"{API}/payments/remita/invoices", headers=P)).json() == []
    # a second initiate on the paid invoice is refused
    r = await http.post(f"{API}/payments/fees/initiate", headers=P,
                        json=dict(invoice_id=inv_ids[child.id], provider="paystack"))
    assert r.status_code == 409


async def test_broad_view_counts_invoice_only_pupils(http, db, org, world):
    """A school that bills by invoice (no Fee Assignment records) must not see zeros."""
    w = world
    acc = await _user(db, org, "accountant", "Acc2")
    A = _h(acc)
    recv = await _acct(db, org, "1100", "Accounts Receivable", "asset")
    inc = await _acct(db, org, "4000", "School Fees", "income")
    for s, pay in ((w["studs"][0], True), (w["studs"][1], False)):
        r = await http.post(f"{API}/finance/invoices", headers=A, json=dict(
            customer_name="x", student_id=s.id, receivable_account_id=recv.id, invoice_date=str(date.today()),
            lines=[dict(description="Fees", quantity=1, unit_price=100000, income_account_id=inc.id)]))
        iid = r.json()["id"]
        await http.post(f"{API}/finance/invoices/{iid}/post", headers=A)
        if pay:
            cash = await _acct(db, org, "1000", "Cash", "asset")
            await http.post(f"{API}/finance/invoices/{iid}/pay", headers=A, json=dict(cash_account_id=cash.id))
    d = (await http.get(f"{API}/finance/broad-view/dashboard", headers=A)).json()
    assert (d["total_revenue"], d["total_debt"], d["full_payments"]) == (200000, 100000, 1)
    led = (await http.get(f"{API}/finance/broad-view/students-ledger", headers=A)).json()
    assert led["total_paid"] == 100000 and led["total_balance"] == 100000


async def test_assign_class_makes_fees_payable_and_parent_pays(http, db, org, world, monkeypatch):
    """Assign Year 10 Amethyst ₦5,000,000 -> each pupil gets a posted invoice -> the linked
    parent can pay it -> Broad View shows it. No manual invoice step."""
    w = world
    acc = await _user(db, org, "accountant", "Acc3")
    A, P = _h(acc), _h(w["parent"])
    gw = _Gateway()
    import app.routers.fee_payments as fp
    monkeypatch.setattr(fp, "get_payment_resolver", lambda: _Resolver(gw))

    body = dict(class_id=w["cls"].id, term="Summer", session_year="2026/2027", tuition_fee=4500000, exam_fee=500000)
    r = await http.post(f"{API}/finance/fee-records/assign-class", headers=A, json=body)
    assert r.status_code == 200 or r.status_code == 201, r.text
    assert r.json()["created"] == 3 and r.json()["invoiced"] == 3
    # repeating is harmless
    r2 = await http.post(f"{API}/finance/fee-records/assign-class", headers=A, json=body)
    assert r2.json()["created"] == 0 and r2.json()["invoiced"] == 0
    g = await http.post(f"{API}/finance/fee-records/generate-invoices", headers=A,
                        json=dict(class_id=w["cls"].id, term="Summer", session_year="2026/2027"))
    assert g.json()["invoiced"] == 0 and g.json()["already_invoiced"] == 3

    inv = (await http.get(f"{API}/payments/remita/invoices", headers=P)).json()
    assert len(inv) == 1 and inv[0]["total"] == 5000000 and inv[0]["student_id"] == w["studs"][0].id

    ref = (await http.post(f"{API}/payments/fees/initiate", headers=P,
                           json=dict(invoice_id=inv[0]["id"], provider="paystack"))).json()["reference"]
    gw.paid.add(ref)
    assert (await http.get(f"{API}/payments/fees/verify/{ref}", headers=P)).json()["status"] == "successful"

    d = (await http.get(f"{API}/finance/broad-view/dashboard", headers=A, params=dict(term="Summer"))).json()
    assert (d["total_revenue"], d["total_debt"], d["full_payments"], d["total_full_payment"]) == (15000000, 10000000, 1, 5000000)


async def test_callback_url_and_unconfigured_message(http, db, org, world, monkeypatch):
    w = world
    acc = await _user(db, org, "accountant", "Acc4")
    A, P = _h(acc), _h(w["parent"])
    recv = await _acct(db, org, "1100", "Accounts Receivable", "asset")
    inc = await _acct(db, org, "4000", "School Fees", "income")
    r = await http.post(f"{API}/finance/invoices", headers=A, json=dict(
        customer_name="x", student_id=w["studs"][0].id, receivable_account_id=recv.id, invoice_date=str(date.today()),
        lines=[dict(description="Fees", quantity=1, unit_price=1000, income_account_id=inc.id)]))
    iid = r.json()["id"]
    await http.post(f"{API}/finance/invoices/{iid}/post", headers=A)
    import app.routers.fee_payments as fp
    from app.config import get_settings
    import app.services.payment_resolver as pr
    # no gateway saved + no platform key -> a clear, actionable message (not "unavailable")
    monkeypatch.setattr(get_settings(), "PAYSTACK_SECRET_KEY", "", raising=False)
    pr.initialize_payment_resolver(get_settings())
    r = await http.post(f"{API}/payments/fees/initiate", headers=P, json=dict(invoice_id=iid, provider="paystack"))
    assert r.status_code == 503 and "finished setting up" in r.json()["detail"]
    # with a gateway: the parent's own site is the return address
    gw = _Gateway()
    monkeypatch.setattr(fp, "get_payment_resolver", lambda: _Resolver(gw))
    r = await http.post(f"{API}/payments/fees/initiate", headers={**P, "Origin": "https://portal.example.ng"},
                        json=dict(invoice_id=iid, provider="paystack"))
    assert r.status_code == 200
    assert gw.last_kw["callback_url"] == "https://portal.example.ng/dashboard/my-children/payments/callback?provider=paystack"


async def test_gateway_save_trims_and_rejects_public_key_in_secret_field(http, db, org, world, monkeypatch):
    import base64, os
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "ENCRYPTION_KEY", base64.b64encode(os.urandom(32)).decode(), raising=False)
    AD = _h(world["admin"])
    r = await http.post(f"{API}/finance/payment-gateways", headers=AD,
                        json=dict(provider="paystack", mode="live", secret_key="pk_live_abc"))
    assert r.status_code == 422 and "PUBLIC key" in r.json()["detail"]
    r = await http.post(f"{API}/finance/payment-gateways", headers=AD,
                        json=dict(provider="paystack", mode="live", secret_key="  sk_live_abc123\n"))
    assert r.status_code == 201, r.text


async def test_reconcile_settles_a_payment_whose_parent_never_returned(http, db, org, world, monkeypatch):
    """Parent paid at the gateway, browser never reached the callback page: the invoice must
    still get settled by reconcile (parent page open, or Finance 'Verify pending')."""
    w = world
    acc = await _user(db, org, "accountant", "Acc5")
    A, P = _h(acc), _h(w["parent"])
    gw = _Gateway()
    import app.routers.fee_payments as fp
    monkeypatch.setattr(fp, "get_payment_resolver", lambda: _Resolver(gw))
    r = await http.post(f"{API}/finance/fee-records/assign-class", headers=A, json=dict(
        class_id=w["cls"].id, term="Summer", session_year="2026/2027", tuition_fee=100000))
    inv = (await http.get(f"{API}/payments/remita/invoices", headers=P)).json()[0]
    ref = (await http.post(f"{API}/payments/fees/initiate", headers=P,
                           json=dict(invoice_id=inv["id"], provider="paystack"))).json()["reference"]
    # still unpaid at the gateway: nothing changes
    r = await http.post(f"{API}/payments/fees/reconcile-mine", headers=P)
    assert r.json()["settled"] == 0
    assert len((await http.get(f"{API}/payments/remita/invoices", headers=P)).json()) == 1
    # money lands; parent never visits the callback. Opening the fees page reconciles.
    gw.paid.add(ref)
    r = await http.post(f"{API}/payments/fees/reconcile-mine", headers=P)
    assert r.json()["settled"] == 1, r.text
    assert (await http.get(f"{API}/payments/remita/invoices", headers=P)).json() == []
    d = (await http.get(f"{API}/finance/broad-view/dashboard", headers=A)).json()
    assert d["full_payments"] == 1
    # repeating is harmless; a parent cannot run the school-wide reconcile
    assert (await http.post(f"{API}/payments/fees/reconcile", headers=A)).json()["pending"] == 0
    assert (await http.post(f"{API}/payments/fees/reconcile", headers=P)).status_code == 403


async def test_reconcile_reports_why_instead_of_500(http, db, org, world, monkeypatch):
    """If settling fails (here: the ledger period is locked) the finance user gets the
    reason, the payment stays pending for a retry, and nothing 500s."""
    from app.models.modules.finance import AccountingPeriod
    w = world
    acc = await _user(db, org, "accountant", "Acc6")
    A, P = _h(acc), _h(w["parent"])
    gw = _Gateway()
    import app.routers.fee_payments as fp
    monkeypatch.setattr(fp, "get_payment_resolver", lambda: _Resolver(gw))
    await http.post(f"{API}/finance/fee-records/assign-class", headers=A, json=dict(
        class_id=w["cls"].id, term="Summer", session_year="2026/2027", tuition_fee=100000))
    inv = (await http.get(f"{API}/payments/remita/invoices", headers=P)).json()[0]
    refs = []
    for _ in range(2):   # the parent paid twice -> two pending payments
        refs.append((await http.post(f"{API}/payments/fees/initiate", headers=P,
                                     json=dict(invoice_id=inv["id"], provider="paystack"))).json()["reference"])
    gw.paid.update(refs)
    today = date.today()
    db.add(AccountingPeriod(id=str(uuid.uuid4()), name="Locked month", start_date=date(today.year, today.month, 1),
                            end_date=date(today.year + (today.month == 12), today.month % 12 + 1, 1),
                            status="locked", org_id=org.id))
    await db.commit()
    r = await http.post(f"{API}/payments/fees/reconcile", headers=A)
    assert r.status_code == 200, r.text
    assert r.json()["errors"] == 2 and "locked" in r.json()["problems"][0]["reason"].lower()
