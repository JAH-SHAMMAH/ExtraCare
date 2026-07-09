"""IDOR fix: CBT attempt endpoints are scoped to the caller.

A student (cbt:read/write, no school:read) may only start/submit/read/list their
OWN attempt; staff (school:read) keep org-wide access (incl. staff-assisted start).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import CBTExam, CBTAttempt, ExamStatus, AttemptStatus, Student
from app.routers.modules.cbt import start_attempt, submit_attempt, get_attempt, list_attempts
from app.schemas.school_experience import AttemptSubmit

pytestmark = pytest.mark.asyncio


async def _staff(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"staff-{uuid.uuid4().hex[:6]}@example.com",
             full_name="Staff", status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="manager", slug=f"manager-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["manager"]), org_id=org.id, is_system=False)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _student_role_user(db, org, email: str) -> User:
    role = Role(id=str(uuid.uuid4()), name="student", slug=f"student-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["student"]), org_id=org.id, is_system=False)
    u = User(id=str(uuid.uuid4()), email=email, full_name="S X", status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _linked_student(db, org):
    """A Student + a User linked by email (resolve_linked_student_id matches on email)."""
    email = f"stu-{uuid.uuid4().hex[:6]}@example.com"
    stu = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:6]}",
                  first_name="S", last_name="X", email=email, org_id=org.id)
    db.add(stu)
    await db.commit()
    return stu, await _student_role_user(db, org, email)


async def _live_exam(db, org, created_by) -> CBTExam:
    exam = CBTExam(id=str(uuid.uuid4()), title="Quiz", created_by=created_by, org_id=org.id,
                   status=ExamStatus.PUBLISHED, total_points=2)  # no window -> live
    db.add(exam)
    await db.commit()
    return exam


def _attempt(exam, student_id, org, status=AttemptStatus.IN_PROGRESS) -> CBTAttempt:
    return CBTAttempt(id=str(uuid.uuid4()), exam_id=exam.id, student_id=student_id,
                      max_score=2, status=status, org_id=org.id)


# ── start ────────────────────────────────────────────────────────────────────────

async def test_student_start_is_forced_to_own_record(db, org):
    staff = await _staff(db, org)
    stu_a, user_a = await _linked_student(db, org)
    stu_b, _ = await _linked_student(db, org)
    exam = await _live_exam(db, org, staff.id)

    # user_a passes stu_b's id, but the attempt is created for stu_a (own), never stu_b
    res = await start_attempt(exam.id, student_id=stu_b.id, db=db, current_user=user_a)
    assert res["student_id"] == stu_a.id
    rows = (await db.execute(select(CBTAttempt).where(CBTAttempt.exam_id == exam.id))).scalars().all()
    assert len(rows) == 1 and rows[0].student_id == stu_a.id


async def test_student_without_linked_record_403(db, org):
    u = await _student_role_user(db, org, f"nolink-{uuid.uuid4().hex[:6]}@example.com")
    exam = await _live_exam(db, org, u.id)
    with pytest.raises(HTTPException) as exc:
        await start_attempt(exam.id, student_id=None, db=db, current_user=u)
    assert exc.value.status_code == 403


async def test_staff_start_requires_valid_student(db, org):
    staff = await _staff(db, org)
    exam = await _live_exam(db, org, staff.id)
    with pytest.raises(HTTPException) as e1:
        await start_attempt(exam.id, student_id=None, db=db, current_user=staff)
    assert e1.value.status_code == 422
    with pytest.raises(HTTPException) as e2:
        await start_attempt(exam.id, student_id=str(uuid.uuid4()), db=db, current_user=staff)
    assert e2.value.status_code == 404


# ── get / submit ──────────────────────────────────────────────────────────────────

async def test_student_cannot_get_or_submit_another_students_attempt(db, org):
    staff = await _staff(db, org)
    stu_a, user_a = await _linked_student(db, org)
    stu_b, _ = await _linked_student(db, org)
    exam = await _live_exam(db, org, staff.id)
    att_b = _attempt(exam, stu_b.id, org)
    db.add(att_b)
    await db.commit()

    with pytest.raises(HTTPException) as e_get:
        await get_attempt(att_b.id, db=db, current_user=user_a)
    assert e_get.value.status_code == 404
    with pytest.raises(HTTPException) as e_sub:
        await submit_attempt(att_b.id, AttemptSubmit(answers=[]), db=db, current_user=user_a)
    assert e_sub.value.status_code == 404

    # staff can read any attempt in the org
    assert (await get_attempt(att_b.id, db=db, current_user=staff))["id"] == att_b.id


# ── list ──────────────────────────────────────────────────────────────────────────

async def test_student_list_returns_only_own(db, org):
    staff = await _staff(db, org)
    stu_a, user_a = await _linked_student(db, org)
    stu_b, _ = await _linked_student(db, org)
    exam = await _live_exam(db, org, staff.id)
    db.add_all([_attempt(exam, stu_a.id, org, AttemptStatus.GRADED),
                _attempt(exam, stu_b.id, org, AttemptStatus.GRADED)])
    await db.commit()

    # even passing stu_b's id, a student only ever sees their own attempts
    student_view = await list_attempts(exam_id=None, student_id=stu_b.id, db=db, current_user=user_a)
    assert {i["student_id"] for i in student_view["items"]} == {stu_a.id}

    # staff see both
    staff_view = await list_attempts(exam_id=exam.id, student_id=None, db=db, current_user=staff)
    assert {stu_a.id, stu_b.id} <= {i["student_id"] for i in staff_view["items"]}
