"""Remita payment recording — the money-critical logic that can't be clicked.

Proves, with a mocked Remita status response:
  • a confirmed payment records EXACTLY ONCE and posts a balanced ledger entry
    (Dr "Remita / Bank" 1015, Cr the invoice's Receivable);
  • the callback (verify) and the webhook cannot double-pay, in either order;
  • an unpaid/pending status records nothing and leaves the invoice posted.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select, func

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.finance import LedgerAccount, Invoice, JournalEntry, JournalLine
from app.models.modules.remita import RemitaTransaction
import app.routers.remita as remita_router

pytestmark = pytest.mark.asyncio


async def _user(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"p-{uuid.uuid4().hex[:6]}@example.com", full_name="Parent P", status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="parent", slug=f"parent-{uuid.uuid4().hex[:6]}", permissions=list(SCHOOL_PERMISSION_PRESETS["parent"]), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _receivable(db, org) -> LedgerAccount:
    a = LedgerAccount(id=str(uuid.uuid4()), code="1200", name="Accounts Receivable", type="asset", org_id=org.id)
    db.add(a)
    await db.flush()
    return a


async def _posted_invoice(db, org, recv, total="5000.00") -> Invoice:
    inv = Invoice(id=str(uuid.uuid4()), number=f"INV-{uuid.uuid4().hex[:6]}", customer_name="Parent P",
                  status="posted", total=Decimal(total), receivable_account_id=recv.id, org_id=org.id)
    db.add(inv)
    await db.flush()
    return inv


async def _tx(db, org, inv, rrr) -> RemitaTransaction:
    t = RemitaTransaction(id=str(uuid.uuid4()), org_id=org.id, invoice_id=inv.id, order_id=uuid.uuid4().hex[:12],
                          rrr=rrr, amount=inv.total, status="pending", initiated_by=None)
    db.add(t)
    await db.commit()
    return t


def _mock_status(monkeypatch, payload):
    async def fake(rrr):
        return payload
    monkeypatch.setattr(remita_router.remita_svc, "query_status", fake)


async def _entries(db, org) -> int:
    return (await db.execute(select(func.count(JournalEntry.id)).where(JournalEntry.org_id == org.id))).scalar()


# ── records once + posts the right ledger lines ──────────────────────────────────

async def test_verify_records_payment_with_dedicated_account(db, org, monkeypatch):
    user = await _user(db, org)
    recv = await _receivable(db, org)
    inv = await _posted_invoice(db, org, recv)
    await _tx(db, org, inv, "RRR-AAA")
    _mock_status(monkeypatch, {"status": "00"})

    before = await _entries(db, org)
    res = await remita_router.verify("RRR-AAA", request=None, db=db, current_user=user)
    assert res.status == "paid"

    inv2 = (await db.execute(select(Invoice).where(Invoice.id == inv.id))).scalar_one()
    assert inv2.status == "paid"
    assert inv2.payment_entry_id is not None

    assert await _entries(db, org) == before + 1   # exactly one posting

    lines = (await db.execute(select(JournalLine).where(JournalLine.entry_id == inv2.payment_entry_id))).scalars().all()
    assert len(lines) == 2
    assert sum(float(l.debit) for l in lines) == sum(float(l.credit) for l in lines) == 5000.0  # balanced

    bank = (await db.execute(select(LedgerAccount).where(LedgerAccount.org_id == org.id, LedgerAccount.code == "1015"))).scalar_one()
    assert bank.name == "Remita / Bank"
    dr = next(l for l in lines if float(l.debit) > 0)
    cr = next(l for l in lines if float(l.credit) > 0)
    assert dr.account_id == bank.id      # Dr Remita / Bank (dedicated, not auto-picked)
    assert cr.account_id == recv.id      # Cr Receivable


# ── idempotency: callback + webhook can't double-pay, either order ───────────────

async def test_callback_then_webhook_no_double_pay(db, org, monkeypatch):
    user = await _user(db, org)
    recv = await _receivable(db, org)
    inv = await _posted_invoice(db, org, recv)
    await _tx(db, org, inv, "RRR-BBB")
    _mock_status(monkeypatch, {"status": "00"})

    await remita_router.verify("RRR-BBB", request=None, db=db, current_user=user)
    after_first = await _entries(db, org)
    await remita_router.webhook(request=None, payload={"rrr": "RRR-BBB"}, db=db)
    assert await _entries(db, org) == after_first   # webhook posted nothing extra

    inv2 = (await db.execute(select(Invoice).where(Invoice.id == inv.id))).scalar_one()
    assert inv2.status == "paid"


async def test_webhook_then_callback_single_payment(db, org, monkeypatch):
    user = await _user(db, org)
    recv = await _receivable(db, org)
    inv = await _posted_invoice(db, org, recv)
    await _tx(db, org, inv, "RRR-CCC")
    _mock_status(monkeypatch, {"status": "00"})

    before = await _entries(db, org)
    await remita_router.webhook(request=None, payload={"RRR": "RRR-CCC"}, db=db)
    await remita_router.verify("RRR-CCC", request=None, db=db, current_user=user)
    assert await _entries(db, org) == before + 1   # exactly one, across both paths


# ── unpaid status records nothing ────────────────────────────────────────────────

async def test_pending_status_records_nothing(db, org, monkeypatch):
    user = await _user(db, org)
    recv = await _receivable(db, org)
    inv = await _posted_invoice(db, org, recv)
    await _tx(db, org, inv, "RRR-DDD")
    _mock_status(monkeypatch, {"status": "021"})   # not a paid code

    before = await _entries(db, org)
    res = await remita_router.verify("RRR-DDD", request=None, db=db, current_user=user)
    assert res.status == "pending"
    assert await _entries(db, org) == before
    inv2 = (await db.execute(select(Invoice).where(Invoice.id == inv.id))).scalar_one()
    assert inv2.status == "posted"   # untouched
