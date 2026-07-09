"""CBT delivery correctness: per-student question shuffle + resolved pass mark.

Shuffle is applied (seeded per student, stable) only for the sitting student;
staff see the canonical position order. Pass mark resolves exam -> org default ->
50%, is recomputed each read, and drives per-attempt `passed` + the pass rate.
"""
from __future__ import annotations

import random
import uuid

import pytest
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import (
    CBTExam, CBTQuestion, CBTAttempt, CBTSettings,
    ExamStatus, QuestionType, AttemptStatus, Student,
)
from app.routers.modules.cbt import list_questions, exam_results

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


async def _exam(db, org, staff, *, shuffle=False, pass_percentage=None, total_points=2) -> CBTExam:
    exam = CBTExam(id=str(uuid.uuid4()), title="Quiz", created_by=staff.id, org_id=org.id,
                   status=ExamStatus.PUBLISHED, total_points=total_points,
                   shuffle_questions=shuffle, pass_percentage=pass_percentage)
    db.add(exam)
    await db.commit()
    return exam


async def _questions(db, org, exam, n=6):
    qs = []
    for i in range(n):
        q = CBTQuestion(id=str(uuid.uuid4()), exam_id=exam.id, question_text=f"Q{i}",
                        question_type=QuestionType.MCQ, correct_answer="a", points=1.0,
                        position=i, org_id=org.id)
        qs.append(q)
    db.add_all(qs)
    await db.commit()
    return qs  # in position order


# ── Shuffle ───────────────────────────────────────────────────────────────────────

async def test_student_shuffle_is_seeded_and_stable(db, org):
    staff = await _staff(db, org)
    stu, stu_user = await _linked_student(db, org)
    exam = await _exam(db, org, staff, shuffle=True)
    qs = await _questions(db, org, exam)

    expected = [q.id for q in qs]
    random.Random(f"{stu.id}:{exam.id}").shuffle(expected)

    res1 = await list_questions(exam.id, include_answers=False, db=db, current_user=stu_user)
    res2 = await list_questions(exam.id, include_answers=False, db=db, current_user=stu_user)
    got1 = [i["id"] for i in res1["items"]]
    got2 = [i["id"] for i in res2["items"]]
    assert got1 == expected            # applied with the per-student seed
    assert got1 == got2                # stable across reloads
    assert set(got1) == {q.id for q in qs}  # same set, just reordered


async def test_staff_see_canonical_order(db, org):
    staff = await _staff(db, org)
    exam = await _exam(db, org, staff, shuffle=True)
    qs = await _questions(db, org, exam)
    res = await list_questions(exam.id, include_answers=False, db=db, current_user=staff)
    assert [i["id"] for i in res["items"]] == [q.id for q in qs]  # position order


async def test_no_shuffle_keeps_position_order_for_student(db, org):
    staff = await _staff(db, org)
    stu, stu_user = await _linked_student(db, org)
    exam = await _exam(db, org, staff, shuffle=False)
    qs = await _questions(db, org, exam)
    res = await list_questions(exam.id, include_answers=False, db=db, current_user=stu_user)
    assert [i["id"] for i in res["items"]] == [q.id for q in qs]


# ── Pass mark ─────────────────────────────────────────────────────────────────────

async def _attempt(db, org, exam, student_id, score):
    a = CBTAttempt(id=str(uuid.uuid4()), exam_id=exam.id, student_id=student_id,
                   score=score, max_score=exam.total_points, status=AttemptStatus.GRADED, org_id=org.id)
    db.add(a)
    await db.commit()
    return a


async def test_pass_uses_exam_mark_and_recomputes(db, org):
    staff = await _staff(db, org)
    stu = (await _linked_student(db, org))[0]
    exam = await _exam(db, org, staff, pass_percentage=60, total_points=2)
    await _attempt(db, org, exam, stu.id, score=1)  # 50%

    res = await exam_results(exam.id, db=db, current_user=staff)
    assert res["exam"]["pass_percentage"] == 60
    assert res["attempts"][0]["passed"] is False and res["stats"]["pass_rate"] == 0

    # lower the mark -> recompute -> now a pass (results not published, so retroactive)
    exam.pass_percentage = 40
    await db.commit()
    res2 = await exam_results(exam.id, db=db, current_user=staff)
    assert res2["exam"]["pass_percentage"] == 40
    assert res2["attempts"][0]["passed"] is True and res2["stats"]["pass_rate"] == 100


async def test_pass_falls_back_to_org_default(db, org):
    staff = await _staff(db, org)
    stu = (await _linked_student(db, org))[0]
    db.add(CBTSettings(org_id=org.id, default_duration_minutes=60, default_pass_percentage=40, shuffle_default=False))
    exam = await _exam(db, org, staff, pass_percentage=None, total_points=2)
    await _attempt(db, org, exam, stu.id, score=1)  # 50% >= 40 -> pass
    await db.commit()
    res = await exam_results(exam.id, db=db, current_user=staff)
    assert res["exam"]["pass_percentage"] == 40 and res["attempts"][0]["passed"] is True


async def test_pass_defaults_to_50_when_unset(db, org):
    staff = await _staff(db, org)
    stu = (await _linked_student(db, org))[0]
    exam = await _exam(db, org, staff, pass_percentage=None, total_points=2)
    await _attempt(db, org, exam, stu.id, score=1)  # exactly 50% -> pass (>= boundary)
    res = await exam_results(exam.id, db=db, current_user=staff)
    assert res["exam"]["pass_percentage"] == 50 and res["attempts"][0]["passed"] is True
