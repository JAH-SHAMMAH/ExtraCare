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
    fee = dict(term="Summer", session_year="2026/2027", tuition_fee=150000, exam_fee=20000)
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
