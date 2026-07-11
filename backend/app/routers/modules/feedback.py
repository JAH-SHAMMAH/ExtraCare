"""
Feedback Router
================
Student-to-school feedback channel with an admin resolution workflow.

Design notes:
  - Any authenticated user of the school module can submit feedback
    (school:read suffices — this is a self-service endpoint that writes a
    user's own message, not an administrative write).
  - Only users with school:write (typically teachers/admins) can resolve and
    respond to feedback. This mirrors how business:leave handles self-service
    submission vs. managerial review.

RBAC:
  - school:read   → submit, list own
  - school:write  → list all, resolve, respond
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.modules.school import (
    StudentFeedback, Student,
    FeedbackSettings, DailyReport, StudentDailyReport,
)
from app.schemas.school_experience import (
    FeedbackCreate,
    FeedbackResolve,
    FeedbackResponse,
)
from app.schemas.feedback_extras import (
    FeedbackSettingsUpdate, FeedbackSettingsResponse,
    DailyReportCreate, DailyReportUpdate, DailyReportResponse,
    StudentDailyReportCreate, StudentDailyReportUpdate, StudentDailyReportResponse,
)
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker
from app.services.audit_service import log_action
from app.models.audit import AuditAction
from app.routers.modules.school import _ensure_student_visible

router = APIRouter(
    prefix="/feedback",
    tags=["Feedback"],
    dependencies=[Depends(require_role_module("school"))],
)

_can_read = Depends(PermissionChecker("school:feedback:read"))
_can_write = Depends(PermissionChecker("school:feedback:write"))
# Daily reports are staff surfaces grouped under Feedback in the reference; they
# ride the broad school scopes so students/parents (narrow scopes) are excluded.
_staff_read = Depends(PermissionChecker("school:read"))
_staff_write = Depends(PermissionChecker("school:write"))
# A single student's daily reports are parent/student-visible, ownership-scoped —
# the same "reports" visibility parents already have for the report card.
_reports_read = Depends(PermissionChecker("school:reports:read"))


@router.post("", status_code=201, dependencies=[_can_read])
async def submit_feedback(
    payload: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    feedback = StudentFeedback(
        **payload.model_dump(),
        submitted_by=current_user.id,
        org_id=current_user.org_id,
    )
    db.add(feedback)
    await db.flush()
    return FeedbackResponse.model_validate(feedback).model_dump()


@router.get("", dependencies=[_can_read])
async def list_feedback(
    mine: bool = False,
    category: str | None = None,
    resolved: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(StudentFeedback).where(StudentFeedback.org_id == current_user.org_id)

    # Self-service: students see only their own submissions. Admin listing is
    # gated behind school:write (see list_all below) — keeping this endpoint
    # scoped prevents students from reading each other's feedback.
    if mine or not current_user.has_permission("school:write"):
        query = query.where(StudentFeedback.submitted_by == current_user.id)

    if category:
        query = query.where(StudentFeedback.category == category)
    if resolved is not None:
        query = query.where(StudentFeedback.is_resolved == resolved)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(StudentFeedback.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()

    # Anonymous submissions hide the submitter id for non-admin viewers.
    response_items = []
    for f in items:
        data = FeedbackResponse.model_validate(f).model_dump()
        if f.is_anonymous and not current_user.has_permission("school:write"):
            data["submitted_by"] = None
        response_items.append(data)

    return {
        "items": response_items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/{feedback_id}/resolve", dependencies=[_can_write])
async def resolve_feedback(
    feedback_id: str,
    payload: FeedbackResolve,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(StudentFeedback).where(
            StudentFeedback.id == feedback_id,
            StudentFeedback.org_id == current_user.org_id,
        )
    )
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found.")

    feedback.admin_response = payload.admin_response
    feedback.is_resolved = payload.is_resolved
    feedback.responded_by = current_user.id
    feedback.responded_at = datetime.now(timezone.utc)
    await db.flush()
    return FeedbackResponse.model_validate(feedback).model_dump()


# ── Helpers for the extra surfaces ───────────────────────────────────────────

async def _user_names(db: AsyncSession, org_id: str, ids: set[str]) -> dict[str, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(
        select(User.id, User.full_name).where(User.org_id == org_id, User.id.in_(ids))
    )).all()
    return {r[0]: r[1] for r in rows}


async def _student_names(db: AsyncSession, org_id: str, ids: set[str]) -> dict[str, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(
        select(Student.id, Student.first_name, Student.last_name)
        .where(Student.org_id == org_id, Student.id.in_(ids))
    )).all()
    return {r[0]: f"{r[1]} {r[2]}".strip() for r in rows}


async def _load(db: AsyncSession, model, obj_id: str, org_id: str, label: str):
    obj = (await db.execute(
        select(model).where(model.id == obj_id, model.org_id == org_id)
    )).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail=f"{label} not found.")
    return obj


# ── Feedback settings ────────────────────────────────────────────────────────

async def _get_settings(db: AsyncSession, org_id: str) -> FeedbackSettings:
    s = (await db.execute(select(FeedbackSettings).where(FeedbackSettings.org_id == org_id))).scalar_one_or_none()
    if s is None:
        s = FeedbackSettings(org_id=org_id)
        db.add(s)
        await db.flush()
    return s


@router.get("/settings", dependencies=[_can_read])
async def get_feedback_settings(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return FeedbackSettingsResponse.model_validate(await _get_settings(db, current_user.org_id)).model_dump()


@router.put("/settings", dependencies=[_can_write])
async def update_feedback_settings(payload: FeedbackSettingsUpdate, request: Request = None,
                                   db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_settings(db, current_user.org_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    await db.flush()
    await log_action(db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
                     resource_type="FeedbackSettings", resource_id=s.id, resource_label="feedback settings", request=request)
    return FeedbackSettingsResponse.model_validate(s).model_dump()


# ── Daily reports (staff) ────────────────────────────────────────────────────

def _daily_dict(r: DailyReport, author_name: str | None) -> dict:
    return DailyReportResponse(
        id=r.id, author_id=r.author_id, author_name=author_name, report_date=r.report_date,
        class_id=r.class_id, summary=r.summary, highlights=r.highlights, challenges=r.challenges,
        created_at=r.created_at, org_id=r.org_id,
    ).model_dump()


@router.get("/daily-reports", dependencies=[_staff_read])
async def list_daily_reports(mine: bool = False, author_id: str | None = None,
                             db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(DailyReport).where(DailyReport.org_id == current_user.org_id)
    if mine:
        q = q.where(DailyReport.author_id == current_user.id)
    elif author_id:
        q = q.where(DailyReport.author_id == author_id)
    rows = (await db.execute(q.order_by(DailyReport.report_date.desc()))).scalars().all()
    names = await _user_names(db, current_user.org_id, {r.author_id for r in rows})
    return {"items": [_daily_dict(r, names.get(r.author_id)) for r in rows]}


@router.post("/daily-reports", status_code=201, dependencies=[_staff_write])
async def create_daily_report(payload: DailyReportCreate, request: Request = None,
                              db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = DailyReport(**payload.model_dump(), author_id=current_user.id, org_id=current_user.org_id)
    db.add(r)
    await db.flush()
    await log_action(db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
                     resource_type="DailyReport", resource_id=r.id, resource_label=f"daily report {r.report_date}", request=request)
    return _daily_dict(r, current_user.full_name)


def _ensure_report_owner(r: DailyReport, user: User) -> None:
    """A daily report is a record: only its author edits/deletes it — with an
    admin override (settings:write) for corrections."""
    if r.author_id != user.id and not user.has_permission("settings:write"):
        raise HTTPException(status_code=403, detail="Only the author can edit or delete this report.")


@router.patch("/daily-reports/{report_id}", dependencies=[_staff_write])
async def update_daily_report(report_id: str, payload: DailyReportUpdate, request: Request = None,
                              db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = await _load(db, DailyReport, report_id, current_user.org_id, "Report")
    _ensure_report_owner(r, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(r, field, value)
    await db.flush()
    names = await _user_names(db, current_user.org_id, {r.author_id})
    return _daily_dict(r, names.get(r.author_id))


@router.delete("/daily-reports/{report_id}", status_code=204, dependencies=[_staff_write])
async def delete_daily_report(report_id: str, request: Request = None,
                              db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = await _load(db, DailyReport, report_id, current_user.org_id, "Report")
    _ensure_report_owner(r, current_user)
    await db.delete(r)
    await log_action(db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
                     resource_type="DailyReport", resource_id=report_id, resource_label="daily report", severity="warning", request=request)


# ── Student daily reports ────────────────────────────────────────────────────

def _student_daily_dict(r: StudentDailyReport, student_name: str | None) -> dict:
    return StudentDailyReportResponse(
        id=r.id, student_id=r.student_id, student_name=student_name, author_id=r.author_id,
        report_date=r.report_date, mood=r.mood, academic=r.academic, behaviour=r.behaviour,
        notes=r.notes, created_at=r.created_at, org_id=r.org_id,
    ).model_dump()


@router.get("/student-daily-reports", dependencies=[_staff_read])
async def list_student_daily_reports(student_id: str | None = None,
                                     db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(StudentDailyReport).where(StudentDailyReport.org_id == current_user.org_id)
    if student_id:
        q = q.where(StudentDailyReport.student_id == student_id)
    rows = (await db.execute(q.order_by(StudentDailyReport.report_date.desc()))).scalars().all()
    names = await _student_names(db, current_user.org_id, {r.student_id for r in rows})
    return {"items": [_student_daily_dict(r, names.get(r.student_id)) for r in rows]}


@router.get("/student-daily-reports/student/{student_id}", dependencies=[_reports_read])
async def list_student_daily_reports_for_student(
    student_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    """One student's daily reports, ownership-scoped: a parent/student sees only
    their own (via _ensure_student_visible), staff (students:read) see any. Mirrors
    how the report card is exposed to parents."""
    await _ensure_student_visible(db, current_user, student_id)
    rows = (await db.execute(
        select(StudentDailyReport).where(
            StudentDailyReport.student_id == student_id, StudentDailyReport.org_id == current_user.org_id)
        .order_by(StudentDailyReport.report_date.desc())
    )).scalars().all()
    names = await _student_names(db, current_user.org_id, {student_id})
    return {"items": [_student_daily_dict(r, names.get(student_id)) for r in rows]}


@router.post("/student-daily-reports", status_code=201, dependencies=[_staff_write])
async def create_student_daily_report(payload: StudentDailyReportCreate, request: Request = None,
                                      db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    await _load(db, Student, payload.student_id, current_user.org_id, "Student")
    r = StudentDailyReport(**payload.model_dump(), author_id=current_user.id, org_id=current_user.org_id)
    db.add(r)
    await db.flush()
    names = await _student_names(db, current_user.org_id, {r.student_id})
    await log_action(db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
                     resource_type="StudentDailyReport", resource_id=r.id, resource_label=f"student daily report {r.report_date}", request=request)
    return _student_daily_dict(r, names.get(r.student_id))


@router.patch("/student-daily-reports/{report_id}", dependencies=[_staff_write])
async def update_student_daily_report(report_id: str, payload: StudentDailyReportUpdate, request: Request = None,
                                      db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = await _load(db, StudentDailyReport, report_id, current_user.org_id, "Report")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(r, field, value)
    await db.flush()
    names = await _student_names(db, current_user.org_id, {r.student_id})
    return _student_daily_dict(r, names.get(r.student_id))


@router.delete("/student-daily-reports/{report_id}", status_code=204, dependencies=[_staff_write])
async def delete_student_daily_report(report_id: str, request: Request = None,
                                      db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = await _load(db, StudentDailyReport, report_id, current_user.org_id, "Report")
    await db.delete(r)
    await log_action(db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
                     resource_type="StudentDailyReport", resource_id=report_id, resource_label="student daily report", severity="warning", request=request)

# CRM: no standalone model — the "CRM" surface is a thin view over Admissions &
# Enquiries (see routers/modules/admissions.py). A parallel CRMContact table was
# removed to avoid two competing prospective-parent enquiry systems.
