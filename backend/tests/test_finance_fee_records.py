"""Tests for Finance: Fee Assignment (populate StudentFeeRecord).

This is the only write path to student fee records — the data that Manage
Discounts, parent Fee Management and the accountant summaries all read. Proves:
  • create sums the breakdown into total_fee and sets outstanding = total (unpaid)
  • duplicate (student, term, session) is rejected (409); empty breakdown → 422
  • update replaces the breakdown and recomputes total/outstanding, preserving
    any paid amount and approved discount
  • assign-class creates a record per student and SKIPS those already assigned
  • RBAC — assignment is payments:write; parents (payments:read) are excluded
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import Student
from app.models.payment import StudentFeeRecord
from app.routers.modules.finance import (
    create_fee_record, update_fee_record, delete_fee_record, list_fee_records, assign_class_fees,
    list_finance_classes,
)
from app.schemas.finance import FeeRecordCreate, FeeRecordUpdate, ClassFeeAssign


pytestmark = pytest.mark.asyncio


async def _student(db, org, cls, first, last) -> Student:
    s = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:5]}", first_name=first, last_name=last,
                email=f"{first.lower()}-{uuid.uuid4().hex[:4]}@example.com", class_id=cls.id, org_id=org.id)
    db.add(s)
    await db.commit()
    return s


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


async def _reload(db, fr_id) -> StudentFeeRecord:
    return (await db.execute(select(StudentFeeRecord).where(StudentFeeRecord.id == fr_id))).scalar_one()


# ── Create (per student) ──────────────────────────────────────────────────────

async def test_create_sums_total_and_sets_outstanding(db, org, teacher, student):
    fr = await create_fee_record(
        FeeRecordCreate(student_id=student.id, term="term1", session_year="2026", tuition_fee=180000, exam_fee=20000),
        request=None, db=db, current_user=teacher,
    )
    assert fr.total_fee == 200000.0
    assert fr.outstanding_balance == 200000.0
    assert fr.payment_status == "unpaid" and fr.is_paid is False
    assert fr.student_name == "Ada Okafor"


async def test_create_duplicate_term_rejected(db, org, teacher, student):
    await create_fee_record(FeeRecordCreate(student_id=student.id, term="term1", session_year="2026", tuition_fee=100000),
                            request=None, db=db, current_user=teacher)
    with pytest.raises(HTTPException) as exc:
        await create_fee_record(FeeRecordCreate(student_id=student.id, term="term1", session_year="2026", tuition_fee=50000),
                                request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 409
    # a different term is fine
    fr2 = await create_fee_record(FeeRecordCreate(student_id=student.id, term="term2", session_year="2026", tuition_fee=50000),
                                  request=None, db=db, current_user=teacher)
    assert fr2.total_fee == 50000.0


async def test_create_empty_breakdown_rejected(db, org, teacher, student):
    with pytest.raises(HTTPException) as exc:
        await create_fee_record(FeeRecordCreate(student_id=student.id, term="term1", session_year="2026"),
                                request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_create_unknown_student_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_fee_record(FeeRecordCreate(student_id="nope", term="term1", session_year="2026", tuition_fee=1000),
                                request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 404


# ── Update (recompute, preserve paid + discount) ──────────────────────────────

async def test_update_recomputes_and_preserves_paid_and_discount(db, org, teacher, student):
    fr = await create_fee_record(
        FeeRecordCreate(student_id=student.id, term="term1", session_year="2026", tuition_fee=200000),
        request=None, db=db, current_user=teacher,
    )
    # Simulate a payment + an approved discount already on the record.
    row = await _reload(db, fr.id)
    row.paid_amount = Decimal("50000")
    row.discount_amount = Decimal("30000")
    await db.commit()
    # Raise the fees; total + outstanding recompute, paid + discount preserved.
    updated = await update_fee_record(
        fr.id, FeeRecordUpdate(tuition_fee=250000, exam_fee=10000),
        request=None, db=db, current_user=teacher,
    )
    assert updated.total_fee == 260000.0
    assert updated.paid_amount == 50000.0 and updated.discount_amount == 30000.0
    assert updated.outstanding_balance == 180000.0     # 260000 − 50000 − 30000
    assert updated.payment_status == "partial"


async def test_delete_fee_record(db, org, teacher, student):
    fr = await create_fee_record(FeeRecordCreate(student_id=student.id, term="term1", session_year="2026", tuition_fee=1000),
                                 request=None, db=db, current_user=teacher)
    await delete_fee_record(fr.id, db=db, current_user=teacher)
    listed = await list_fee_records(student_id=None, term=None, session_year=None, db=db, current_user=teacher)
    assert all(x.id != fr.id for x in listed)


# ── Class bulk assign ─────────────────────────────────────────────────────────

async def test_assign_class_creates_per_student_and_skips_existing(db, org, teacher, school_class, student):
    # `student` (Ada) is already in school_class; add two more.
    await _student(db, org, school_class, "Bola", "Ade")
    await _student(db, org, school_class, "Chidi", "Eze")
    res = await assign_class_fees(
        ClassFeeAssign(class_id=school_class.id, term="term1", session_year="2026", tuition_fee=150000, exam_fee=15000),
        request=None, db=db, current_user=teacher,
    )
    assert res.total_students == 3
    assert res.created == 3 and res.skipped == 0
    assert all(r.total_fee == 165000.0 for r in res.records)
    # Running it again skips everyone (already assigned this term).
    res2 = await assign_class_fees(
        ClassFeeAssign(class_id=school_class.id, term="term1", session_year="2026", tuition_fee=150000),
        request=None, db=db, current_user=teacher,
    )
    assert res2.created == 0 and res2.skipped == 3


async def test_assign_class_unknown_class_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await assign_class_fees(ClassFeeAssign(class_id="nope", term="term1", session_year="2026", tuition_fee=1000),
                                request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 404


# ── Class dropdown (finance-gated class list) ─────────────────────────────────

async def test_list_finance_classes_with_counts(db, org, teacher, school_class, student):
    # `student` (Ada) is in school_class; add one more.
    await _student(db, org, school_class, "Bola", "Ade")
    classes = await list_finance_classes(db=db, current_user=teacher)
    ours = next(c for c in classes if c.id == school_class.id)
    assert ours.name == school_class.name
    assert ours.student_count == 2


# ── RBAC ──────────────────────────────────────────────────────────────────────

async def test_fee_assignment_rbac(db, org):
    # Assigning fees = payments:write. Parents hold payments:read (own fees) but
    # must NOT be able to assign fees.
    manager = await _preset_user(db, org, "manager")
    assert manager.has_permission("payments:write")
    parent = await _preset_user(db, org, "parent")
    assert parent.has_permission("payments:read")
    assert not parent.has_permission("payments:write")
    for slug in ("teacher", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("payments:write")
