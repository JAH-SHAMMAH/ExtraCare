"""CBT timer enforcement + attempt-limit.

Attempt cap (max_attempts; 0 = unlimited), deadline exposure, and the late-submit
policy: on-time (not flagged), late-but-accepted (submitted_late), egregiously
late (>2x duration past deadline -> 409 attempt_expired). Structured error codes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import CBTExam, CBTAttempt, ExamStatus, AttemptStatus, Student
from app.routers.modules.cbt import start_attempt, submit_attempt
from app.schemas.school_experience import AttemptSubmit

pytestmark = pytest.mark.asyncio


async def _staff(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"staff-{uuid.uuid4().hex[:6]}@example.com",
             full_name="Staff", status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="manager", slug=f"m-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["manager"]), org_id=org.id, is_system=False)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _student(db, org) -> Student:
    s = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:6]}",
                first_name="S", last_name="X", org_id=org.id)
    db.add(s)
    await db.commit()
    return s


async def _exam(db, org, created_by, *, duration=60, max_attempts=1) -> CBTExam:
    exam = CBTExam(id=str(uuid.uuid4()), title="Quiz", created_by=created_by, org_id=org.id,
                   status=ExamStatus.PUBLISHED, total_points=2, duration_minutes=duration,
                   max_attempts=max_attempts)  # PUBLISHED + no window -> live
    db.add(exam)
    await db.commit()
    return exam


def _attempt(exam, student_id, org, *, started_at, status=AttemptStatus.IN_PROGRESS) -> CBTAttempt:
    return CBTAttempt(id=str(uuid.uuid4()), exam_id=exam.id, student_id=student_id, max_score=2,
                      status=status, started_at=started_at, org_id=org.id)


# ── Attempt limit ─────────────────────────────────────────────────────────────────

async def test_attempt_limit_blocks_second_start(db, org):
    staff, stu = await _staff(db, org), await _student(db, org)
    exam = await _exam(db, org, staff.id, max_attempts=1)
    db.add(_attempt(exam, stu.id, org, started_at=datetime.now(timezone.utc), status=AttemptStatus.GRADED))
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await start_attempt(exam.id, student_id=stu.id, db=db, current_user=staff)
    assert exc.value.status_code == 409 and exc.value.detail["code"] == "attempt_limit_reached"


async def test_attempt_limit_allows_up_to_cap(db, org):
    staff, stu = await _staff(db, org), await _student(db, org)
    exam = await _exam(db, org, staff.id, max_attempts=2)
    db.add(_attempt(exam, stu.id, org, started_at=datetime.now(timezone.utc), status=AttemptStatus.GRADED))
    await db.commit()
    # one completed, cap 2 -> a second start succeeds
    res = await start_attempt(exam.id, student_id=stu.id, db=db, current_user=staff)
    assert res["status"] == "in_progress"


async def test_unlimited_when_zero(db, org):
    staff, stu = await _staff(db, org), await _student(db, org)
    exam = await _exam(db, org, staff.id, max_attempts=0)
    for _ in range(3):
        db.add(_attempt(exam, stu.id, org, started_at=datetime.now(timezone.utc), status=AttemptStatus.GRADED))
    await db.commit()
    res = await start_attempt(exam.id, student_id=stu.id, db=db, current_user=staff)
    assert res["status"] == "in_progress"


async def test_inprogress_resume_not_blocked(db, org):
    staff, stu = await _staff(db, org), await _student(db, org)
    exam = await _exam(db, org, staff.id, max_attempts=1)
    att = _attempt(exam, stu.id, org, started_at=datetime.now(timezone.utc))
    db.add(att)
    await db.commit()
    # resuming the in-progress attempt returns it, not a limit error
    res = await start_attempt(exam.id, student_id=stu.id, db=db, current_user=staff)
    assert res["id"] == att.id


# ── Deadline ──────────────────────────────────────────────────────────────────────

async def test_start_response_includes_deadline(db, org):
    staff, stu = await _staff(db, org), await _student(db, org)
    exam = await _exam(db, org, staff.id, duration=60)
    res = await start_attempt(exam.id, student_id=stu.id, db=db, current_user=staff)
    assert res["deadline"] is not None and res["deadline"] > datetime.now(timezone.utc)


# ── Timer / late policy ───────────────────────────────────────────────────────────

async def _submit(db, actor, att):
    return await submit_attempt(att.id, AttemptSubmit(answers=[]), db=db, current_user=actor)


async def test_submit_on_time_not_flagged(db, org):
    staff, stu = await _staff(db, org), await _student(db, org)
    exam = await _exam(db, org, staff.id, duration=60)
    att = _attempt(exam, stu.id, org, started_at=datetime.now(timezone.utc))
    db.add(att)
    await db.commit()
    res = await _submit(db, staff, att)
    assert res["submitted_late"] is False


async def test_submit_late_accepted_and_flagged(db, org):
    staff, stu = await _staff(db, org), await _student(db, org)
    exam = await _exam(db, org, staff.id, duration=60)
    # started 90 min ago -> deadline 30 min ago -> late but within 2x window
    att = _attempt(exam, stu.id, org, started_at=datetime.now(timezone.utc) - timedelta(minutes=90))
    db.add(att)
    await db.commit()
    res = await _submit(db, staff, att)
    assert res["submitted_late"] is True and res["status"] == "graded"


async def test_submit_egregiously_late_rejected(db, org):
    staff, stu = await _staff(db, org), await _student(db, org)
    exam = await _exam(db, org, staff.id, duration=60)
    # started 200 min ago -> deadline 140 min ago -> past deadline + 2x60 -> reject
    att = _attempt(exam, stu.id, org, started_at=datetime.now(timezone.utc) - timedelta(minutes=200))
    db.add(att)
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await _submit(db, staff, att)
    assert exc.value.status_code == 409 and exc.value.detail["code"] == "attempt_expired"
