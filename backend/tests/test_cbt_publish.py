"""CBT results distribution Phase 1: publish gate + frozen pass mark.

hold_results gates a student's view of their score until published; publishing
snapshots the resolved pass mark (frozen even if the live mark changes). Staff
always see results. Immediate (not-held) exams are unchanged.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import (
    CBTExam, CBTAttempt, CBTAnswer, CBTSettings, ExamStatus, AttemptStatus, Student,
)
from app.routers.modules.cbt import (
    publish_exam_results, unpublish_exam_results, get_attempt,
)

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


async def _linked_student(db, org):
    email = f"stu-{uuid.uuid4().hex[:6]}@example.com"
    stu = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:6]}",
                  first_name="S", last_name="X", email=email, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="student", slug=f"student-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["student"]), org_id=org.id, is_system=False)
    u = User(id=str(uuid.uuid4()), email=email, full_name="S X", status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([stu, role, u])
    await db.commit()
    return stu, u


async def _exam(db, org, staff, *, hold_results=False, pass_percentage=None) -> CBTExam:
    exam = CBTExam(id=str(uuid.uuid4()), title="Quiz", created_by=staff.id, org_id=org.id,
                   status=ExamStatus.PUBLISHED, total_points=2,
                   hold_results=hold_results, pass_percentage=pass_percentage)
    db.add(exam)
    await db.commit()
    return exam


async def _graded_attempt(db, org, exam, student_id):
    att = CBTAttempt(id=str(uuid.uuid4()), exam_id=exam.id, student_id=student_id, max_score=2, score=2,
                     status=AttemptStatus.GRADED, started_at=datetime.now(timezone.utc), org_id=org.id)
    ans = CBTAnswer(id=str(uuid.uuid4()), attempt_id=att.id, question_id=str(uuid.uuid4()),
                    answer_text="a", is_correct=True, points_awarded=2, org_id=org.id)
    db.add_all([att, ans])
    await db.commit()
    return att


# ── Publish snapshot / freeze ─────────────────────────────────────────────────────

async def test_publish_snapshots_and_freezes_pass_mark(db, org):
    staff = await _staff(db, org)
    exam = await _exam(db, org, staff, pass_percentage=60)
    res = await publish_exam_results(exam.id, request=None, db=db, current_user=staff)
    assert res["published"] is True and res["published_pass_percentage"] == 60

    row = (await db.execute(select(CBTExam).where(CBTExam.id == exam.id))).scalar_one()
    assert row.results_published_at is not None and row.results_published_by == staff.id
    # change the LIVE pass mark — the frozen published snapshot must not move
    row.pass_percentage = 40
    await db.commit()
    row2 = (await db.execute(select(CBTExam).where(CBTExam.id == exam.id))).scalar_one()
    assert row2.published_pass_percentage == 60


async def test_publish_resolves_pass_mark_from_org_default(db, org):
    staff = await _staff(db, org)
    db.add(CBTSettings(org_id=org.id, default_duration_minutes=60, default_pass_percentage=40, shuffle_default=False))
    exam = await _exam(db, org, staff, pass_percentage=None)
    await db.commit()
    res = await publish_exam_results(exam.id, request=None, db=db, current_user=staff)
    assert res["published_pass_percentage"] == 40


# ── The student gate ──────────────────────────────────────────────────────────────

async def test_held_results_hidden_from_student_until_published(db, org):
    staff = await _staff(db, org)
    stu, stu_user = await _linked_student(db, org)
    exam = await _exam(db, org, staff, hold_results=True)
    att = await _graded_attempt(db, org, exam, stu.id)

    # held + unpublished: the student sees a pending stub, no score/answers
    pending = await get_attempt(att.id, db=db, current_user=stu_user)
    assert pending.get("results_pending") is True and "score" not in pending and "answers" not in pending
    # staff always see the full result
    full_staff = await get_attempt(att.id, db=db, current_user=staff)
    assert full_staff["score"] == 2 and "answers" in full_staff

    # publish → the student now sees the full result
    await publish_exam_results(exam.id, request=None, db=db, current_user=staff)
    shown = await get_attempt(att.id, db=db, current_user=stu_user)
    assert shown.get("results_pending") is None and shown["score"] == 2 and "answers" in shown


async def test_not_held_results_visible_immediately(db, org):
    staff = await _staff(db, org)
    stu, stu_user = await _linked_student(db, org)
    exam = await _exam(db, org, staff, hold_results=False)
    att = await _graded_attempt(db, org, exam, stu.id)
    shown = await get_attempt(att.id, db=db, current_user=stu_user)
    assert shown.get("results_pending") is None and shown["score"] == 2


async def test_unpublish_retracts_student_visibility(db, org):
    staff = await _staff(db, org)
    stu, stu_user = await _linked_student(db, org)
    exam = await _exam(db, org, staff, hold_results=True)
    att = await _graded_attempt(db, org, exam, stu.id)

    await publish_exam_results(exam.id, request=None, db=db, current_user=staff)
    assert (await get_attempt(att.id, db=db, current_user=stu_user))["score"] == 2
    await unpublish_exam_results(exam.id, request=None, db=db, current_user=staff)
    assert (await get_attempt(att.id, db=db, current_user=stu_user)).get("results_pending") is True


# ── RBAC ──────────────────────────────────────────────────────────────────────────

async def test_publish_is_staff_write_only(db, org):
    admin = await _staff(db, org)  # manager preset
    assert admin.has_permission("school:write")
    _, stu_user = await _linked_student(db, org)
    assert not stu_user.has_permission("school:write")  # students can't publish
