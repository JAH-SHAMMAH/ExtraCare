"""Tests for Invoice Center + Payroll (Batch 5), incl. segregation of duties.

Headline: a payroll run cannot be approved by its creator (two-person control),
and posting an invoice/payroll produces a balanced, immutable ledger entry that
void corrects via reversal. Handlers called directly per convention.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.finance import LedgerAccount, JournalEntry, JournalLine, Invoice, PayrollRun
from app.routers.modules.finance import (
    create_invoice, post_invoice, pay_invoice, void_invoice, update_invoice,
    create_payroll, approve_payroll, void_payroll,
)
from app.schemas.finance import (
    InvoiceCreate, InvoiceLineInput, InvoiceUpdate, PaymentRequest,
    PayrollRunCreate, PayslipInput,
)


pytestmark = pytest.mark.asyncio


async def _acct(db, org, code, name, type_) -> LedgerAccount:
    a = LedgerAccount(id=str(uuid.uuid4()), code=code, name=name, type=type_, org_id=org.id, is_active=True)
    db.add(a)
    await db.commit()
    return a


async def _preset_user(db, org, slug, email=None) -> User:
    u = User(id=str(uuid.uuid4()), email=email or f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _entry_balanced(db, entry_id) -> bool:
    lines = (await db.execute(select(JournalLine).where(JournalLine.entry_id == entry_id))).scalars().all()
    return sum(float(l.debit) for l in lines) == sum(float(l.credit) for l in lines) and len(lines) >= 2


# ── Invoices ───────────────────────────────────────────────────────────────────

async def test_invoice_lifecycle_posts_balanced_entry(db, org, teacher):
    ar = await _acct(db, org, "1100", "Accounts Receivable", "asset")
    fees = await _acct(db, org, "4000", "Tuition", "income")
    cash = await _acct(db, org, "1000", "Cash", "asset")

    inv = await create_invoice(
        InvoiceCreate(customer_name="Mr Bello", invoice_date=date(2026, 2, 1), receivable_account_id=ar.id,
                      lines=[InvoiceLineInput(description="Term fees", quantity=2, unit_price=150, income_account_id=fees.id)]),
        request=None, db=db, current_user=teacher,
    )
    assert inv.status == "draft"
    assert inv.total == 300.0

    posted = await post_invoice(inv.id, request=None, db=db, current_user=teacher)
    assert posted.status == "posted"
    assert posted.journal_entry_id is not None
    assert await _entry_balanced(db, posted.journal_entry_id)

    paid = await pay_invoice(inv.id, PaymentRequest(cash_account_id=cash.id), request=None, db=db, current_user=teacher)
    assert paid.status == "paid"
    assert paid.payment_entry_id is not None


async def test_posted_invoice_is_immutable(db, org, teacher):
    ar = await _acct(db, org, "1100", "AR", "asset")
    fees = await _acct(db, org, "4000", "Fees", "income")
    inv = await create_invoice(
        InvoiceCreate(customer_name="X", receivable_account_id=ar.id,
                      lines=[InvoiceLineInput(description="f", unit_price=100, income_account_id=fees.id)]),
        request=None, db=db, current_user=teacher,
    )
    await post_invoice(inv.id, request=None, db=db, current_user=teacher)
    with pytest.raises(HTTPException) as exc:
        await update_invoice(inv.id, InvoiceUpdate(customer_name="Y"), db=db, current_user=teacher)
    assert exc.value.status_code == 409


async def test_void_posted_invoice_reverses(db, org, teacher):
    ar = await _acct(db, org, "1100", "AR", "asset")
    fees = await _acct(db, org, "4000", "Fees", "income")
    inv = await create_invoice(
        InvoiceCreate(customer_name="X", receivable_account_id=ar.id,
                      lines=[InvoiceLineInput(description="f", unit_price=100, income_account_id=fees.id)]),
        request=None, db=db, current_user=teacher,
    )
    posted = await post_invoice(inv.id, request=None, db=db, current_user=teacher)
    jid = posted.journal_entry_id
    voided = await void_invoice(inv.id, request=None, db=db, current_user=teacher)
    assert voided.status == "void"
    original = (await db.execute(select(JournalEntry).where(JournalEntry.id == jid))).scalar_one()
    assert original.reversed_by_id is not None   # corrected by reversal, not deleted


# ── Payroll: segregation of duties / two-person ────────────────────────────────

async def test_payroll_creator_cannot_self_approve(db, org):
    expense = await _acct(db, org, "5000", "Salaries", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    accountant = await _preset_user(db, org, "accountant", "acc1@example.com")
    run = await create_payroll(
        PayrollRunCreate(period_label="Jan", run_date=date(2026, 1, 31), expense_account_id=expense.id,
                         net_account_id=cash.id, payslips=[PayslipInput(staff_name="Mr A", gross=1000, deductions=100)]),
        request=None, db=db, current_user=accountant,
    )
    assert run.status == "draft"
    # Same person approving their own run is refused (two-person control).
    with pytest.raises(HTTPException) as exc:
        await approve_payroll(run.id, request=None, db=db, current_user=accountant)
    assert exc.value.status_code == 403


async def test_payroll_approved_by_second_person_posts_balanced(db, org):
    expense = await _acct(db, org, "5000", "Salaries", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    deductions = await _acct(db, org, "2100", "Deductions Payable", "liability")
    creator = await _preset_user(db, org, "accountant", "acc2@example.com")
    approver = await _preset_user(db, org, "org_admin", "boss@example.com")
    run = await create_payroll(
        PayrollRunCreate(period_label="Feb", run_date=date(2026, 2, 28), expense_account_id=expense.id,
                         net_account_id=cash.id, deductions_account_id=deductions.id,
                         payslips=[PayslipInput(staff_name="A", gross=1000, deductions=100),
                                   PayslipInput(staff_name="B", gross=500, deductions=0)]),
        request=None, db=db, current_user=creator,
    )
    posted = await approve_payroll(run.id, request=None, db=db, current_user=approver)
    assert posted.status == "posted"
    assert posted.approved_by == approver.id
    assert posted.total_gross == 1500.0 and posted.total_net == 1400.0 and posted.total_deductions == 100.0
    assert await _entry_balanced(db, posted.journal_entry_id)


async def test_payroll_void_reverses(db, org):
    expense = await _acct(db, org, "5000", "Salaries", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    creator = await _preset_user(db, org, "accountant", "acc3@example.com")
    approver = await _preset_user(db, org, "org_admin", "boss2@example.com")
    run = await create_payroll(
        PayrollRunCreate(period_label="Mar", expense_account_id=expense.id, net_account_id=cash.id,
                         payslips=[PayslipInput(staff_name="A", gross=800)]),
        request=None, db=db, current_user=creator,
    )
    posted = await approve_payroll(run.id, request=None, db=db, current_user=approver)
    jid = posted.journal_entry_id
    voided = await void_payroll(run.id, request=None, db=db, current_user=approver)
    assert voided.status == "void"
    original = (await db.execute(select(JournalEntry).where(JournalEntry.id == jid))).scalar_one()
    assert original.reversed_by_id is not None


async def test_payroll_tenant_scoped(db, org, teacher):
    from app.models.organization import Organization, IndustryType
    from app.routers.modules.finance import list_payroll
    expense = await _acct(db, org, "5000", "Salaries", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    creator = await _preset_user(db, org, "accountant", "acc4@example.com")
    await create_payroll(
        PayrollRunCreate(period_label="Apr", expense_account_id=expense.id, net_account_id=cash.id,
                         payslips=[PayslipInput(staff_name="A", gross=800)]),
        request=None, db=db, current_user=creator,
    )
    other = Organization(id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:6]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    other_user = User(id=str(uuid.uuid4()), email="o@example.com", full_name="O",
                      status=UserStatus.ACTIVE, org_id=other.id)
    db.add(other_user)
    await db.commit()
    theirs = await list_payroll(status=None, page=1, page_size=25, db=db, current_user=other_user)
    assert theirs.total == 0
