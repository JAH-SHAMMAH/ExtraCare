"""
CBT (exams / questions / attempts) coverage — academic integrity + isolation.

Direct handler-call style (see conftest). Covers the success paths (auto-grade)
and the security/forbidden paths: answer-key never leaks to non-writers, closed
exams reject attempts, cross-tenant exams 404.
"""

import uuid

import pytest
from fastapi import HTTPException

from app.models.organization import Organization, IndustryType
from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import (
    CBTExam, CBTQuestion, ExamStatus, QuestionType, SchoolClass, Student,
)
from app.routers.modules.cbt import (
    get_exam, list_questions, start_attempt, submit_attempt,
)
from app.schemas.school_experience import AttemptSubmit, AttemptAnswerInput

pytestmark = pytest.mark.asyncio


async def _staff(db, org) -> User:
    """A role-loaded staff user (school:read/write) for staff-assisted attempt
    starts — the bare `teacher` fixture is intentionally permission-less."""
    u = User(id=str(uuid.uuid4()), email=f"staff-{uuid.uuid4().hex[:6]}@example.com",
             full_name="Staff", status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="teacher", slug=f"t-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["teacher"]), org_id=org.id, is_system=False)
    u.roles = [role]
    db.add_all([role, u])
    await db.flush()
    return u


async def _class(db, org) -> SchoolClass:
    c = SchoolClass(id=str(uuid.uuid4()), name=f"JSS{uuid.uuid4().hex[:3]}", level="Secondary",
                    org_id=org.id)
    db.add(c)
    await db.flush()
    return c


async def _sitting_student(db, org, class_id: str | None = None) -> User:
    """A user with the real STUDENT preset (school:cbt:sit, never school:write or
    school:cbt:manage) — the actual threat model for the answer-key check.

    Pass `class_id` to also create the linked Student record, which is what makes
    the account able to reach an exam at all (the sit path resolves the caller's
    class to check the exam is theirs)."""
    email = f"pupil-{uuid.uuid4().hex[:6]}@example.com"
    u = User(id=str(uuid.uuid4()), email=email,
             full_name="Pupil", status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="student", slug=f"s-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["student"]), org_id=org.id, is_system=False)
    u.roles = [role]
    db.add_all([role, u])
    if class_id:
        db.add(Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:5]}",
                       first_name="P", last_name="Q", email=email, user_id=u.id,
                       class_id=class_id, org_id=org.id))
    await db.flush()
    return u


async def _exam(db, org, teacher, status=ExamStatus.PUBLISHED, class_id=None):
    e = CBTExam(
        id=str(uuid.uuid4()), title="Quiz", status=status, total_points=1.0,
        duration_minutes=60, created_by=teacher.id, class_id=class_id, org_id=org.id,
    )
    db.add(e)
    await db.flush()
    return e


async def _question(db, org, exam, answer="4"):
    q = CBTQuestion(
        id=str(uuid.uuid4()), exam_id=exam.id, question_text="2+2?",
        question_type=QuestionType.MCQ, correct_answer=answer, points=1.0,
        position=0, org_id=org.id,
    )
    db.add(q)
    await db.flush()
    return q


async def test_attempt_autogrades_correct_answer(db, org, teacher, student):
    staff = await _staff(db, org)
    exam = await _exam(db, org, teacher)
    q = await _question(db, org, exam, answer="4")
    started = await start_attempt(exam_id=exam.id, student_id=student.id, db=db, current_user=staff)
    res = await submit_attempt(
        attempt_id=started["id"],
        payload=AttemptSubmit(answers=[AttemptAnswerInput(question_id=q.id, answer_text="4")]),
        db=db, current_user=staff,
    )
    assert res["score"] == 1.0


async def test_attempt_autogrades_wrong_answer_zero(db, org, teacher, student):
    staff = await _staff(db, org)
    exam = await _exam(db, org, teacher)
    q = await _question(db, org, exam, answer="4")
    started = await start_attempt(exam_id=exam.id, student_id=student.id, db=db, current_user=staff)
    res = await submit_attempt(
        attempt_id=started["id"],
        payload=AttemptSubmit(answers=[AttemptAnswerInput(question_id=q.id, answer_text="5")]),
        db=db, current_user=staff,
    )
    assert res["score"] == 0.0


async def test_attempt_blocked_when_exam_not_live(db, org, teacher, student):
    staff = await _staff(db, org)
    exam = await _exam(db, org, teacher, status=ExamStatus.DRAFT)
    with pytest.raises(HTTPException) as ei:
        await start_attempt(exam_id=exam.id, student_id=student.id, db=db, current_user=staff)
    assert ei.value.status_code == 400


async def test_questions_hide_correct_answer_from_non_writers(db, org, teacher):
    """Security: include_answers=true must be ignored for callers lacking
    school:write / school:cbt:manage — students must never receive the answer key.

    Uses a real STUDENT-preset user. This previously leaned on the `teacher`
    fixture being permission-less, which made it pass for the wrong reason: a real
    teacher holds school:cbt:manage and is *supposed* to see the answer key (they
    author the bank). The pupil is the caller the check actually exists to stop.
    """
    cls = await _class(db, org)
    exam = await _exam(db, org, teacher, class_id=cls.id)
    await _question(db, org, exam, answer="secret")
    pupil = await _sitting_student(db, org, class_id=cls.id)  # in the exam's class
    out = await list_questions(exam_id=exam.id, include_answers=True, db=db, current_user=pupil)
    assert out["items"]
    assert "correct_answer" not in out["items"][0]


async def test_get_exam_cross_tenant_404(db, org, teacher):
    other = Organization(
        id=str(uuid.uuid4()), name="Other", slug=f"other-{uuid.uuid4().hex[:8]}",
        industry=IndustryType.SCHOOL, modules_enabled=["school"],
    )
    db.add(other)
    await db.flush()
    foreign = CBTExam(
        id=str(uuid.uuid4()), title="Foreign", status=ExamStatus.PUBLISHED,
        total_points=1.0, duration_minutes=60, created_by=teacher.id, org_id=other.id,
    )
    db.add(foreign)
    await db.flush()
    with pytest.raises(HTTPException) as ei:
        await get_exam(exam_id=foreign.id, db=db, current_user=teacher)
    assert ei.value.status_code == 404
