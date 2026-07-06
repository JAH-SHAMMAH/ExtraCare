"""Tests for Finance: Salary Advance (staff loans recovered via payroll/cash).

A salary advance rides the SAME ledger engine payroll uses, so these tests prove
— not assume — it inherits the shared-engine guards and mirrors payroll's controls:
  • approve DISBURSES a BALANCED Dr Staff Advances / Cr Cash entry
  • segregation of duties: approver != requester → 403 (same rule as payroll)
  • disbursing into a LOCKED period → 409 (inherited period-lock guard)
  • partial then full repayment posts balanced Dr Cash / Cr Staff Advances,
    accrues amount_repaid, and flips status → repaid when the balance clears
  • over-repayment is rejected (422); repaying an un-disbursed advance → 409
  • a disbursed advance can't be deleted; a pending one can
  • finance RBAC (write to request, post to approve/repay)
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
    LedgerAccount, AccountingPeriod, JournalLine, SalaryAdvance, SalaryAdvanceRepayment,
)
from app.routers.modules.finance import (
    create_salary_advance, approve_salary_advance, reject_salary_advance,
    repay_salary_advance, delete_salary_advance, list_salary_advances,
    STAFF_ADVANCE_ACCOUNT_CODE,
)
from app.schemas.finance import SalaryAdvanceCreate, SalaryAdvanceApprove, SalaryAdvanceRepay


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


# ── Request (create) ──────────────────────────────────────────────────────────

async def test_create_advance_is_pending_and_moves_no_money(db, org, teacher):
    staff = await _user(db, org, "staffer")
    a = await create_salary_advance(
        SalaryAdvanceCreate(staff_user_id=staff.id, amount=50000, reason="Rent"),
        request=None, db=db, current_user=teacher,
    )
    assert a.status == "pending"
    assert a.amount == 50000.0
    assert a.amount_repaid == 0.0
    assert a.outstanding == 50000.0
    assert a.disburse_entry_id is None            # nothing posted yet
    assert a.staff_name == "Staffer"
    assert a.requested_by == teacher.id


async def test_create_advance_unknown_staff_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_salary_advance(
            SalaryAdvanceCreate(staff_user_id="does-not-exist", amount=1000),
            request=None, db=db, current_user=teacher,
        )
    assert exc.value.status_code == 404


# ── Approve == disburse (ledger + SoD) ────────────────────────────────────────

async def test_approve_disburses_balanced_ledger(db, org):
    requester = await _user(db, org, "requester")
    approver = await _user(db, org, "approver")
    staff = await _user(db, org, "beneficiary")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    a = await create_salary_advance(
        SalaryAdvanceCreate(staff_user_id=staff.id, amount=30000),
        request=None, db=db, current_user=requester,
    )
    approved = await approve_salary_advance(
        a.id, payload=SalaryAdvanceApprove(cash_account_id=cash.id),
        request=None, db=db, current_user=approver,
    )
    assert approved.status == "approved"
    assert approved.approved_by == approver.id
    assert approved.disburse_entry_id is not None
    assert await _balanced(db, approved.disburse_entry_id)
    # A dedicated 'Staff Advances' asset account (1300) was auto-provisioned and DEBITED.
    adv_acct = (await db.execute(
        select(LedgerAccount).where(LedgerAccount.org_id == org.id, LedgerAccount.code == STAFF_ADVANCE_ACCOUNT_CODE)
    )).scalar_one_or_none()
    assert adv_acct is not None and adv_acct.type == "asset"
    lines = await _lines(db, approved.disburse_entry_id)
    adv_line = next(l for l in lines if l.account_id == adv_acct.id)
    cash_line = next(l for l in lines if l.account_id == cash.id)
    assert float(adv_line.debit) == 30000.0 and float(adv_line.credit) == 0.0   # Dr Staff Advances
    assert float(cash_line.credit) == 30000.0 and float(cash_line.debit) == 0.0  # Cr Cash


async def test_approve_auto_picks_cash_account(db, org):
    requester = await _user(db, org, "req2")
    approver = await _user(db, org, "app2")
    staff = await _user(db, org, "ben2")
    await _acct(db, org, "1000", "Cash", "asset")   # only asset → auto-picked
    a = await create_salary_advance(
        SalaryAdvanceCreate(staff_user_id=staff.id, amount=10000),
        request=None, db=db, current_user=requester,
    )
    approved = await approve_salary_advance(a.id, request=None, db=db, current_user=approver)
    assert approved.status == "approved"
    assert await _balanced(db, approved.disburse_entry_id)


async def test_approve_segregation_of_duties_block(db, org):
    staff = await _user(db, org, "ben3")
    await _acct(db, org, "1000", "Cash", "asset")
    same = await _user(db, org, "solo")
    a = await create_salary_advance(
        SalaryAdvanceCreate(staff_user_id=staff.id, amount=5000),
        request=None, db=db, current_user=same,
    )
    with pytest.raises(HTTPException) as exc:
        await approve_salary_advance(
            a.id, payload=SalaryAdvanceApprove(), request=None, db=db, current_user=same,
        )
    assert exc.value.status_code == 403   # approver must differ from requester (same rule as payroll)


async def test_approve_into_locked_period_rejected(db, org):
    requester = await _user(db, org, "req4")
    approver = await _user(db, org, "app4")
    staff = await _user(db, org, "ben4")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    a = await create_salary_advance(
        SalaryAdvanceCreate(staff_user_id=staff.id, amount=8000),
        request=None, db=db, current_user=requester,
    )
    await _lock_all_periods(db, org)   # today falls inside the locked period
    with pytest.raises(HTTPException) as exc:
        await approve_salary_advance(
            a.id, payload=SalaryAdvanceApprove(cash_account_id=cash.id),
            request=None, db=db, current_user=approver,
        )
    assert exc.value.status_code == 409   # inherited period-lock guard
    # And the advance stays pending — the disbursement rolled back cleanly.
    still = (await db.execute(select(SalaryAdvance).where(SalaryAdvance.id == a.id))).scalar_one()
    assert still.status == "pending" and still.disburse_entry_id is None


async def test_approve_twice_rejected(db, org):
    requester = await _user(db, org, "req5")
    approver = await _user(db, org, "app5")
    staff = await _user(db, org, "ben5")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    a = await create_salary_advance(
        SalaryAdvanceCreate(staff_user_id=staff.id, amount=6000),
        request=None, db=db, current_user=requester,
    )
    await approve_salary_advance(a.id, payload=SalaryAdvanceApprove(cash_account_id=cash.id),
                                 request=None, db=db, current_user=approver)
    with pytest.raises(HTTPException) as exc:
        await approve_salary_advance(a.id, payload=SalaryAdvanceApprove(cash_account_id=cash.id),
                                     request=None, db=db, current_user=approver)
    assert exc.value.status_code == 409


# ── Repayment ─────────────────────────────────────────────────────────────────

async def test_partial_then_full_repay(db, org):
    requester = await _user(db, org, "req6")
    approver = await _user(db, org, "app6")
    staff = await _user(db, org, "ben6")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    a = await create_salary_advance(
        SalaryAdvanceCreate(staff_user_id=staff.id, amount=20000),
        request=None, db=db, current_user=requester,
    )
    await approve_salary_advance(a.id, payload=SalaryAdvanceApprove(cash_account_id=cash.id),
                                 request=None, db=db, current_user=approver)
    # Partial repayment — still outstanding, still 'approved'.
    r1 = await repay_salary_advance(
        a.id, SalaryAdvanceRepay(amount=8000, method="payroll", cash_account_id=cash.id),
        request=None, db=db, current_user=approver,
    )
    assert r1.status == "approved"
    assert r1.amount_repaid == 8000.0
    assert r1.outstanding == 12000.0
    # Repayment posted a balanced Dr Cash / Cr Staff Advances.
    rep = (await db.execute(select(SalaryAdvanceRepayment).where(SalaryAdvanceRepayment.advance_id == a.id))).scalars().all()
    assert len(rep) == 1
    assert await _balanced(db, rep[0].journal_entry_id)
    adv_acct = (await db.execute(
        select(LedgerAccount).where(LedgerAccount.org_id == org.id, LedgerAccount.code == STAFF_ADVANCE_ACCOUNT_CODE)
    )).scalar_one()
    lines = await _lines(db, rep[0].journal_entry_id)
    adv_line = next(l for l in lines if l.account_id == adv_acct.id)
    assert float(adv_line.credit) == 8000.0   # Cr Staff Advances (recovering)
    # Final repayment clears the balance → 'repaid'.
    r2 = await repay_salary_advance(
        a.id, SalaryAdvanceRepay(amount=12000, method="cash", cash_account_id=cash.id),
        request=None, db=db, current_user=approver,
    )
    assert r2.status == "repaid"
    assert r2.amount_repaid == 20000.0
    assert r2.outstanding == 0.0


async def test_over_repay_rejected(db, org):
    requester = await _user(db, org, "req7")
    approver = await _user(db, org, "app7")
    staff = await _user(db, org, "ben7")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    a = await create_salary_advance(
        SalaryAdvanceCreate(staff_user_id=staff.id, amount=10000),
        request=None, db=db, current_user=requester,
    )
    await approve_salary_advance(a.id, payload=SalaryAdvanceApprove(cash_account_id=cash.id),
                                 request=None, db=db, current_user=approver)
    with pytest.raises(HTTPException) as exc:
        await repay_salary_advance(
            a.id, SalaryAdvanceRepay(amount=15000, cash_account_id=cash.id),
            request=None, db=db, current_user=approver,
        )
    assert exc.value.status_code == 422   # cannot repay more than outstanding


async def test_repay_before_approve_rejected(db, org):
    requester = await _user(db, org, "req8")
    staff = await _user(db, org, "ben8")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    a = await create_salary_advance(
        SalaryAdvanceCreate(staff_user_id=staff.id, amount=4000),
        request=None, db=db, current_user=requester,
    )
    with pytest.raises(HTTPException) as exc:
        await repay_salary_advance(
            a.id, SalaryAdvanceRepay(amount=1000, cash_account_id=cash.id),
            request=None, db=db, current_user=requester,
        )
    assert exc.value.status_code == 409   # nothing disbursed to repay


# ── Reject / Delete ───────────────────────────────────────────────────────────

async def test_reject_pending(db, org):
    requester = await _user(db, org, "req9")
    approver = await _user(db, org, "app9")
    staff = await _user(db, org, "ben9")
    a = await create_salary_advance(
        SalaryAdvanceCreate(staff_user_id=staff.id, amount=3000),
        request=None, db=db, current_user=requester,
    )
    rejected = await reject_salary_advance(a.id, request=None, db=db, current_user=approver)
    assert rejected.status == "rejected"


async def test_reject_after_approve_rejected(db, org):
    requester = await _user(db, org, "req10")
    approver = await _user(db, org, "app10")
    staff = await _user(db, org, "ben10")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    a = await create_salary_advance(
        SalaryAdvanceCreate(staff_user_id=staff.id, amount=3000),
        request=None, db=db, current_user=requester,
    )
    await approve_salary_advance(a.id, payload=SalaryAdvanceApprove(cash_account_id=cash.id),
                                 request=None, db=db, current_user=approver)
    with pytest.raises(HTTPException) as exc:
        await reject_salary_advance(a.id, request=None, db=db, current_user=approver)
    assert exc.value.status_code == 409


async def test_delete_pending_ok_but_disbursed_blocked(db, org):
    requester = await _user(db, org, "req11")
    approver = await _user(db, org, "app11")
    staff = await _user(db, org, "ben11")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    # Pending → deletable.
    a1 = await create_salary_advance(
        SalaryAdvanceCreate(staff_user_id=staff.id, amount=2000),
        request=None, db=db, current_user=requester,
    )
    await delete_salary_advance(a1.id, db=db, current_user=requester)
    gone = (await db.execute(select(SalaryAdvance).where(SalaryAdvance.id == a1.id))).scalar_one()
    assert gone.is_deleted is True
    listed = await list_salary_advances(status=None, staff_user_id=None, db=db, current_user=requester)
    assert all(x.id != a1.id for x in listed)
    # Disbursed → cannot delete.
    a2 = await create_salary_advance(
        SalaryAdvanceCreate(staff_user_id=staff.id, amount=2000),
        request=None, db=db, current_user=requester,
    )
    await approve_salary_advance(a2.id, payload=SalaryAdvanceApprove(cash_account_id=cash.id),
                                 request=None, db=db, current_user=approver)
    with pytest.raises(HTTPException) as exc:
        await delete_salary_advance(a2.id, db=db, current_user=requester)
    assert exc.value.status_code == 409


# ── RBAC ──────────────────────────────────────────────────────────────────────

async def test_salary_advance_rbac(db, org):
    # Request (draft) = payments:write; approve/reject/repay (post to ledger) = payments:post.
    manager = await _preset_user(db, org, "manager")
    assert manager.has_permission("payments:write")
    assert not manager.has_permission("payments:post")     # can request, cannot disburse
    accountant = await _preset_user(db, org, "accountant")
    assert accountant.has_permission("payments:write") and accountant.has_permission("payments:post")
    for slug in ("teacher", "parent", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("payments:write")
        assert not u.has_permission("payments:post")
