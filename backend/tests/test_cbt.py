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
    CBTExam, CBTQuestion, ExamStatus, QuestionType,
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


async def _exam(db, org, teacher, status=ExamStatus.PUBLISHED):
    e = CBTExam(
        id=str(uuid.uuid4()), title="Quiz", status=status, total_points=1.0,
        duration_minutes=60, created_by=teacher.id, org_id=org.id,
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
    school:write — students must never receive the answer key."""
    exam = await _exam(db, org, teacher)
    await _question(db, org, exam, answer="secret")
    await db.refresh(teacher, attribute_names=["roles"])  # empty roles → not a writer
    out = await list_questions(exam_id=exam.id, include_answers=True, db=db, current_user=teacher)
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
