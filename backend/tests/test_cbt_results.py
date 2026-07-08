"""Tests for CBT Phase B — Result Manager, Test Export, Test Remark.

Covers the subjective-grading gap: the auto-grader scores MCQ/true-false only, so
short/long answers land ungraded (points_awarded=None). Remark awards them and
re-totals the attempt.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import (
    CBTExam, CBTQuestion, CBTAttempt, CBTAnswer, ExamStatus, AttemptStatus, QuestionType,
)
from app.routers.modules.cbt import (
    exam_results, export_results, review_attempt, remark_attempt,
)
from app.schemas.school_experience import RemarkItem

pytestmark = pytest.mark.asyncio


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


async def _seed_exam_with_attempt(db, org, teacher, student):
    """Exam with an MCQ (auto-graded 1/1) + a short-answer (ungraded), total 3."""
    exam = CBTExam(id=str(uuid.uuid4()), title="Quiz 1", created_by=teacher.id, org_id=org.id,
                   status=ExamStatus.PUBLISHED, total_points=3)
    mcq = CBTQuestion(id=str(uuid.uuid4()), exam_id=exam.id, question_text="2+2?",
                      question_type=QuestionType.MCQ, correct_answer="a", points=1, org_id=org.id)
    short = CBTQuestion(id=str(uuid.uuid4()), exam_id=exam.id, question_text="Explain gravity.",
                        question_type=QuestionType.SHORT_ANSWER, points=2, org_id=org.id)
    attempt = CBTAttempt(id=str(uuid.uuid4()), exam_id=exam.id, student_id=student.id,
                         max_score=3, score=1, status=AttemptStatus.GRADED, org_id=org.id)
    ans_mcq = CBTAnswer(id=str(uuid.uuid4()), attempt_id=attempt.id, question_id=mcq.id,
                        answer_text="a", is_correct=True, points_awarded=1, org_id=org.id)
    ans_short = CBTAnswer(id=str(uuid.uuid4()), attempt_id=attempt.id, question_id=short.id,
                          answer_text="Mass attracts mass.", is_correct=None, points_awarded=None, org_id=org.id)
    db.add_all([exam, mcq, short, attempt, ans_mcq, ans_short])
    await db.commit()
    return exam, attempt, ans_short


# ── Result Manager ────────────────────────────────────────────────────────────

async def test_exam_results_and_stats(db, org, teacher, student):
    exam, attempt, _ = await _seed_exam_with_attempt(db, org, teacher, student)
    res = await exam_results(exam.id, db=db, current_user=teacher)
    assert res["exam"]["title"] == "Quiz 1" and res["exam"]["total_points"] == 3
    assert res["stats"]["attempts"] == 1 and res["stats"]["pending_review"] == 1
    row = res["attempts"][0]
    assert row["student_id"] == student.id and row["student_name"]
    assert row["score"] == 1 and row["max_score"] == 3 and row["needs_review"] is True


# ── Export ────────────────────────────────────────────────────────────────────

async def test_export_results_csv(db, org, teacher, student):
    exam, _, _ = await _seed_exam_with_attempt(db, org, teacher, student)
    res = await export_results(exam.id, db=db, current_user=teacher)
    body = res.body.decode("utf-8")
    assert res.media_type == "text/csv"
    assert "Student,Student ID,Score,Max,Percentage,Status,Submitted" in body
    assert student.id in body and ",1," in body and ",3," in body


# ── Review (staff sees correct answer + grading flag) ──────────────────────────

async def test_review_shows_correct_answer_and_grading_flag(db, org, teacher, student):
    exam, attempt, ans_short = await _seed_exam_with_attempt(db, org, teacher, student)
    res = await review_attempt(attempt.id, db=db, current_user=teacher)
    assert res["attempt"]["student_name"]
    short_row = next(r for r in res["answers"] if r["answer_id"] == ans_short.id)
    assert short_row["question_type"] == "short_answer"
    assert short_row["needs_grading"] is True and short_row["max_points"] == 2
    mcq_row = next(r for r in res["answers"] if r["answer_id"] != ans_short.id)
    assert mcq_row["correct_answer"] == "a" and mcq_row["needs_grading"] is False


# ── Remark (award subjective + re-total) ───────────────────────────────────────

async def test_remark_retotals_attempt(db, org, teacher, student):
    exam, attempt, ans_short = await _seed_exam_with_attempt(db, org, teacher, student)
    res = await remark_attempt(attempt.id, [RemarkItem(answer_id=ans_short.id, points_awarded=2)],
                               request=None, db=db, current_user=teacher)
    assert res["changed"] == 1 and res["score"] == 3  # 1 (mcq) + 2 (awarded)
    await db.refresh(attempt)
    assert attempt.score == 3
    # re-check: no more pending review
    after = await exam_results(exam.id, db=db, current_user=teacher)
    assert after["stats"]["pending_review"] == 0


async def test_remark_caps_at_question_max(db, org, teacher, student):
    exam, attempt, ans_short = await _seed_exam_with_attempt(db, org, teacher, student)
    # award 10 to a 2-point question -> capped at 2
    await remark_attempt(attempt.id, [RemarkItem(answer_id=ans_short.id, points_awarded=10)],
                         request=None, db=db, current_user=teacher)
    await db.refresh(attempt)
    assert attempt.score == 3  # 1 + capped 2


async def test_review_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await review_attempt(str(uuid.uuid4()), db=db, current_user=teacher)
    assert exc.value.status_code == 404


# ── RBAC: staff-only (students hold cbt:* to sit, not school:* to see results) ──

async def test_results_rbac_excludes_students(db, org):
    for slug in ("manager", "teacher"):
        u = await _preset_user(db, org, slug)
        assert u.has_permission("school:read") and u.has_permission("school:write")
    student = await _preset_user(db, org, "student")
    assert not student.has_permission("school:read") and not student.has_permission("school:write")
