"""Tests for Finance: Requisitions / Request Form (purchase-request approval).

Like the other Finance workflows, a requisition rides the SAME ledger engine +
two-person control as payroll, so these prove — not assume — the shared-engine
guards and the correct double-entry on approval:
  • create computes line amount (qty × unit_cost) and the total; draft posts nothing
  • approve posts a BALANCED Dr Expense / Cr Cash|Payable entry
  • segregation of duties: approver != requester → 403
  • approving into a LOCKED period → 409 (inherited period-lock guard)
  • reject (draft only), void reverses, draft-only delete, mismatched-account guard
  • finance RBAC (write to raise, post to approve/reject/void)
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
    LedgerAccount, AccountingPeriod, JournalEntry, JournalLine, Requisition,
)
from app.routers.modules.finance import (
    create_requisition, approve_requisition, reject_requisition,
    void_requisition, delete_requisition, list_requisitions,
)
from app.schemas.finance import RequisitionCreate, RequisitionItemInput


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


def _payload(exp, cash, title="New whiteboards"):
    return RequisitionCreate(
        title=title, department="Science", category="supplies",
        expense_account_id=exp.id, settle_account_id=cash.id,
        items=[
            RequisitionItemInput(description="Whiteboard", quantity=2, unit_cost=5000),   # 10000
            RequisitionItemInput(description="Markers (box)", quantity=1, unit_cost=3000),  # 3000
        ],
    )


# ── Create (draft) ────────────────────────────────────────────────────────────

async def test_create_is_draft_computes_total_no_ledger(db, org, teacher):
    exp = await _acct(db, org, "5200", "Teaching Supplies", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    r = await create_requisition(_payload(exp, cash), request=None, db=db, current_user=teacher)
    assert r.status == "draft"
    assert r.total_amount == 13000.0          # 2×5000 + 1×3000
    assert r.items[0].amount == 10000.0       # qty × unit_cost computed server-side
    assert r.journal_entry_id is None
    assert r.requested_by == teacher.id


async def test_create_rejects_zero_total(db, org, teacher):
    exp = await _acct(db, org, "5200", "Supplies", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    with pytest.raises(HTTPException) as exc:
        await create_requisition(
            RequisitionCreate(title="Freebies", expense_account_id=exp.id, settle_account_id=cash.id,
                              items=[RequisitionItemInput(description="X", quantity=3, unit_cost=0)]),
            request=None, db=db, current_user=teacher,
        )
    assert exc.value.status_code == 422       # total must be positive


async def test_create_rejects_same_account(db, org, teacher):
    cash = await _acct(db, org, "1000", "Cash", "asset")
    with pytest.raises(HTTPException) as exc:
        await create_requisition(
            RequisitionCreate(title="Bad", expense_account_id=cash.id, settle_account_id=cash.id,
                              items=[RequisitionItemInput(description="X", quantity=1, unit_cost=100)]),
            request=None, db=db, current_user=teacher,
        )
    assert exc.value.status_code == 422


async def test_create_rejects_unknown_account(db, org, teacher):
    cash = await _acct(db, org, "1000", "Cash", "asset")
    with pytest.raises(HTTPException) as exc:
        await create_requisition(
            RequisitionCreate(title="Bad", expense_account_id="nope", settle_account_id=cash.id,
                              items=[RequisitionItemInput(description="X", quantity=1, unit_cost=100)]),
            request=None, db=db, current_user=teacher,
        )
    assert exc.value.status_code == 404


# ── Approve == post to ledger (direction + SoD) ───────────────────────────────

async def test_approve_posts_dr_expense_cr_cash(db, org):
    requester = await _user(db, org, "requester")
    approver = await _user(db, org, "approver")
    exp = await _acct(db, org, "5200", "Teaching Supplies", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    r = await create_requisition(_payload(exp, cash), request=None, db=db, current_user=requester)
    approved = await approve_requisition(r.id, request=None, db=db, current_user=approver)
    assert approved.status == "approved"
    assert approved.approved_by == approver.id
    assert approved.journal_entry_id is not None
    assert await _balanced(db, approved.journal_entry_id)
    lines = await _lines(db, approved.journal_entry_id)
    exp_line = next(l for l in lines if l.account_id == exp.id)
    cash_line = next(l for l in lines if l.account_id == cash.id)
    assert float(exp_line.debit) == 13000.0 and float(exp_line.credit) == 0.0   # Dr Expense
    assert float(cash_line.credit) == 13000.0 and float(cash_line.debit) == 0.0  # Cr Cash


async def test_approve_segregation_of_duties_block(db, org):
    same = await _user(db, org, "solo")
    exp = await _acct(db, org, "5200", "Supplies", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    r = await create_requisition(_payload(exp, cash), request=None, db=db, current_user=same)
    with pytest.raises(HTTPException) as exc:
        await approve_requisition(r.id, request=None, db=db, current_user=same)
    assert exc.value.status_code == 403


async def test_approve_into_locked_period_rejected(db, org):
    requester = await _user(db, org, "req2")
    approver = await _user(db, org, "app2")
    exp = await _acct(db, org, "5200", "Supplies", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    r = await create_requisition(_payload(exp, cash), request=None, db=db, current_user=requester)
    await _lock_all_periods(db, org)
    with pytest.raises(HTTPException) as exc:
        await approve_requisition(r.id, request=None, db=db, current_user=approver)
    assert exc.value.status_code == 409
    still = (await db.execute(select(Requisition).where(Requisition.id == r.id))).scalar_one()
    assert still.status == "draft" and still.journal_entry_id is None


async def test_approve_twice_rejected(db, org):
    requester = await _user(db, org, "req3")
    approver = await _user(db, org, "app3")
    exp = await _acct(db, org, "5200", "Supplies", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    r = await create_requisition(_payload(exp, cash), request=None, db=db, current_user=requester)
    await approve_requisition(r.id, request=None, db=db, current_user=approver)
    with pytest.raises(HTTPException) as exc:
        await approve_requisition(r.id, request=None, db=db, current_user=approver)
    assert exc.value.status_code == 409


# ── Reject / Void / Delete ────────────────────────────────────────────────────

async def test_reject_draft_then_not_again(db, org):
    requester = await _user(db, org, "req4")
    approver = await _user(db, org, "app4")
    exp = await _acct(db, org, "5200", "Supplies", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    r = await create_requisition(_payload(exp, cash), request=None, db=db, current_user=requester)
    rejected = await reject_requisition(r.id, request=None, db=db, current_user=approver)
    assert rejected.status == "rejected"
    # can't reject a non-draft
    with pytest.raises(HTTPException) as exc:
        await reject_requisition(r.id, request=None, db=db, current_user=approver)
    assert exc.value.status_code == 409


async def test_void_reverses_approved(db, org):
    requester = await _user(db, org, "req5")
    approver = await _user(db, org, "app5")
    exp = await _acct(db, org, "5200", "Supplies", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    r = await create_requisition(_payload(exp, cash), request=None, db=db, current_user=requester)
    approved = await approve_requisition(r.id, request=None, db=db, current_user=approver)
    voided = await void_requisition(r.id, request=None, db=db, current_user=approver)
    assert voided.status == "void"
    orig = (await db.execute(select(JournalEntry).where(JournalEntry.id == approved.journal_entry_id))).scalar_one()
    assert orig.reversed_by_id is not None


async def test_void_requires_approved(db, org):
    requester = await _user(db, org, "req6")
    exp = await _acct(db, org, "5200", "Supplies", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    r = await create_requisition(_payload(exp, cash), request=None, db=db, current_user=requester)
    with pytest.raises(HTTPException) as exc:
        await void_requisition(r.id, request=None, db=db, current_user=requester)
    assert exc.value.status_code == 409       # draft can't be voided (delete/reject it)


async def test_delete_draft_ok_but_approved_blocked(db, org):
    requester = await _user(db, org, "req7")
    approver = await _user(db, org, "app7")
    exp = await _acct(db, org, "5200", "Supplies", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    r1 = await create_requisition(_payload(exp, cash), request=None, db=db, current_user=requester)
    await delete_requisition(r1.id, db=db, current_user=requester)
    listed = await list_requisitions(status=None, department=None, db=db, current_user=requester)
    assert all(x.id != r1.id for x in listed)
    r2 = await create_requisition(_payload(exp, cash), request=None, db=db, current_user=requester)
    await approve_requisition(r2.id, request=None, db=db, current_user=approver)
    with pytest.raises(HTTPException) as exc:
        await delete_requisition(r2.id, db=db, current_user=requester)
    assert exc.value.status_code == 409


async def test_list_filters_by_status(db, org, teacher):
    exp = await _acct(db, org, "5200", "Supplies", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    await create_requisition(_payload(exp, cash, title="D1"), request=None, db=db, current_user=teacher)
    drafts = await list_requisitions(status="draft", department=None, db=db, current_user=teacher)
    assert all(x.status == "draft" for x in drafts) and len(drafts) >= 1


# ── RBAC ──────────────────────────────────────────────────────────────────────

async def test_requisition_rbac(db, org):
    # Raise (draft) = payments:write; approve/reject/void (post) = payments:post.
    manager = await _preset_user(db, org, "manager")
    assert manager.has_permission("payments:write")
    assert not manager.has_permission("payments:post")
    accountant = await _preset_user(db, org, "accountant")
    assert accountant.has_permission("payments:write") and accountant.has_permission("payments:post")
    for slug in ("teacher", "parent", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("payments:write")
        assert not u.has_permission("payments:post")
