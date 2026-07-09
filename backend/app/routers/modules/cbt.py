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

import csv
import io
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, UploadFile, File
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.modules.school import (
    CBTExam,
    CBTQuestion,
    CBTAttempt,
    CBTAnswer,
    QuestionBankItem,
    CBTIntervention,
    CBTSettings,
    InterventionStatus,
    Subject,
    ExamStatus,
    AttemptStatus,
    QuestionType,
    Student,
)
from app.schemas.question_bank import BankItemCreate, BankItemUpdate, ComposeFromBank
from app.schemas.cbt_ops import InterventionCreate, InterventionUpdate, CBTSettingsUpdate
from app.schemas.school_experience import (
    ExamCreate,
    ExamUpdate,
    ExamResponse,
    QuestionCreate,
    QuestionResponse,
    QuestionWithAnswer,
    AttemptSubmit,
    AttemptResponse,
    RemarkItem,
)
from fastapi.responses import Response
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
# The Question Bank holds correct answers and is a teacher/admin authoring tool.
# Gate it on the broad school scopes, NOT school:cbt:* — students hold cbt:read/
# write to SIT tests and must never read the bank's answers.
_bank_read = Depends(PermissionChecker("school:read"))
_bank_write = Depends(PermissionChecker("school:write"))


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


# ── Question Bank (reusable questions) ───────────────────────────────────────
# A pool of questions independent of any exam, categorised by subject/topic/
# difficulty. Tests are composed by COPYING selected bank items into an exam's
# CBTQuestion set (from-bank below), so the take/score engine is untouched.

_DIFFICULTY = ("easy", "medium", "hard")
_QTYPES = ("mcq", "true_false", "short_answer", "long_answer")


async def _bank_subject_names(db: AsyncSession, org_id: str, ids: set) -> dict:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(
        select(Subject.id, Subject.name).where(Subject.org_id == org_id, Subject.id.in_(ids))
    )).all()
    return {r.id: r.name for r in rows}


def _bank_dict(q: QuestionBankItem, subject_name) -> dict:
    return {
        "id": q.id,
        "subject_id": q.subject_id,
        "subject_name": subject_name,
        "topic": q.topic,
        "difficulty": q.difficulty,
        "question_text": q.question_text,
        "question_type": q.question_type.value if hasattr(q.question_type, "value") else q.question_type,
        "options": q.options,
        "correct_answer": q.correct_answer,
        "points": float(q.points or 0),
        "created_at": q.created_at.isoformat() if q.created_at else None,
    }


async def _load_bank_item(db: AsyncSession, item_id: str, org_id: str) -> QuestionBankItem:
    q = (await db.execute(
        select(QuestionBankItem).where(QuestionBankItem.id == item_id, QuestionBankItem.org_id == org_id)
    )).scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found in bank.")
    return q


@router.get("/question-bank", dependencies=[_bank_read])
async def list_bank(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    subject_id: str | None = None,
    topic: str | None = None,
    difficulty: str | None = None,
    question_type: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org_id = current_user.org_id
    query = select(QuestionBankItem).where(QuestionBankItem.org_id == org_id)
    if subject_id:
        query = query.where(QuestionBankItem.subject_id == subject_id)
    if topic:
        query = query.where(QuestionBankItem.topic == topic)
    if difficulty in _DIFFICULTY:
        query = query.where(QuestionBankItem.difficulty == difficulty)
    if question_type in _QTYPES:
        query = query.where(QuestionBankItem.question_type == QuestionType(question_type))
    if search:
        query = query.where(QuestionBankItem.question_text.ilike(f"%{search}%"))
    query = query.order_by(QuestionBankItem.created_at.desc())
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    names = await _bank_subject_names(db, org_id, {q.subject_id for q in rows})
    return {
        "items": [_bank_dict(q, names.get(q.subject_id)) for q in rows],
        "total": total, "page": page, "page_size": page_size,
    }


@router.post("/question-bank", status_code=201, dependencies=[_bank_write])
async def create_bank_item(
    payload: BankItemCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org_id = current_user.org_id
    if payload.difficulty not in _DIFFICULTY:
        raise HTTPException(status_code=422, detail="difficulty must be easy, medium, or hard.")
    if payload.question_type not in _QTYPES:
        raise HTTPException(status_code=422, detail=f"invalid question_type. One of: {', '.join(_QTYPES)}.")
    if payload.subject_id:
        ok = (await db.execute(
            select(Subject.id).where(Subject.id == payload.subject_id, Subject.org_id == org_id)
        )).scalar_one_or_none()
        if not ok:
            raise HTTPException(status_code=404, detail="Subject not found.")
    data = payload.model_dump()
    data["question_type"] = QuestionType(data["question_type"])  # "mcq" -> QuestionType.MCQ
    q = QuestionBankItem(**data, created_by=current_user.id, org_id=org_id)
    db.add(q)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, org_id, actor=current_user,
        resource_type="QuestionBankItem", resource_id=q.id, resource_label="bank question", request=request,
    )
    names = await _bank_subject_names(db, org_id, {q.subject_id})
    return _bank_dict(q, names.get(q.subject_id))


@router.patch("/question-bank/{item_id}", dependencies=[_bank_write])
async def update_bank_item(
    item_id: str,
    payload: BankItemUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org_id = current_user.org_id
    q = await _load_bank_item(db, item_id, org_id)
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("difficulty") and updates["difficulty"] not in _DIFFICULTY:
        raise HTTPException(status_code=422, detail="difficulty must be easy, medium, or hard.")
    if updates.get("question_type") and updates["question_type"] not in _QTYPES:
        raise HTTPException(status_code=422, detail="invalid question_type.")
    if "question_type" in updates:
        updates["question_type"] = QuestionType(updates["question_type"])
    for k, v in updates.items():
        setattr(q, k, v)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, org_id, actor=current_user,
        resource_type="QuestionBankItem", resource_id=q.id, resource_label="bank question", request=request,
    )
    names = await _bank_subject_names(db, org_id, {q.subject_id})
    return _bank_dict(q, names.get(q.subject_id))


@router.delete("/question-bank/{item_id}", status_code=204, dependencies=[_bank_write])
async def delete_bank_item(
    item_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org_id = current_user.org_id
    q = await _load_bank_item(db, item_id, org_id)
    await db.delete(q)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_DELETED, org_id, actor=current_user,
        resource_type="QuestionBankItem", resource_id=item_id, resource_label="bank question",
        severity="warning", request=request,
    )


@router.post("/question-bank/import", dependencies=[_bank_write])
async def import_bank(
    file: UploadFile = File(...),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Bulk-import bank questions from a CSV. Columns (case-insensitive):
    question, type, subject, topic, difficulty, option_a..option_e, correct_answer,
    points. Unknown subject/type/difficulty fall back to null/mcq/medium."""
    org_id = current_user.org_id
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="File must be a UTF-8 CSV.")
    reader = csv.DictReader(io.StringIO(text))
    subs = (await db.execute(
        select(Subject.id, Subject.name, Subject.code).where(Subject.org_id == org_id)
    )).all()
    lut: dict[str, str] = {}
    for sid, name, code in subs:
        if name:
            lut[name.strip().lower()] = sid
        if code:
            lut[code.strip().lower()] = sid
    imported = 0
    errors: list[str] = []
    for i, raw in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "") for k, v in raw.items()}
        qtext = (row.get("question") or row.get("question_text") or "").strip()
        if not qtext:
            errors.append(f"row {i}: missing question")
            continue
        opts = [{"key": k, "text": row[f"option_{k}"].strip()} for k in "abcde" if row.get(f"option_{k}", "").strip()]
        qtype = (row.get("type") or row.get("question_type") or "mcq").strip().lower()
        if qtype not in _QTYPES:
            qtype = "mcq"
        diff = (row.get("difficulty") or "medium").strip().lower()
        if diff not in _DIFFICULTY:
            diff = "medium"
        try:
            pts = float(row.get("points") or 1)
        except ValueError:
            pts = 1.0
        db.add(QuestionBankItem(
            question_text=qtext, question_type=QuestionType(qtype), options=opts or None,
            correct_answer=(row.get("correct_answer") or row.get("answer") or "").strip() or None,
            difficulty=diff, topic=(row.get("topic") or "").strip() or None,
            subject_id=lut.get((row.get("subject") or "").strip().lower()),
            points=pts, created_by=current_user.id, org_id=org_id,
        ))
        imported += 1
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, org_id, actor=current_user,
        resource_type="QuestionBankItem", resource_label=f"imported {imported} bank question(s)",
        severity="warning", metadata={"imported": imported, "errors": len(errors)}, request=request,
    )
    return {"imported": imported, "errors": errors[:20]}


@router.post("/exams/{exam_id}/questions/from-bank", status_code=201, dependencies=[_bank_write])
async def add_questions_from_bank(
    exam_id: str,
    payload: ComposeFromBank,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Compose a test: copy the chosen bank questions onto the exam as CBTQuestions
    (so editing/deleting them on the exam doesn't touch the bank)."""
    org_id = current_user.org_id
    exam = await _get_exam_or_404(db, exam_id, org_id)
    items = (await db.execute(
        select(QuestionBankItem).where(
            QuestionBankItem.id.in_(payload.question_ids), QuestionBankItem.org_id == org_id)
    )).scalars().all()
    if not items:
        raise HTTPException(status_code=404, detail="No matching bank questions found.")
    max_pos = (await db.execute(
        select(func.max(CBTQuestion.position)).where(CBTQuestion.exam_id == exam.id)
    )).scalar() or 0
    added = 0
    pts = 0.0
    for it in items:
        added += 1
        db.add(CBTQuestion(
            exam_id=exam.id, question_text=it.question_text, question_type=it.question_type,
            options=it.options, correct_answer=it.correct_answer, points=it.points,
            position=max_pos + added, org_id=org_id,
        ))
        pts += float(it.points or 0)
    exam.total_points = (exam.total_points or 0) + pts
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, org_id, actor=current_user,
        resource_type="CBTQuestion", resource_label=f"added {added} question(s) from bank to exam {exam.id}",
        metadata={"exam_id": exam.id, "added": added}, request=request,
    )
    return {"added": added, "total_points": float(exam.total_points or 0)}


# ── Results: manager / export / remark ───────────────────────────────────────
# Staff-only (school:read/write, not cbt:*): these expose every student's scores
# and correct answers. The auto-grader only scores MCQ/true-false; subjective
# (short/long) answers land ungraded (points_awarded=None) — Test Remark is how a
# teacher awards them, which re-totals the attempt.

_PASS_FRACTION = 0.5  # CBTExam has no pass mark; 50% of total is the default line


async def _cbt_student_names(db: AsyncSession, org_id: str, ids: set) -> dict:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(
        select(Student.id, Student.first_name, Student.last_name).where(
            Student.org_id == org_id, Student.id.in_(ids))
    )).all()
    return {r.id: " ".join(p for p in [r.first_name, r.last_name] if p) or r.id for r in rows}


async def _load_attempt(db: AsyncSession, attempt_id: str, org_id: str) -> CBTAttempt:
    a = (await db.execute(
        select(CBTAttempt).where(CBTAttempt.id == attempt_id, CBTAttempt.org_id == org_id)
    )).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    return a


async def _ungraded_by_attempt(db: AsyncSession, org_id: str, attempt_ids: list[str]) -> dict[str, int]:
    """attempt_id -> count of answers still awaiting a manual grade (points None)."""
    if not attempt_ids:
        return {}
    rows = (await db.execute(
        select(CBTAnswer.attempt_id, func.count(CBTAnswer.id)).where(
            CBTAnswer.org_id == org_id, CBTAnswer.attempt_id.in_(attempt_ids),
            CBTAnswer.points_awarded.is_(None))
        .group_by(CBTAnswer.attempt_id)
    )).all()
    return {r[0]: r[1] for r in rows}


def _result_rows(attempts, names, ungraded, total_points):
    rows = []
    for a in attempts:
        score = float(a.score or 0)
        mx = float(a.max_score or total_points or 0)
        status = a.status.value if hasattr(a.status, "value") else a.status
        rows.append({
            "id": a.id, "student_id": a.student_id, "student_name": names.get(a.student_id),
            "score": score, "max_score": mx,
            "percentage": round(score / mx * 100, 1) if mx else 0.0,
            "status": status,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            "needs_review": ungraded.get(a.id, 0) > 0,
        })
    return rows


@router.get("/exams/{exam_id}/results", dependencies=[_bank_read])
async def exam_results(exam_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Result Manager for one exam: every attempt (student, score, %, review flag)
    plus summary stats."""
    org_id = current_user.org_id
    exam = await _get_exam_or_404(db, exam_id, org_id)
    attempts = (await db.execute(
        select(CBTAttempt).where(CBTAttempt.exam_id == exam_id, CBTAttempt.org_id == org_id)
        .order_by(CBTAttempt.score.desc())
    )).scalars().all()
    names = await _cbt_student_names(db, org_id, {a.student_id for a in attempts})
    ungraded = await _ungraded_by_attempt(db, org_id, [a.id for a in attempts])
    total_points = float(exam.total_points or 0)
    rows = _result_rows(attempts, names, ungraded, total_points)

    scored = [r for r in rows if r["status"] != "in_progress"]
    scores = [r["score"] for r in scored]
    stats = {
        "attempts": len(rows),
        "completed": len(scored),
        "pending_review": sum(1 for r in rows if r["needs_review"]),
        "average": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "highest": max(scores) if scores else 0.0,
        "lowest": min(scores) if scores else 0.0,
        "pass_rate": round(sum(1 for r in scored if r["max_score"] and r["score"] >= r["max_score"] * _PASS_FRACTION) / len(scored) * 100) if scored else 0,
    }
    return {
        "exam": {"id": exam.id, "title": exam.title, "total_points": total_points,
                 "class_id": exam.class_id, "subject_id": exam.subject_id},
        "attempts": rows,
        "stats": stats,
    }


@router.get("/exams/{exam_id}/results/export", dependencies=[_bank_read])
async def export_results(exam_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Download the exam's results as CSV."""
    org_id = current_user.org_id
    exam = await _get_exam_or_404(db, exam_id, org_id)
    attempts = (await db.execute(
        select(CBTAttempt).where(CBTAttempt.exam_id == exam_id, CBTAttempt.org_id == org_id)
        .order_by(CBTAttempt.score.desc())
    )).scalars().all()
    names = await _cbt_student_names(db, org_id, {a.student_id for a in attempts})
    total_points = float(exam.total_points or 0)

    def _n(x: float):
        return int(x) if float(x).is_integer() else round(x, 2)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Student", "Student ID", "Score", "Max", "Percentage", "Status", "Submitted"])
    for a in attempts:
        score = float(a.score or 0)
        mx = float(a.max_score or total_points or 0)
        w.writerow([
            names.get(a.student_id, a.student_id), a.student_id, _n(score), _n(mx),
            f"{round(score / mx * 100, 1) if mx else 0}%",
            a.status.value if hasattr(a.status, "value") else a.status,
            a.submitted_at.isoformat() if a.submitted_at else "",
        ])
    safe_title = "".join(c if c.isalnum() else "_" for c in (exam.title or "exam"))[:40]
    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="results_{safe_title}.csv"'},
    )


@router.get("/attempts/{attempt_id}/review", dependencies=[_bank_read])
async def review_attempt(attempt_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Staff review of one attempt — every answer with the question text, the
    correct answer, and the current award, so subjective answers can be graded.
    Distinct from GET /attempts/{id} (student self-review), which never leaks the
    correct answer."""
    org_id = current_user.org_id
    attempt = await _load_attempt(db, attempt_id, org_id)
    answers = (await db.execute(
        select(CBTAnswer).where(CBTAnswer.attempt_id == attempt.id, CBTAnswer.org_id == org_id)
    )).scalars().all()
    questions = {q.id: q for q in (await db.execute(
        select(CBTQuestion).where(CBTQuestion.exam_id == attempt.exam_id, CBTQuestion.org_id == org_id)
    )).scalars().all()}
    names = await _cbt_student_names(db, org_id, {attempt.student_id})

    rows = []
    for a in answers:
        q = questions.get(a.question_id)
        qtype = (q.question_type.value if q and hasattr(q.question_type, "value") else (q.question_type if q else None))
        rows.append({
            "answer_id": a.id, "question_id": a.question_id,
            "question_text": q.question_text if q else None,
            "question_type": qtype,
            "max_points": float(q.points) if q else 0.0,
            "correct_answer": q.correct_answer if q else None,
            "answer_text": a.answer_text,
            "is_correct": a.is_correct,
            "points_awarded": a.points_awarded,
            "needs_grading": a.points_awarded is None and q is not None
                             and q.question_type in (QuestionType.SHORT_ANSWER, QuestionType.LONG_ANSWER),
        })
    return {
        "attempt": {
            **AttemptResponse.model_validate(attempt).model_dump(),
            "student_name": names.get(attempt.student_id),
        },
        "answers": rows,
    }


@router.post("/attempts/{attempt_id}/remark", dependencies=[_bank_write])
async def remark_attempt(
    attempt_id: str,
    payload: list[RemarkItem],
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Apply manual grade overrides to an attempt's answers, then re-total the
    attempt score from every answer's award (subjective grades now count)."""
    org_id = current_user.org_id
    attempt = await _load_attempt(db, attempt_id, org_id)
    answers = {a.id: a for a in (await db.execute(
        select(CBTAnswer).where(CBTAnswer.attempt_id == attempt.id, CBTAnswer.org_id == org_id)
    )).scalars().all()}
    questions = {q.id: q for q in (await db.execute(
        select(CBTQuestion).where(CBTQuestion.exam_id == attempt.exam_id, CBTQuestion.org_id == org_id)
    )).scalars().all()}

    changed = 0
    for item in payload:
        a = answers.get(item.answer_id)
        if not a:
            continue
        q = questions.get(a.question_id)
        cap = float(q.points) if q else item.points_awarded
        pts = max(0.0, min(float(item.points_awarded), cap))
        a.points_awarded = pts
        a.is_correct = pts >= cap if cap else pts > 0
        changed += 1

    # Re-total from all answers (None counts as 0 — still-ungraded subjective items).
    attempt.score = sum(float(a.points_awarded or 0) for a in answers.values())
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, org_id, actor=current_user,
        resource_type="CBTAttempt", resource_id=attempt.id,
        resource_label=f"re-marked {changed} answer(s); score {attempt.score}", request=request,
    )
    return {"score": float(attempt.score or 0), "max_score": float(attempt.max_score or 0), "changed": changed}


# ── Reset / Intervention / Settings (Phase C) ─────────────────────────────────
# Staff-only ops: reset an attempt for a retake, flag a student for follow-up,
# and set org-level CBT defaults.

@router.post("/attempts/{attempt_id}/reset", dependencies=[_bank_write])
async def reset_attempt(
    attempt_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete an attempt + its answers so the student can retake the exam."""
    org_id = current_user.org_id
    attempt = await _load_attempt(db, attempt_id, org_id)
    answers = (await db.execute(
        select(CBTAnswer).where(CBTAnswer.attempt_id == attempt.id, CBTAnswer.org_id == org_id)
    )).scalars().all()
    for a in answers:
        await db.delete(a)
    await db.delete(attempt)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_DELETED, org_id, actor=current_user,
        resource_type="CBTAttempt", resource_id=attempt_id,
        resource_label=f"reset attempt for retake ({len(answers)} answers cleared)",
        severity="warning", request=request,
    )
    return {"reset": True}


def _intervention_dict(iv: CBTIntervention, student_name) -> dict:
    return {
        "id": iv.id,
        "student_id": iv.student_id,
        "student_name": student_name,
        "exam_id": iv.exam_id,
        "attempt_id": iv.attempt_id,
        "reason": iv.reason,
        "note": iv.note,
        "status": iv.status.value if hasattr(iv.status, "value") else iv.status,
        "created_at": iv.created_at.isoformat() if iv.created_at else None,
        "resolved_at": iv.resolved_at.isoformat() if iv.resolved_at else None,
    }


async def _load_intervention(db: AsyncSession, iv_id: str, org_id: str) -> CBTIntervention:
    iv = (await db.execute(
        select(CBTIntervention).where(CBTIntervention.id == iv_id, CBTIntervention.org_id == org_id)
    )).scalar_one_or_none()
    if not iv:
        raise HTTPException(status_code=404, detail="Intervention not found.")
    return iv


async def _intervention_in_scope(db: AsyncSession, user: User, iv: CBTIntervention) -> bool:
    """Teacher-tier visibility (R2): admins (school_admin:read) see every
    intervention org-wide; everyone else sees only flags for a student in one of
    their own classes, or ones they raised themselves."""
    if user.has_permission("school_admin:read"):
        return True
    if iv.created_by == user.id:
        return True
    taught = await resolve_taught_class_ids(db, user)
    if not taught:
        return False
    student_class = (await db.execute(
        select(Student.class_id).where(Student.id == iv.student_id)
    )).scalar_one_or_none()
    return student_class in taught


@router.get("/interventions", dependencies=[_bank_read])
async def list_interventions(
    status: str | None = None,
    student_id: str | None = None,
    exam_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org_id = current_user.org_id
    query = select(CBTIntervention).where(CBTIntervention.org_id == org_id)
    if status is not None:
        if status not in ("open", "in_progress", "resolved"):
            raise HTTPException(status_code=422, detail="Invalid status. Use open, in_progress, or resolved.")
        query = query.where(CBTIntervention.status == InterventionStatus(status))
    if student_id:
        query = query.where(CBTIntervention.student_id == student_id)
    if exam_id:
        query = query.where(CBTIntervention.exam_id == exam_id)
    # Teacher-tier scoping (R2): admins see org-wide; everyone else only their own
    # classes' flagged students, or interventions they raised. Least-exposure.
    if not current_user.has_permission("school_admin:read"):
        taught = await resolve_taught_class_ids(db, current_user)
        query = query.join(Student, Student.id == CBTIntervention.student_id)
        if taught:
            query = query.where(or_(
                Student.class_id.in_(taught),
                CBTIntervention.created_by == current_user.id,
            ))
        else:
            query = query.where(CBTIntervention.created_by == current_user.id)
    query = query.order_by(CBTIntervention.created_at.desc())
    rows = (await db.execute(query)).scalars().all()
    names = await _cbt_student_names(db, org_id, {iv.student_id for iv in rows})
    return {"items": [_intervention_dict(iv, names.get(iv.student_id)) for iv in rows]}


@router.post("/interventions", status_code=201, dependencies=[_bank_write])
async def create_intervention(
    payload: InterventionCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Flag a student for follow-up (e.g. from a low score on the Result Manager)."""
    org_id = current_user.org_id
    student = (await db.execute(
        select(Student).where(
            Student.id == payload.student_id, Student.org_id == org_id, Student.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    # Validate optional links belong to this org (reuse the org-scoped loaders,
    # which 404 on a missing/foreign id) so an intervention can't reference
    # another org's exam/attempt or a non-existent one.
    if payload.exam_id:
        await _get_exam_or_404(db, payload.exam_id, org_id)
    if payload.attempt_id:
        await _load_attempt(db, payload.attempt_id, org_id)
    iv = CBTIntervention(
        student_id=payload.student_id, exam_id=payload.exam_id, attempt_id=payload.attempt_id,
        reason=payload.reason, note=payload.note, status=InterventionStatus.OPEN,
        created_by=current_user.id, org_id=org_id,
    )
    db.add(iv)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, org_id, actor=current_user,
        resource_type="CBTIntervention", resource_id=iv.id,
        resource_label=f"flagged {student.first_name} {student.last_name}", request=request,
    )
    name = " ".join(p for p in [student.first_name, student.last_name] if p) or student.student_id
    return _intervention_dict(iv, name)


@router.patch("/interventions/{iv_id}", dependencies=[_bank_write])
async def update_intervention(
    iv_id: str,
    payload: InterventionUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org_id = current_user.org_id
    iv = await _load_intervention(db, iv_id, org_id)
    # Teacher-tier can only mutate interventions they can see (R2) — 404 (not 403)
    # to avoid leaking that an out-of-scope intervention exists.
    if not await _intervention_in_scope(db, current_user, iv):
        raise HTTPException(status_code=404, detail="Intervention not found.")
    updates = payload.model_dump(exclude_unset=True)
    if "status" in updates:
        new_status = InterventionStatus(updates["status"])
        iv.status = new_status
        if new_status == InterventionStatus.RESOLVED:
            iv.resolved_by = current_user.id
            iv.resolved_at = datetime.now(timezone.utc)
        else:
            iv.resolved_by = None
            iv.resolved_at = None
    if "note" in updates:
        iv.note = updates["note"]
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, org_id, actor=current_user,
        resource_type="CBTIntervention", resource_id=iv.id,
        resource_label=f"intervention -> {iv.status.value if hasattr(iv.status, 'value') else iv.status}", request=request,
    )
    names = await _cbt_student_names(db, org_id, {iv.student_id})
    return _intervention_dict(iv, names.get(iv.student_id))


async def _get_or_create_settings(db: AsyncSession, org_id: str) -> CBTSettings:
    s = (await db.execute(
        select(CBTSettings).where(CBTSettings.org_id == org_id)
    )).scalar_one_or_none()
    if not s:
        s = CBTSettings(org_id=org_id, default_duration_minutes=60, default_pass_percentage=50, shuffle_default=False)
        db.add(s)
        await db.flush()
    return s


def _settings_dict(s: CBTSettings) -> dict:
    return {
        "default_duration_minutes": int(s.default_duration_minutes or 60),
        "default_pass_percentage": int(s.default_pass_percentage or 50),
        "shuffle_default": bool(s.shuffle_default),
        "instructions": s.instructions,
    }


@router.get("/settings", dependencies=[_bank_read])
async def get_cbt_settings(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return _settings_dict(await _get_or_create_settings(db, current_user.org_id))


@router.put("/settings", dependencies=[_bank_write])
async def update_cbt_settings(
    payload: CBTSettingsUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org_id = current_user.org_id
    s = await _get_or_create_settings(db, org_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, org_id, actor=current_user,
        resource_type="CBTSettings", resource_id=s.id, resource_label="updated CBT defaults", request=request,
    )
    return _settings_dict(s)
