"""Tests for Finance: Manage Discounts (fee discounts / scholarships / waivers).

The "Both" design: approving a discount reduces the student's fee record (what
parents see) AND posts a ledger contra Dr Fee Discounts / Cr Accounts Receivable.
These prove:
  • create computes the amount (fixed or % of total fee); draft applies nothing
  • over-discount (> outstanding) is rejected (422)
  • approve updates the fee record (discount_amount ↑, outstanding ↓) AND posts a
    balanced contra to the ledger
  • two-person control (approver ≠ proposer → 403)
  • void reverses BOTH sides (ledger reversed, fee-record balance restored)
  • reject/delete rules; RBAC — parents (payments:read) can't grant or list
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.payment import StudentFeeRecord
from app.models.modules.finance import LedgerAccount, JournalLine, FeeDiscount
from app.routers.modules.finance import (
    create_discount, approve_discount, reject_discount, void_discount,
    delete_discount, list_discounts,
    FEE_DISCOUNT_ACCOUNT_CODE, RECEIVABLE_ACCOUNT_CODE,
)
from app.schemas.finance import DiscountCreate


pytestmark = pytest.mark.asyncio


async def _fee_record(db, org, student, total, paid) -> StudentFeeRecord:
    fr = StudentFeeRecord(
        id=str(uuid.uuid4()), org_id=org.id, student_id=student.id, term="term1_2026", session_year="2026",
        total_fee=Decimal(total), paid_amount=Decimal(paid),
        outstanding_balance=Decimal(total) - Decimal(paid), discount_amount=Decimal(0),
        payment_status="partial" if paid else "unpaid",
    )
    db.add(fr)
    await db.commit()
    return fr


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


async def _reload_fr(db, fr_id) -> StudentFeeRecord:
    return (await db.execute(select(StudentFeeRecord).where(StudentFeeRecord.id == fr_id))).scalar_one()


async def _balanced(db, entry_id) -> bool:
    lines = (await db.execute(select(JournalLine).where(JournalLine.entry_id == entry_id))).scalars().all()
    return len(lines) >= 2 and sum(float(l.debit) for l in lines) == sum(float(l.credit) for l in lines)


# ── Create (draft) ────────────────────────────────────────────────────────────

async def test_create_fixed_is_draft_applies_nothing(db, org, teacher, student):
    fr = await _fee_record(db, org, student, 250000, 50000)   # outstanding 200000
    d = await create_discount(
        DiscountCreate(student_id=student.id, discount_type="fixed", value=50000, reason="Sibling"),
        request=None, db=db, current_user=teacher,
    )
    assert d.status == "draft" and d.amount == 50000.0 and d.journal_entry_id is None
    assert d.student_name == "Ada Okafor"
    # fee record untouched until approval
    fr2 = await _reload_fr(db, fr.id)
    assert float(fr2.discount_amount) == 0.0 and float(fr2.outstanding_balance) == 200000.0


async def test_create_percent_computes_amount(db, org, teacher, student):
    await _fee_record(db, org, student, 250000, 0)
    d = await create_discount(
        DiscountCreate(student_id=student.id, discount_type="percent", value=20, reason="Scholarship"),
        request=None, db=db, current_user=teacher,
    )
    assert d.amount == 50000.0     # 20% of 250000


async def test_create_exceeding_outstanding_rejected(db, org, teacher, student):
    await _fee_record(db, org, student, 250000, 50000)   # outstanding 200000
    with pytest.raises(HTTPException) as exc:
        await create_discount(
            DiscountCreate(student_id=student.id, discount_type="fixed", value=300000),
            request=None, db=db, current_user=teacher,
        )
    assert exc.value.status_code == 422


async def test_create_no_fee_record_rejected(db, org, teacher, student):
    with pytest.raises(HTTPException) as exc:
        await create_discount(
            DiscountCreate(student_id=student.id, discount_type="fixed", value=1000),
            request=None, db=db, current_user=teacher,
        )
    assert exc.value.status_code == 422


async def test_create_unknown_student_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_discount(
            DiscountCreate(student_id="nope", discount_type="fixed", value=1000),
            request=None, db=db, current_user=teacher,
        )
    assert exc.value.status_code == 404


# ── Approve == apply both sides ───────────────────────────────────────────────

async def test_approve_updates_fee_record_and_posts_contra(db, org, student):
    proposer = await _user(db, org, "proposer")
    approver = await _user(db, org, "approver")
    fr = await _fee_record(db, org, student, 250000, 50000)   # outstanding 200000
    d = await create_discount(
        DiscountCreate(student_id=student.id, discount_type="fixed", value=50000, reason="Sibling"),
        request=None, db=db, current_user=proposer,
    )
    approved = await approve_discount(d.id, request=None, db=db, current_user=approver)
    assert approved.status == "approved" and approved.approved_by == approver.id and approved.journal_entry_id
    # Fee-record side (what parents see)
    fr2 = await _reload_fr(db, fr.id)
    assert float(fr2.discount_amount) == 50000.0
    assert float(fr2.outstanding_balance) == 150000.0        # 250000 − 50000 paid − 50000 discount
    assert fr2.payment_status == "partial"
    # Ledger side: balanced Dr Fee Discounts (5900) / Cr Receivable (1100)
    assert await _balanced(db, approved.journal_entry_id)
    disc_acct = (await db.execute(select(LedgerAccount).where(
        LedgerAccount.org_id == org.id, LedgerAccount.code == FEE_DISCOUNT_ACCOUNT_CODE))).scalar_one()
    recv_acct = (await db.execute(select(LedgerAccount).where(
        LedgerAccount.org_id == org.id, LedgerAccount.code == RECEIVABLE_ACCOUNT_CODE))).scalar_one()
    assert disc_acct.type == "expense" and recv_acct.type == "asset"
    lines = (await db.execute(select(JournalLine).where(JournalLine.entry_id == approved.journal_entry_id))).scalars().all()
    dr = next(l for l in lines if l.account_id == disc_acct.id)
    cr = next(l for l in lines if l.account_id == recv_acct.id)
    assert float(dr.debit) == 50000.0 and float(cr.credit) == 50000.0


async def test_discount_covering_balance_marks_paid(db, org, student):
    proposer = await _user(db, org, "p2")
    approver = await _user(db, org, "a2")
    fr = await _fee_record(db, org, student, 100000, 0)       # outstanding 100000
    d = await create_discount(DiscountCreate(student_id=student.id, discount_type="fixed", value=100000, reason="Full waiver"),
                              request=None, db=db, current_user=proposer)
    await approve_discount(d.id, request=None, db=db, current_user=approver)
    fr2 = await _reload_fr(db, fr.id)
    assert float(fr2.outstanding_balance) == 0.0 and fr2.is_paid is True and fr2.payment_status == "paid"


async def test_approve_segregation_of_duties_block(db, org, student):
    same = await _user(db, org, "solo")
    await _fee_record(db, org, student, 250000, 0)
    d = await create_discount(DiscountCreate(student_id=student.id, discount_type="fixed", value=10000),
                              request=None, db=db, current_user=same)
    with pytest.raises(HTTPException) as exc:
        await approve_discount(d.id, request=None, db=db, current_user=same)
    assert exc.value.status_code == 403


async def test_approve_twice_rejected(db, org, student):
    proposer = await _user(db, org, "p3")
    approver = await _user(db, org, "a3")
    await _fee_record(db, org, student, 250000, 0)
    d = await create_discount(DiscountCreate(student_id=student.id, discount_type="fixed", value=10000),
                              request=None, db=db, current_user=proposer)
    await approve_discount(d.id, request=None, db=db, current_user=approver)
    with pytest.raises(HTTPException) as exc:
        await approve_discount(d.id, request=None, db=db, current_user=approver)
    assert exc.value.status_code == 409


# ── Void reverses both ────────────────────────────────────────────────────────

async def test_void_reverses_fee_record_and_ledger(db, org, student):
    proposer = await _user(db, org, "p4")
    approver = await _user(db, org, "a4")
    fr = await _fee_record(db, org, student, 250000, 50000)
    d = await create_discount(DiscountCreate(student_id=student.id, discount_type="fixed", value=50000),
                              request=None, db=db, current_user=proposer)
    approved = await approve_discount(d.id, request=None, db=db, current_user=approver)
    voided = await void_discount(d.id, request=None, db=db, current_user=approver)
    assert voided.status == "void"
    # fee record restored
    fr2 = await _reload_fr(db, fr.id)
    assert float(fr2.discount_amount) == 0.0 and float(fr2.outstanding_balance) == 200000.0
    # ledger reversed
    from app.models.modules.finance import JournalEntry
    orig = (await db.execute(select(JournalEntry).where(JournalEntry.id == approved.journal_entry_id))).scalar_one()
    assert orig.reversed_by_id is not None


async def test_void_requires_approved(db, org, teacher, student):
    await _fee_record(db, org, student, 250000, 0)
    d = await create_discount(DiscountCreate(student_id=student.id, discount_type="fixed", value=10000),
                              request=None, db=db, current_user=teacher)
    with pytest.raises(HTTPException) as exc:
        await void_discount(d.id, request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 409


# ── Reject / Delete ───────────────────────────────────────────────────────────

async def test_reject_then_delete(db, org, teacher, student):
    await _fee_record(db, org, student, 250000, 0)
    d = await create_discount(DiscountCreate(student_id=student.id, discount_type="fixed", value=10000),
                              request=None, db=db, current_user=teacher)
    rejected = await reject_discount(d.id, request=None, db=db, current_user=teacher)
    assert rejected.status == "rejected"
    await delete_discount(d.id, db=db, current_user=teacher)
    assert all(x.id != d.id for x in await list_discounts(status=None, student_id=None, db=db, current_user=teacher))


async def test_delete_approved_blocked(db, org, student):
    proposer = await _user(db, org, "p5")
    approver = await _user(db, org, "a5")
    await _fee_record(db, org, student, 250000, 0)
    d = await create_discount(DiscountCreate(student_id=student.id, discount_type="fixed", value=10000),
                              request=None, db=db, current_user=proposer)
    await approve_discount(d.id, request=None, db=db, current_user=approver)
    with pytest.raises(HTTPException) as exc:
        await delete_discount(d.id, db=db, current_user=proposer)
    assert exc.value.status_code == 409


# ── RBAC ──────────────────────────────────────────────────────────────────────

async def test_discount_rbac(db, org):
    # Propose/list = payments:write; approve/void = payments:post.
    # Parents hold payments:READ (own fees) but must NOT be able to grant or list.
    manager = await _preset_user(db, org, "manager")
    assert manager.has_permission("payments:write")
    accountant = await _preset_user(db, org, "accountant")
    assert accountant.has_permission("payments:write") and accountant.has_permission("payments:post")
    parent = await _preset_user(db, org, "parent")
    assert parent.has_permission("payments:read")          # sees own fees…
    assert not parent.has_permission("payments:write")     # …but can't grant or list discounts
    for slug in ("teacher", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("payments:write")
