"""Tests for the Broad View → Report Dashboard: invoice/payment/debt cards,
income distribution, and each bank's CURRENT balance (its cash ledger account)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.user import User, UserStatus
from app.models.payment import StudentFeeRecord
from app.models.modules.finance import LedgerAccount, BankAccount, Invoice
from app.routers.modules.finance import broad_view_dashboard
from app.services import ledger


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@example.com", full_name="Admin",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def _acct(db, org, code, name, type_) -> LedgerAccount:
    a = LedgerAccount(id=str(uuid.uuid4()), code=code, name=name, type=type_, org_id=org.id, is_active=True)
    db.add(a)
    await db.commit()
    return a


async def _fee(db, org, student_id, total, paid, status) -> StudentFeeRecord:
    fr = StudentFeeRecord(id=str(uuid.uuid4()), org_id=org.id, student_id=student_id, term="term1_2026",
                          session_year="2026", total_fee=Decimal(total), paid_amount=Decimal(paid),
                          outstanding_balance=Decimal(total) - Decimal(paid), payment_status=status)
    db.add(fr)
    await db.commit()
    return fr


async def test_broad_view_dashboard(db, org, student):
    admin = await _admin(db, org)
    cash = await _acct(db, org, "1001", "Access Bank Cash", "asset")
    income = await _acct(db, org, "4000", "School Fees", "income")
    # Dr Cash / Cr Income 1000 → cash balance 1000, income 1000.
    await ledger.post_journal_entry(
        db, org_id=org.id, entry_date=date(2026, 5, 1), memo="fees", source="manual", source_id=None,
        lines=[{"account_id": cash.id, "debit": Decimal(1000), "credit": 0},
               {"account_id": income.id, "debit": 0, "credit": Decimal(1000)}],
        actor=admin,
    )
    db.add(BankAccount(id=str(uuid.uuid4()), bank_name="Access Bank", account_name="Fairview", account_number="0022699874",
                       ledger_account_id=cash.id, is_active=True, org_id=org.id))
    db.add(Invoice(id=str(uuid.uuid4()), number="INV-1", customer_name="Ada", total=Decimal(500), status="posted", org_id=org.id))
    await db.commit()

    await _fee(db, org, student.id, 500, 500, "paid")
    await _fee(db, org, student.id, 300, 100, "partial")
    await _fee(db, org, student.id, 400, 0, "unpaid")

    res = await broad_view_dashboard(session=None, term=None, db=db, current_user=admin)
    assert res.invoices == 1
    assert res.full_payments == 1 and res.part_payments == 1
    assert res.total_revenue == 1200.0        # 500 + 300 + 400
    assert res.total_full_payment == 500.0
    assert res.total_part_payment == 100.0
    assert res.total_debt == 600.0            # 0 + 200 + 400
    assert res.bank_accounts == 1
    # Bank shows its CURRENT balance (cash ledger = Dr 1000).
    assert res.banks[0].balance == 1000.0 and res.banks[0].bank_name == "Access Bank"
    # Income distribution by head.
    assert any(d.head == "School Fees" and d.amount == 1000.0 for d in res.distribution)


async def test_broad_view_session_filter(db, org, student):
    admin = await _admin(db, org)
    await _fee(db, org, student.id, 1000, 0, "unpaid")   # session_year "2026"
    # Matching session → counted.
    r1 = await broad_view_dashboard(session="2026", term=None, db=db, current_user=admin)
    assert r1.total_revenue == 1000.0
    # Non-matching session → excluded.
    r2 = await broad_view_dashboard(session="2099", term=None, db=db, current_user=admin)
    assert r2.total_revenue == 0.0
