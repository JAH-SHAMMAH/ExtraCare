"""Tests for the Broad View → Report Dashboard: invoice/payment/debt cards,
income distribution, and each bank's CURRENT balance (its cash ledger account)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.user import User, UserStatus
from app.models.payment import StudentFeeRecord
from app.models.modules.finance import LedgerAccount, BankAccount, Invoice, InvoiceLine, FeeDiscount
from app.models.modules.wallet import ParentWallet, ParentWalletEntry
from app.routers.modules.finance import (
    broad_view_dashboard, broad_view_account_head_summary, broad_view_termly_summary,
    broad_view_discount_log, broad_view_wallet_log,
)
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


# ── Batch 2 tabs ──────────────────────────────────────────────────────────────

async def test_account_head_summary(db, org):
    admin = await _admin(db, org)
    income = await _acct(db, org, "4000", "School Fees", "income")
    inv = Invoice(id=str(uuid.uuid4()), number="INV-1", customer_name="Ada", total=Decimal(500), status="paid", org_id=org.id)
    db.add(inv)
    await db.flush()
    db.add(InvoiceLine(id=str(uuid.uuid4()), invoice_id=inv.id, description="Term fees", quantity=Decimal(1),
                       unit_price=Decimal(500), amount=Decimal(500), income_account_id=income.id, org_id=org.id))
    await db.commit()

    res = await broad_view_account_head_summary(db=db, current_user=admin)
    row = next(r for r in res.items if r.account_name == "School Fees")
    assert row.total_invoice == 1 and row.total_receipt == 1
    assert row.invoice_charge == 500.0 and row.amount_paid == 500.0


async def test_termly_summary(db, org, student):
    admin = await _admin(db, org)
    fr = StudentFeeRecord(id=str(uuid.uuid4()), org_id=org.id, student_id=student.id, term="term1_2026",
                          session_year="2026", tuition_fee=Decimal(1000), exam_fee=Decimal(200),
                          total_fee=Decimal(1200), paid_amount=Decimal(0), outstanding_balance=Decimal(1200), payment_status="unpaid")
    db.add(fr)
    await db.commit()
    res = await broad_view_termly_summary(session="2026", term="term1_2026", db=db, current_user=admin)
    by = {r.fee: r.amount for r in res.items}
    assert by["Tuition"] == 1000.0 and by["Exam"] == 200.0 and res.total == 1200.0


async def test_discount_log(db, org, student):
    admin = await _admin(db, org)
    db.add(FeeDiscount(id=str(uuid.uuid4()), org_id=org.id, student_id=student.id, student_name="Ada Okafor",
                       discount_type="fixed", value=Decimal(100), amount=Decimal(100), reason="sibling", status="approved"))
    await db.commit()
    res = await broad_view_discount_log(db=db, current_user=admin)
    assert len(res.items) == 1 and res.items[0].student_name == "Ada Okafor"
    assert res.items[0].amount == 100.0 and res.total_discount == 100.0


async def test_wallet_log(db, org):
    admin = await _admin(db, org)
    parent = User(id=str(uuid.uuid4()), email=f"p-{uuid.uuid4().hex[:6]}@example.com", full_name="Mrs Parent",
                  status=UserStatus.ACTIVE, org_id=org.id)
    db.add(parent)
    await db.flush()
    w = ParentWallet(id=str(uuid.uuid4()), user_id=parent.id, is_active=True, org_id=org.id)
    db.add(w)
    await db.flush()
    db.add(ParentWalletEntry(id=str(uuid.uuid4()), wallet_id=w.id, user_id=parent.id, kind="credit", signed_amount=Decimal(500), org_id=org.id))
    db.add(ParentWalletEntry(id=str(uuid.uuid4()), wallet_id=w.id, user_id=parent.id, kind="debit", signed_amount=Decimal(-120), org_id=org.id))
    await db.commit()

    res = await broad_view_wallet_log(db=db, current_user=admin)
    assert len(res.items) == 2
    assert res.total_credit == 500.0 and res.total_debit == 120.0
    assert all(r.wallet_name == "Mrs Parent" for r in res.items)
