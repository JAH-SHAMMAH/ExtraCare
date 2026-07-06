"""
CBT (Computer-Based Testing) Router
=====================================
Exams, questions, student attempts and auto-grading for MCQ/True-False.

Design notes:
  - Teachers build exams + questions, publish them, then students start an
    attempt, submit answers, and the system auto-grades objective questions.
  - Free-text answers are stored but not graded — teachers can grade them
    manually via a later endpoint (not yet wired here; stored for future use).
  - Correct answers never leak to students: the /exams/{id}/questions endpoint
    strips `correct_answer` for non-write callers.

RBAC:
  - school:read   → students viewing published exams, their own attempts
  - school:write  → teachers creating exams, grading, publishing
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.modules.school import (
    CBTExam,
    CBTQuestion,
    CBTAttempt,
    CBTAnswer,
    ExamStatus,
    AttemptStatus,
    QuestionType,
    Student,
)
from app.schemas.school_experience import (
    ExamCreate,
    ExamUpdate,
    ExamResponse,
    QuestionCreate,
    QuestionResponse,
    QuestionWithAnswer,
    AttemptSubmit,
    AttemptResponse,
)
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker
from app.services.audit_service import log_action
from app.models.audit import AuditAction
from app.core.events import log_event
from app.core.school_identity import (
    resolve_linked_student_id,
    resolve_taught_class_ids,
    resolve_taught_subject_ids,
)

router = APIRouter(
    prefix="/cbt",
    tags=["CBT - Computer-Based Testing"],
    dependencies=[Depends(require_role_module("school"))],
)

_can_read = Depends(PermissionChecker("school:cbt:read"))
_can_write = Depends(PermissionChecker("school:cbt:write"))


# ── Exams ─────────────────────────────────────────────────────────────────────


@router.get("/exams", dependencies=[_can_read])
async def list_exams(
    class_id: str | None = None,
    status_filter: str | None = Query(default=None, alias="status", description="Server-recognised values: draft, published, active, closed, live."),
    for_me: bool = Query(default=False, description="Scope to the caller: student → own class; teacher → owned classes/subjects."),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    now = datetime.now(timezone.utc)

    query = select(CBTExam).where(
        CBTExam.org_id == current_user.org_id,
        CBTExam.is_deleted == False,
    )
    if class_id:
        query = query.where(CBTExam.class_id == class_id)

    # "live" is a derived status — exam is open AND now is within window.
    if status_filter == "live":
        query = query.where(
            CBTExam.status.in_([ExamStatus.PUBLISHED, ExamStatus.ACTIVE]),
            CBTExam.start_time <= now,
            CBTExam.end_time >= now,
        )
    elif status_filter:
        query = query.where(CBTExam.status == status_filter)

    if for_me:
        taught_classes = await resolve_taught_class_ids(db, current_user)
        taught_subjects = await resolve_taught_subject_ids(db, current_user)
        if taught_classes or taught_subjects:
            from sqlalchemy import or_
            conditions = []
            if taught_classes:
                conditions.append(CBTExam.class_id.in_(taught_classes))
            if taught_subjects:
                conditions.append(CBTExam.subject_id.in_(taught_subjects))
            conditions.append(CBTExam.created_by == current_user.id)
            query = query.where(or_(*conditions))
        else:
            student_id = await resolve_linked_student_id(db, current_user)
            if student_id:
                student_class = (await db.execute(
                    select(Student.class_id).where(Student.id == student_id)
                )).scalar_one_or_none()
                if student_class:
                    query = query.where(CBTExam.class_id == student_class)
                else:
                    query = query.where(CBTExam.id == "__none__")
            else:
                query = query.where(CBTExam.id == "__none__")

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(CBTExam.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()

    return {
        "items": [_exam_with_live(e, now) for e in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _is_live(exam: CBTExam, now: datetime) -> bool:
    if exam.status not in (ExamStatus.PUBLISHED, ExamStatus.ACTIVE):
        return False
    if exam.start_time and exam.start_time > now:
        return False
    if exam.end_time and exam.end_time < now:
        return False
    return True


def _exam_with_live(exam: CBTExam, now: datetime) -> dict:
    payload = ExamResponse.model_validate(exam).model_dump()
    payload["is_live"] = _is_live(exam, now)
    return payload


@router.post("/exams", status_code=201, dependencies=[_can_write])
async def create_exam(
    payload: ExamCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    exam = CBTExam(
        **payload.model_dump(),
        created_by=current_user.id,
        org_id=current_user.org_id,
    )
    db.add(exam)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="CBTExam", resource_id=exam.id,
        resource_label=getattr(exam, "title", None) or exam.id,
        request=request,
    )
    return ExamResponse.model_validate(exam).model_dump()


@router.get("/exams/{exam_id}", dependencies=[_can_read])
async def get_exam(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    exam = await _get_exam_or_404(db, exam_id, current_user.org_id)
    return _exam_with_live(exam, datetime.now(timezone.utc))


@router.patch("/exams/{exam_id}", dependencies=[_can_write])
async def update_exam(
    exam_id: str,
    payload: ExamUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    exam = await _get_exam_or_404(db, exam_id, current_user.org_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(exam, field, value)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="CBTExam", resource_id=exam.id,
        resource_label=getattr(exam, "title", None) or exam.id,
        new_values=changes, request=request,
    )
    return ExamResponse.model_validate(exam).model_dump()


@router.delete("/exams/{exam_id}", status_code=204, dependencies=[_can_write])
async def delete_exam(
    exam_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    exam = await _get_exam_or_404(db, exam_id, current_user.org_id)
    exam.is_deleted = True
    exam.deleted_at = datetime.now(timezone.utc)
    await log_action(
        db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
        resource_type="CBTExam", resource_id=exam.id,
        resource_label=getattr(exam, "title", None) or exam.id,
        severity="warning", request=request,
    )


# ── Questions ─────────────────────────────────────────────────────────────────


@router.get("/exams/{exam_id}/questions", dependencies=[_can_read])
async def list_questions(
    exam_id: str,
    include_answers: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    exam = await _get_exam_or_404(db, exam_id, current_user.org_id)

    result = await db.execute(
        select(CBTQuestion).where(
            CBTQuestion.exam_id == exam.id,
            CBTQuestion.org_id == current_user.org_id,
        ).order_by(CBTQuestion.position.asc(), CBTQuestion.created_at.asc())
    )
    questions = result.scalars().all()

    # Only teachers with school:write should see correct_answer. Because this
    # endpoint is behind school:read, include_answers=true is permitted only if
    # the user also has school:write.
    wants_answers = include_answers and current_user.has_permission("school:write")
    if wants_answers:
        return {"items": [QuestionWithAnswer.model_validate(q).model_dump() for q in questions]}
    return {"items": [QuestionResponse.model_validate(q).model_dump() for q in questions]}


@router.post("/exams/{exam_id}/questions", status_code=201, dependencies=[_can_write])
async def add_question(
    exam_id: str,
    payload: QuestionCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    exam = await _get_exam_or_404(db, exam_id, current_user.org_id)

    question = CBTQuestion(
        exam_id=exam.id,
        **payload.model_dump(),
        org_id=current_user.org_id,
    )
    db.add(question)

    # Keep total_points in sync for quick display in exam lists.
    exam.total_points = (exam.total_points or 0) + payload.points
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="CBTQuestion", resource_id=question.id,
        resource_label=f"question in exam {exam.id}",
        metadata={"exam_id": exam.id, "points": payload.points}, request=request,
    )
    return QuestionWithAnswer.model_validate(question).model_dump()


@router.delete("/questions/{question_id}", status_code=204, dependencies=[_can_write])
async def delete_question(
    question_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(CBTQuestion).where(
            CBTQuestion.id == question_id,
            CBTQuestion.org_id == current_user.org_id,
        )
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    # Decrement exam total_points.
    exam = (await db.execute(
        select(CBTExam).where(CBTExam.id == question.exam_id)
    )).scalar_one_or_none()
    if exam:
        exam.total_points = max(0, (exam.total_points or 0) - (question.points or 0))

    q_ref, q_exam = question.id, question.exam_id
    await db.delete(question)
    await log_action(
        db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
        resource_type="CBTQuestion", resource_id=q_ref,
        resource_label=f"question in exam {q_exam}",
        severity="warning", request=request,
    )


# ── Attempts ──────────────────────────────────────────────────────────────────


@router.post("/exams/{exam_id}/attempts", status_code=201, dependencies=[_can_read])
async def start_attempt(
    exam_id: str,
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    exam = await _get_exam_or_404(db, exam_id, current_user.org_id)
    now = datetime.now(timezone.utc)
    if not _is_live(exam, now):
        # Categorise rejection so we can spot UX issues (e.g. clocks drifting,
        # exams being closed too eagerly, students hitting the early/late edges).
        if exam.status not in (ExamStatus.PUBLISHED, ExamStatus.ACTIVE):
            reason = "status_closed"
        elif exam.start_time and exam.start_time > now:
            reason = "before_window"
        elif exam.end_time and exam.end_time < now:
            reason = "after_window"
        else:
            reason = "unknown"
        log_event(
            "cbt_attempt_rejected",
            org_id=current_user.org_id,
            exam_id=exam.id,
            student_id=student_id,
            reason=reason,
            status=exam.status.value if hasattr(exam.status, "value") else str(exam.status),
        )
        raise HTTPException(status_code=400, detail="Exam is not currently live.")

    # One in-progress attempt per student per exam
    existing = (await db.execute(
        select(CBTAttempt).where(
            CBTAttempt.exam_id == exam.id,
            CBTAttempt.student_id == student_id,
            CBTAttempt.org_id == current_user.org_id,
            CBTAttempt.status == AttemptStatus.IN_PROGRESS,
        )
    )).scalar_one_or_none()
    if existing:
        return AttemptResponse.model_validate(existing).model_dump()

    attempt = CBTAttempt(
        exam_id=exam.id,
        student_id=student_id,
        started_at=datetime.now(timezone.utc),
        max_score=exam.total_points,
        status=AttemptStatus.IN_PROGRESS,
        org_id=current_user.org_id,
    )
    db.add(attempt)
    await db.flush()
    return AttemptResponse.model_validate(attempt).model_dump()


@router.post("/attempts/{attempt_id}/submit", dependencies=[_can_read])
async def submit_attempt(
    attempt_id: str,
    payload: AttemptSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    attempt = (await db.execute(
        select(CBTAttempt).where(
            CBTAttempt.id == attempt_id,
            CBTAttempt.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Attempt already submitted.")

    # Load all questions for this exam into a dict for fast lookup.
    q_result = await db.execute(
        select(CBTQuestion).where(
            CBTQuestion.exam_id == attempt.exam_id,
            CBTQuestion.org_id == current_user.org_id,
        )
    )
    questions = {q.id: q for q in q_result.scalars().all()}

    total_score = 0.0
    for ans in payload.answers:
        question = questions.get(ans.question_id)
        if not question:
            continue  # silently skip — prevents client error from corrupting grading

        is_correct = None
        points_awarded = None
        # Auto-grade objective types only
        if question.question_type in (QuestionType.MCQ, QuestionType.TRUE_FALSE):
            is_correct = (ans.answer_text or "").strip().lower() == (question.correct_answer or "").strip().lower()
            points_awarded = question.points if is_correct else 0.0
            total_score += points_awarded

        db.add(CBTAnswer(
            attempt_id=attempt.id,
            question_id=question.id,
            answer_text=ans.answer_text,
            is_correct=is_correct,
            points_awarded=points_awarded,
            org_id=current_user.org_id,
        ))

    attempt.score = total_score
    attempt.submitted_at = datetime.now(timezone.utc)
    attempt.status = AttemptStatus.GRADED  # auto-graded objective exams
    await db.flush()
    return AttemptResponse.model_validate(attempt).model_dump()


@router.get("/attempts", dependencies=[_can_read])
async def list_attempts(
    exam_id: str | None = None,
    student_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(CBTAttempt).where(CBTAttempt.org_id == current_user.org_id)
    if exam_id:
        query = query.where(CBTAttempt.exam_id == exam_id)
    if student_id:
        query = query.where(CBTAttempt.student_id == student_id)
    query = query.order_by(CBTAttempt.created_at.desc())
    items = (await db.execute(query)).scalars().all()
    return {"items": [AttemptResponse.model_validate(a).model_dump() for a in items]}


@router.get("/attempts/{attempt_id}", dependencies=[_can_read])
async def get_attempt(
    attempt_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    attempt = (await db.execute(
        select(CBTAttempt).where(
            CBTAttempt.id == attempt_id,
            CBTAttempt.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found.")

    # Include answers for review
    answers = (await db.execute(
        select(CBTAnswer).where(
            CBTAnswer.attempt_id == attempt.id,
            CBTAnswer.org_id == current_user.org_id,
        )
    )).scalars().all()

    return {
        **AttemptResponse.model_validate(attempt).model_dump(),
        "answers": [
            {
                "id": a.id,
                "question_id": a.question_id,
                "answer_text": a.answer_text,
                "is_correct": a.is_correct,
                "points_awarded": a.points_awarded,
            }
            for a in answers
        ],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_exam_or_404(db: AsyncSession, exam_id: str, org_id: str) -> CBTExam:
    result = await db.execute(
        select(CBTExam).where(
            CBTExam.id == exam_id,
            CBTExam.org_id == org_id,
            CBTExam.is_deleted == False,
        )
    )
    exam = result.scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found.")
    return exam
