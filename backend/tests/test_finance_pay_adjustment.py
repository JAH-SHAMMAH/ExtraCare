"""Tests for Finance: Bonus/Reduction Pack (batch pay adjustments).

Like Salary Advance, a pack rides the SAME ledger engine + two-person control as
payroll, so these prove — not assume — the shared-engine guards and the correct,
kind-dependent double-entry direction:
  • bonus     approve → Dr expense / Cr settle   (balanced)
  • reduction approve → Dr settle  / Cr expense  (balanced)
  • segregation of duties: approver != creator → 403
  • approving into a LOCKED period → 409 (inherited period-lock guard)
  • void reverses the ledger entry; draft-only delete; mismatched-account guard
  • finance RBAC (write to draft, post to approve/void)
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.finance import (
    LedgerAccount, AccountingPeriod, JournalEntry, JournalLine, PayAdjustmentPack,
)
from app.routers.modules.finance import (
    create_pay_adjustment, approve_pay_adjustment, void_pay_adjustment,
    delete_pay_adjustment, list_pay_adjustments,
)
from app.schemas.finance import PayAdjustmentCreate, PayAdjustmentItemInput


pytestmark = pytest.mark.asyncio


async def _acct(db, org, code, name, type_) -> LedgerAccount:
    a = LedgerAccount(id=str(uuid.uuid4()), code=code, name=name, type=type_, org_id=org.id, is_active=True)
    db.add(a)
    await db.commit()
    return a


async def _user(db, org, name) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{name}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=name.title(), status=UserStatus.ACTIVE, org_id=org.id)
    db.add(u)
    await db.commit()
    return u


async def _preset_user(db, org, slug) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _lock_all_periods(db, org):
    p = AccountingPeriod(id=str(uuid.uuid4()), name="Locked", start_date=date(2000, 1, 1),
                         end_date=date(2100, 1, 1), status="locked", org_id=org.id)
    db.add(p)
    await db.commit()
    return p


async def _lines(db, entry_id):
    return (await db.execute(select(JournalLine).where(JournalLine.entry_id == entry_id))).scalars().all()


async def _balanced(db, entry_id) -> bool:
    lines = await _lines(db, entry_id)
    return len(lines) >= 2 and sum(float(l.debit) for l in lines) == sum(float(l.credit) for l in lines)


def _bonus_payload(exp, cash, kind="bonus", label="December Bonus"):
    return PayAdjustmentCreate(
        label=label, kind=kind, expense_account_id=exp.id, settle_account_id=cash.id,
        items=[
            PayAdjustmentItemInput(staff_name="Alice", amount=15000),
            PayAdjustmentItemInput(staff_name="Bob", amount=10000),
        ],
    )


# ── Create (draft) ────────────────────────────────────────────────────────────

async def test_create_pack_is_draft_no_ledger(db, org, teacher):
    exp = await _acct(db, org, "6100", "Bonus Expense", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    p = await create_pay_adjustment(_bonus_payload(exp, cash), request=None, db=db, current_user=teacher)
    assert p.status == "draft"
    assert p.kind == "bonus"
    assert p.total_amount == 25000.0        # 15000 + 10000
    assert p.journal_entry_id is None
    assert len(p.items) == 2


async def test_create_rejects_same_account_both_sides(db, org, teacher):
    cash = await _acct(db, org, "1000", "Cash", "asset")
    with pytest.raises(HTTPException) as exc:
        await create_pay_adjustment(
            PayAdjustmentCreate(label="Bad", kind="bonus", expense_account_id=cash.id, settle_account_id=cash.id,
                                items=[PayAdjustmentItemInput(staff_name="X", amount=1000)]),
            request=None, db=db, current_user=teacher,
        )
    assert exc.value.status_code == 422


async def test_create_rejects_unknown_account(db, org, teacher):
    cash = await _acct(db, org, "1000", "Cash", "asset")
    with pytest.raises(HTTPException) as exc:
        await create_pay_adjustment(
            PayAdjustmentCreate(label="Bad", kind="bonus", expense_account_id="nope", settle_account_id=cash.id,
                                items=[PayAdjustmentItemInput(staff_name="X", amount=1000)]),
            request=None, db=db, current_user=teacher,
        )
    assert exc.value.status_code == 404


# ── Approve == post to ledger (direction + SoD) ───────────────────────────────

async def test_bonus_approve_posts_dr_expense_cr_cash(db, org):
    creator = await _user(db, org, "creator")
    approver = await _user(db, org, "approver")
    exp = await _acct(db, org, "6100", "Bonus Expense", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    p = await create_pay_adjustment(_bonus_payload(exp, cash), request=None, db=db, current_user=creator)
    approved = await approve_pay_adjustment(p.id, request=None, db=db, current_user=approver)
    assert approved.status == "approved"
    assert approved.journal_entry_id is not None
    assert approved.approved_by == approver.id
    assert await _balanced(db, approved.journal_entry_id)
    lines = await _lines(db, approved.journal_entry_id)
    exp_line = next(l for l in lines if l.account_id == exp.id)
    cash_line = next(l for l in lines if l.account_id == cash.id)
    assert float(exp_line.debit) == 25000.0 and float(exp_line.credit) == 0.0   # Dr Bonus Expense
    assert float(cash_line.credit) == 25000.0 and float(cash_line.debit) == 0.0  # Cr Cash


async def test_reduction_approve_posts_dr_cash_cr_income(db, org):
    creator = await _user(db, org, "creator2")
    approver = await _user(db, org, "approver2")
    income = await _acct(db, org, "4200", "Recoveries / Penalties", "income")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    p = await create_pay_adjustment(
        PayAdjustmentCreate(label="Late Penalty", kind="reduction", expense_account_id=income.id,
                            settle_account_id=cash.id,
                            items=[PayAdjustmentItemInput(staff_name="Carol", amount=3000)]),
        request=None, db=db, current_user=creator,
    )
    approved = await approve_pay_adjustment(p.id, request=None, db=db, current_user=approver)
    assert await _balanced(db, approved.journal_entry_id)
    lines = await _lines(db, approved.journal_entry_id)
    cash_line = next(l for l in lines if l.account_id == cash.id)
    income_line = next(l for l in lines if l.account_id == income.id)
    assert float(cash_line.debit) == 3000.0 and float(cash_line.credit) == 0.0     # Dr Cash (money kept)
    assert float(income_line.credit) == 3000.0 and float(income_line.debit) == 0.0  # Cr Income/offset


async def test_approve_segregation_of_duties_block(db, org):
    same = await _user(db, org, "solo")
    exp = await _acct(db, org, "6100", "Bonus Expense", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    p = await create_pay_adjustment(_bonus_payload(exp, cash), request=None, db=db, current_user=same)
    with pytest.raises(HTTPException) as exc:
        await approve_pay_adjustment(p.id, request=None, db=db, current_user=same)
    assert exc.value.status_code == 403   # approver must differ from creator (same rule as payroll)


async def test_approve_into_locked_period_rejected(db, org):
    creator = await _user(db, org, "creator3")
    approver = await _user(db, org, "approver3")
    exp = await _acct(db, org, "6100", "Bonus Expense", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    p = await create_pay_adjustment(_bonus_payload(exp, cash), request=None, db=db, current_user=creator)
    await _lock_all_periods(db, org)
    with pytest.raises(HTTPException) as exc:
        await approve_pay_adjustment(p.id, request=None, db=db, current_user=approver)
    assert exc.value.status_code == 409   # inherited period-lock guard
    still = (await db.execute(select(PayAdjustmentPack).where(PayAdjustmentPack.id == p.id))).scalar_one()
    assert still.status == "draft" and still.journal_entry_id is None


async def test_approve_twice_rejected(db, org):
    creator = await _user(db, org, "creator4")
    approver = await _user(db, org, "approver4")
    exp = await _acct(db, org, "6100", "Bonus Expense", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    p = await create_pay_adjustment(_bonus_payload(exp, cash), request=None, db=db, current_user=creator)
    await approve_pay_adjustment(p.id, request=None, db=db, current_user=approver)
    with pytest.raises(HTTPException) as exc:
        await approve_pay_adjustment(p.id, request=None, db=db, current_user=approver)
    assert exc.value.status_code == 409


# ── Void / Delete ─────────────────────────────────────────────────────────────

async def test_void_reverses_posted_pack(db, org):
    creator = await _user(db, org, "creator5")
    approver = await _user(db, org, "approver5")
    exp = await _acct(db, org, "6100", "Bonus Expense", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    p = await create_pay_adjustment(_bonus_payload(exp, cash), request=None, db=db, current_user=creator)
    approved = await approve_pay_adjustment(p.id, request=None, db=db, current_user=approver)
    voided = await void_pay_adjustment(p.id, request=None, db=db, current_user=approver)
    assert voided.status == "void"
    # The original entry was reversed (a reversing entry now points back to it).
    orig = (await db.execute(select(JournalEntry).where(JournalEntry.id == approved.journal_entry_id))).scalar_one()
    assert orig.reversed_by_id is not None


async def test_delete_draft_ok_but_posted_blocked(db, org):
    creator = await _user(db, org, "creator6")
    approver = await _user(db, org, "approver6")
    exp = await _acct(db, org, "6100", "Bonus Expense", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    # draft → deletable
    p1 = await create_pay_adjustment(_bonus_payload(exp, cash), request=None, db=db, current_user=creator)
    await delete_pay_adjustment(p1.id, db=db, current_user=creator)
    listed = await list_pay_adjustments(kind=None, status=None, db=db, current_user=creator)
    assert all(x.id != p1.id for x in listed)
    # posted → cannot delete (must void)
    p2 = await create_pay_adjustment(_bonus_payload(exp, cash), request=None, db=db, current_user=creator)
    await approve_pay_adjustment(p2.id, request=None, db=db, current_user=approver)
    with pytest.raises(HTTPException) as exc:
        await delete_pay_adjustment(p2.id, db=db, current_user=creator)
    assert exc.value.status_code == 409


async def test_list_filters_by_kind(db, org, teacher):
    exp = await _acct(db, org, "6100", "Bonus Expense", "expense")
    income = await _acct(db, org, "4200", "Penalties", "income")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    await create_pay_adjustment(_bonus_payload(exp, cash, kind="bonus", label="B1"), request=None, db=db, current_user=teacher)
    await create_pay_adjustment(
        PayAdjustmentCreate(label="R1", kind="reduction", expense_account_id=income.id, settle_account_id=cash.id,
                            items=[PayAdjustmentItemInput(staff_name="Z", amount=500)]),
        request=None, db=db, current_user=teacher,
    )
    bonuses = await list_pay_adjustments(kind="bonus", status=None, db=db, current_user=teacher)
    reductions = await list_pay_adjustments(kind="reduction", status=None, db=db, current_user=teacher)
    assert all(x.kind == "bonus" for x in bonuses) and len(bonuses) >= 1
    assert all(x.kind == "reduction" for x in reductions) and len(reductions) >= 1


# ── RBAC ──────────────────────────────────────────────────────────────────────

async def test_pay_adjustment_rbac(db, org):
    # Draft = payments:write; approve/void (post to ledger) = payments:post.
    manager = await _preset_user(db, org, "manager")
    assert manager.has_permission("payments:write")
    assert not manager.has_permission("payments:post")
    accountant = await _preset_user(db, org, "accountant")
    assert accountant.has_permission("payments:write") and accountant.has_permission("payments:post")
    for slug in ("teacher", "parent", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("payments:write")
        assert not u.has_permission("payments:post")
