"""Student exam portal extras: self-made practice papers, progress, and exam-room
integrity signals.

Everything here is scoped to the signed-in student's own linked Student record.
Practice papers are real CBTExam rows (exam_type="practice", created_by = the
student) so the existing start → sit → submit → grade flow is reused unchanged;
they are filtered out of every staff list, never reach the gradebook (no term),
and only their creator can open them.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import PermissionChecker
from app.core.school_identity import resolve_linked_student_id
from app.core.tenant import require_role_module
from app.database import get_db
from app.deps import get_current_active_user
from app.models.modules.school import (
    AttemptStatus, CBTAnswer, CBTAttempt, CBTExam, CBTQuestion, ExamStatus,
    QuestionBankItem, QuestionType, SchoolClass, Student, Subject,
)
from app.models.user import User

router = APIRouter(
    prefix="/cbt",
    tags=["CBT - Student portal"],
    dependencies=[Depends(require_role_module("school")), Depends(PermissionChecker("school:cbt:sit"))],
)

PRACTICE_DAILY_CAP = 30
_OBJECTIVE = (QuestionType.MCQ, QuestionType.TRUE_FALSE)


async def _me_student(db: AsyncSession, user: User) -> Student:
    sid = await resolve_linked_student_id(db, user)
    if not sid:
        raise HTTPException(status_code=403, detail="No linked student record for this account.")
    student = (await db.execute(select(Student).where(Student.id == sid))).scalar_one()
    return student


async def _section_id(db: AsyncSession, student: Student) -> str | None:
    if not student.class_id:
        return None
    return (await db.execute(
        select(SchoolClass.section_id).where(SchoolClass.id == student.class_id)
    )).scalar_one_or_none()


# ── Practice ──────────────────────────────────────────────────────────────────


@router.get("/practice/subjects")
async def practice_subjects(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    """Subjects the student can practise: their section's, with at least one
    auto-markable question in the Question Bank."""
    student = await _me_student(db, current_user)
    section_id = await _section_id(db, student)
    q = (
        select(Subject.id, Subject.name, func.count(QuestionBankItem.id))
        .join(QuestionBankItem, QuestionBankItem.subject_id == Subject.id)
        .where(
            Subject.org_id == current_user.org_id,
            QuestionBankItem.org_id == current_user.org_id,
            QuestionBankItem.question_type.in_(_OBJECTIVE),
            Subject.is_active == True,  # noqa: E712
        )
        .group_by(Subject.id, Subject.name)
        .order_by(Subject.name)
    )
    if section_id:
        q = q.where((Subject.section_id == section_id) | (Subject.section_id.is_(None)))
    rows = (await db.execute(q)).all()
    return {"items": [{"id": r[0], "name": r[1], "question_count": r[2]} for r in rows]}


class PracticeStart(BaseModel):
    subject_id: str
    count: int = Field(default=10, ge=5, le=40)
    difficulty: Literal["any", "easy", "medium", "hard"] = "any"


@router.post("/practice/start", status_code=201)
async def start_practice(
    payload: PracticeStart,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    """Build a fresh practice paper for this student from the Question Bank and
    return the exam id; the client then sits it through the normal attempt flow."""
    student = await _me_student(db, current_user)
    org = current_user.org_id
    subject = (await db.execute(select(Subject).where(
        Subject.id == payload.subject_id, Subject.org_id == org,
    ))).scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")
    section_id = await _section_id(db, student)
    if section_id and subject.section_id and subject.section_id != section_id:
        raise HTTPException(status_code=404, detail="Subject not found.")

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    made = (await db.execute(select(func.count()).select_from(CBTExam).where(
        CBTExam.org_id == org, CBTExam.created_by == current_user.id,
        CBTExam.exam_type == "practice", CBTExam.created_at >= since,
    ))).scalar_one()
    if made >= PRACTICE_DAILY_CAP:
        raise HTTPException(status_code=429, detail="You've reached today's practice limit. Come back tomorrow.")

    bq = select(QuestionBankItem).where(
        QuestionBankItem.org_id == org, QuestionBankItem.subject_id == subject.id,
        QuestionBankItem.question_type.in_(_OBJECTIVE),
    )
    if payload.difficulty != "any":
        bq = bq.where(QuestionBankItem.difficulty == payload.difficulty)
    pool = list((await db.execute(bq)).scalars().all())
    if not pool:
        raise HTTPException(status_code=404, detail="There are no practice questions for that choice yet.")
    picked = random.sample(pool, min(payload.count, len(pool)))

    exam = CBTExam(
        title=f"Practice: {subject.name}",
        description="Self-made practice. Your score is saved to your progress.",
        class_id=student.class_id, subject_id=subject.id,
        created_by=current_user.id, org_id=org,
        duration_minutes=max(5, math.ceil(len(picked) * 1.0)),
        total_points=sum(float(p.points or 1) for p in picked),
        max_attempts=0, shuffle_questions=False, hold_results=False,
        status=ExamStatus.ACTIVE, exam_type="practice",
    )
    db.add(exam)
    await db.flush()
    for pos, item in enumerate(picked):
        db.add(CBTQuestion(
            exam_id=exam.id, question_text=item.question_text, question_type=item.question_type,
            options=item.options, correct_answer=item.correct_answer,
            points=item.points or 1.0, position=pos, answer_type="text", org_id=org,
        ))
    await db.flush()
    return {"exam_id": exam.id, "title": exam.title, "question_count": len(picked),
            "duration_minutes": exam.duration_minutes}


@router.get("/practice/attempts/{attempt_id}/review")
async def review_practice(
    attempt_id: str,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    """Right/wrong with the answer key — practice papers only. School exams, tests
    and mocks never expose their key to the student."""
    student = await _me_student(db, current_user)
    attempt = (await db.execute(select(CBTAttempt).where(
        CBTAttempt.id == attempt_id, CBTAttempt.org_id == current_user.org_id,
        CBTAttempt.student_id == student.id,
    ))).scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    exam = (await db.execute(select(CBTExam).where(CBTExam.id == attempt.exam_id))).scalar_one()
    if exam.exam_type != "practice" or exam.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    if attempt.status == AttemptStatus.IN_PROGRESS:
        raise HTTPException(status_code=409, detail="Submit the practice first.")
    qs = (await db.execute(select(CBTQuestion).where(CBTQuestion.exam_id == exam.id)
                           .order_by(CBTQuestion.position))).scalars().all()
    ans = {a.question_id: a for a in (await db.execute(
        select(CBTAnswer).where(CBTAnswer.attempt_id == attempt.id))).scalars().all()}
    items = []
    for q in qs:
        a = ans.get(q.id)
        items.append({
            "question_id": q.id, "question_text": q.question_text,
            "question_type": q.question_type.value if hasattr(q.question_type, "value") else q.question_type,
            "options": q.options, "your_answer": a.answer_text if a else None,
            "correct_answer": q.correct_answer, "is_correct": bool(a and a.is_correct),
            "points": q.points, "points_awarded": (a.points_awarded if a else 0.0) or 0.0,
        })
    return {"attempt_id": attempt.id, "score": attempt.score, "max_score": attempt.max_score, "items": items}


# ── Progress ──────────────────────────────────────────────────────────────────


def _pct(score, mx) -> float | None:
    mx = float(mx or 0)
    return round(float(score or 0) / mx * 100, 1) if mx > 0 else None


def _avg(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


@router.get("/my-progress")
async def my_progress(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    """The student's scores over time, by kind and by subject. Held results (a
    school exam whose teacher hasn't released it) count as 'pending', never as a score."""
    student = await _me_student(db, current_user)
    org = current_user.org_id
    rows = (await db.execute(
        select(CBTAttempt, CBTExam)
        .join(CBTExam, CBTExam.id == CBTAttempt.exam_id)
        .where(
            CBTAttempt.org_id == org, CBTAttempt.student_id == student.id,
            CBTAttempt.superseded_at.is_(None),
            CBTAttempt.status.in_([AttemptStatus.SUBMITTED, AttemptStatus.GRADED]),
            CBTExam.is_deleted == False,  # noqa: E712
        ).order_by(CBTAttempt.submitted_at.asc())
    )).all()
    subj_ids = {e.subject_id for _, e in rows if e.subject_id}
    names = {}
    if subj_ids:
        names = dict((await db.execute(select(Subject.id, Subject.name).where(Subject.id.in_(subj_ids)))).all())

    recent, by_type, by_subject, pending = [], defaultdict(list), defaultdict(list), 0
    for a, e in rows:
        released = e.exam_type == "practice" or (not e.hold_results) or e.results_published_at is not None
        if not released:
            pending += 1
        pct = _pct(a.score, a.max_score) if released else None
        item = {
            "attempt_id": a.id, "exam_id": e.id, "title": e.title, "exam_type": e.exam_type,
            "subject_id": e.subject_id, "subject_name": names.get(e.subject_id),
            "score": a.score if released else None, "max_score": a.max_score,
            "percentage": pct, "pending": not released,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
        }
        recent.append(item)
        if pct is not None:
            by_type[e.exam_type].append(pct)
            by_subject[e.subject_id or "_"].append(pct)

    all_pcts = [p for v in by_type.values() for p in v]
    subjects = [{
        "subject_id": sid if sid != "_" else None, "name": names.get(sid, "General"),
        "taken": len(v), "average": _avg(v), "last": v[-1], "best": max(v), "trend": v[-10:],
    } for sid, v in by_subject.items()]
    subjects.sort(key=lambda s: s["name"])
    return {
        "overall": {
            "taken": len(rows), "average": _avg(all_pcts), "best": max(all_pcts) if all_pcts else None,
            "pending_results": pending, "trend": all_pcts[-12:],
        },
        "by_type": {t: {"taken": len(v), "average": _avg(v)} for t, v in by_type.items()},
        "subjects": subjects,
        "recent": list(reversed(recent))[:40],
    }


# ── Exam-room integrity signals ───────────────────────────────────────────────


class AttemptEvent(BaseModel):
    type: Literal["idle", "blur", "paste"]


_EVENT_COL = {"idle": CBTAttempt.idle_count, "blur": CBTAttempt.blur_count, "paste": CBTAttempt.paste_count}


@router.post("/attempts/{attempt_id}/events", status_code=204)
async def record_attempt_event(
    attempt_id: str, payload: AttemptEvent,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    """Count an idle / tab-switch / paste event on the student's own in-progress
    attempt, so staff can see it next to the result."""
    student = await _me_student(db, current_user)
    col = _EVENT_COL[payload.type]
    res = await db.execute(
        sa_update(CBTAttempt)
        .where(
            CBTAttempt.id == attempt_id, CBTAttempt.org_id == current_user.org_id,
            CBTAttempt.student_id == student.id, CBTAttempt.status == AttemptStatus.IN_PROGRESS,
        )
        .values({col.key: col + 1})
    )
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Attempt not found.")
