"""Admissions & Enrollment router (Batch 2).

One router, prefix ``/enrollment``, covering the student lifecycle:

  /enrollment/applications              GET/POST     — admission enquiries/apps
  /enrollment/applications/{id}         PATCH/DELETE
  /enrollment/applications/{id}/admit   POST         — convert → Student
  /enrollment/entrance-exams            GET/POST
  /enrollment/entrance-exams/{id}       PATCH/DELETE
  /enrollment/entrance-exams/{id}/results  GET/POST
  /enrollment/exam-results/{id}         PATCH/DELETE
  /enrollment/promotions                GET/POST     — bulk class roll-over
  /enrollment/transfers                 GET/POST
  /enrollment/transfers/{id}            PATCH

RBAC
----
  Applications + entrance exams → school:admissions:read / :write
  Admit / promotions / transfers (touch the roster) → school:students:read / :write
Trusted staff reach these via the broad school:read/write hierarchy; students/
parents (narrow scopes) never do. Every query is pinned to the caller's org_id.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.modules.school import Student, SchoolClass
from app.models.modules.admissions import (
    AdmissionApplication, EntranceExam, EntranceExamResult,
    PromotionRecord, TransferRecord, StudentAuthorizedPickup,
)
from app.schemas.admissions import (
    AdmissionApplicationCreate, AdmissionApplicationUpdate, AdmissionApplicationResponse,
    AdmissionApplicationListResponse, AdmitRequest,
    EntranceExamCreate, EntranceExamUpdate, EntranceExamResponse, EntranceExamListResponse,
    EntranceExamResultCreate, EntranceExamResultUpdate, EntranceExamResultResponse,
    PromotionCreate, PromotionRecordResponse, PromotionListResponse,
    PromotionPreviewItem, PromotionPreviewResponse, PromotionRevertResponse,
    TransferCreate, TransferUpdate, TransferRecordResponse, TransferListResponse,
    AuthorizedPickupCreate, AuthorizedPickupUpdate, AuthorizedPickupResponse,
    AuthorizedPickupListResponse,
    ADMISSION_STATUSES, APPOINTMENT_STATUSES, EXAM_STATUSES, EXAM_OUTCOMES,
    PROMOTION_OUTCOMES, TRANSFER_TYPES, TRANSFER_STATUSES,
)
from app.services.audit_service import log_action
from app.models.audit import AuditAction

router = APIRouter(
    prefix="/enrollment",
    tags=["Admissions & Enrollment"],
    dependencies=[Depends(require_role_module("school"))],
)

_adm_read = Depends(PermissionChecker("school:admissions:read"))
_adm_write = Depends(PermissionChecker("school:admissions:write"))
_stu_read = Depends(PermissionChecker("school:students:read"))
_stu_write = Depends(PermissionChecker("school:students:write"))


# ── shared helpers ────────────────────────────────────────────────────────────

async def _class_names(db: AsyncSession, org_id: str, ids: set[str]) -> dict[str, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(
        select(SchoolClass.id, SchoolClass.name).where(
            SchoolClass.org_id == org_id, SchoolClass.id.in_(ids),
        )
    )).all()
    return {r.id: r.name for r in rows}


async def _student_names(db: AsyncSession, org_id: str, ids: set[str]) -> dict[str, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(
        select(Student.id, Student.first_name, Student.last_name).where(
            Student.org_id == org_id, Student.id.in_(ids),
        )
    )).all()
    return {r.id: f"{r.first_name} {r.last_name}".strip() for r in rows}


async def _require_class(db: AsyncSession, org_id: str, class_id: str) -> SchoolClass:
    cls = (await db.execute(
        select(SchoolClass).where(SchoolClass.id == class_id, SchoolClass.org_id == org_id)
    )).scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="class not found in your organisation.")
    return cls


async def _require_student(db: AsyncSession, org_id: str, student_id: str) -> Student:
    s = (await db.execute(
        select(Student).where(
            Student.id == student_id, Student.org_id == org_id, Student.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="student not found in your organisation.")
    return s


# ── Admission Applications ─────────────────────────────────────────────────────

def _application_response(a: AdmissionApplication, class_name: str | None) -> AdmissionApplicationResponse:
    return AdmissionApplicationResponse(
        id=a.id, first_name=a.first_name, last_name=a.last_name,
        full_name=f"{a.first_name} {a.last_name}".strip(),
        date_of_birth=a.date_of_birth, gender=a.gender,
        guardian_name=a.guardian_name, guardian_phone=a.guardian_phone, guardian_email=a.guardian_email,
        applying_for_class_id=a.applying_for_class_id, applying_for_class_name=class_name,
        applying_for_level=a.applying_for_level, source=a.source, status=a.status, notes=a.notes,
        appointment_at=a.appointment_at, appointment_status=a.appointment_status or "none",
        appointment_notes=a.appointment_notes,
        admitted_student_id=a.admitted_student_id,
        created_at=a.created_at, updated_at=a.updated_at, org_id=a.org_id,
    )


async def _load_application(db: AsyncSession, app_id: str, org_id: str) -> AdmissionApplication:
    a = (await db.execute(
        select(AdmissionApplication).where(
            AdmissionApplication.id == app_id, AdmissionApplication.org_id == org_id,
            AdmissionApplication.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Application not found.")
    return a


@router.get("/applications", response_model=AdmissionApplicationListResponse, dependencies=[_adm_read])
async def list_applications(
    status: str | None = Query(default=None),
    appointment_status: str | None = None,  # none|scheduled|attended|no_show — Enquiry Appointment view
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = select(AdmissionApplication).where(
        AdmissionApplication.org_id == current_user.org_id,
        AdmissionApplication.is_deleted == False,  # noqa: E712
    )
    if status:
        base = base.where(AdmissionApplication.status == status)
    if appointment_status:
        base = base.where(AdmissionApplication.appointment_status == appointment_status)
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        base = base.where(or_(
            func.lower(AdmissionApplication.first_name).like(term),
            func.lower(AdmissionApplication.last_name).like(term),
            func.lower(AdmissionApplication.guardian_name).like(term),
        ))
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(AdmissionApplication.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    names = await _class_names(db, current_user.org_id, {r.applying_for_class_id for r in rows})
    return AdmissionApplicationListResponse(
        items=[_application_response(r, names.get(r.applying_for_class_id)) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/applications", response_model=AdmissionApplicationResponse, status_code=201, dependencies=[_adm_write])
async def create_application(
    payload: AdmissionApplicationCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.status not in ADMISSION_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(ADMISSION_STATUSES)}")
    if payload.applying_for_class_id:
        await _require_class(db, current_user.org_id, payload.applying_for_class_id)
    values = payload.model_dump()
    # appointment_status is NOT NULL with a server default — drop an omitted/None
    # value so the default applies rather than forcing NULL. Validate if supplied.
    if values.get("appointment_status") is None:
        values.pop("appointment_status", None)
    elif values["appointment_status"] not in APPOINTMENT_STATUSES:
        raise HTTPException(status_code=422, detail=f"appointment_status must be one of {sorted(APPOINTMENT_STATUSES)}")
    a = AdmissionApplication(
        **values, org_id=current_user.org_id, created_by=current_user.id,
    )
    db.add(a)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="AdmissionApplication", resource_id=a.id,
        resource_label=f"application {a.first_name} {a.last_name}",
        metadata={"status": a.status}, request=request,
    )
    name = (await _class_names(db, current_user.org_id, {a.applying_for_class_id})).get(a.applying_for_class_id)
    return _application_response(a, name)


@router.patch("/applications/{app_id}", response_model=AdmissionApplicationResponse, dependencies=[_adm_write])
async def update_application(
    app_id: str,
    payload: AdmissionApplicationUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    a = await _load_application(db, app_id, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in ADMISSION_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(ADMISSION_STATUSES)}")
    # Guard the NOT NULL column: a client clearing the appointment should send
    # "none", never null. Reject anything outside the allowed set.
    if "appointment_status" in data and data["appointment_status"] not in APPOINTMENT_STATUSES:
        raise HTTPException(status_code=422, detail=f"appointment_status must be one of {sorted(APPOINTMENT_STATUSES)}")
    if data.get("applying_for_class_id"):
        await _require_class(db, current_user.org_id, data["applying_for_class_id"])
    for field, value in data.items():
        setattr(a, field, value)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="AdmissionApplication", resource_id=a.id,
        resource_label=f"application {a.first_name} {a.last_name}", request=request,
    )
    name = (await _class_names(db, current_user.org_id, {a.applying_for_class_id})).get(a.applying_for_class_id)
    return _application_response(a, name)


@router.delete("/applications/{app_id}", status_code=204, dependencies=[_adm_write])
async def delete_application(
    app_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    a = await _load_application(db, app_id, current_user.org_id)
    a.is_deleted = True
    a.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
        resource_type="AdmissionApplication", resource_id=a.id,
        resource_label="application", severity="warning", request=request,
    )


@router.post("/applications/{app_id}/admit", response_model=AdmissionApplicationResponse, dependencies=[_stu_write])
async def admit_application(
    app_id: str,
    payload: AdmitRequest = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Convert an application into a Student on the roster (idempotent-safe)."""
    payload = payload or AdmitRequest()
    a = await _load_application(db, app_id, current_user.org_id)
    if a.admitted_student_id:
        raise HTTPException(status_code=409, detail="This application has already been admitted.")

    class_id = payload.class_id or a.applying_for_class_id
    if class_id:
        await _require_class(db, current_user.org_id, class_id)

    student_code = (payload.student_id or f"ADM-{uuid.uuid4().hex[:8].upper()}").strip()
    student = Student(
        student_id=student_code,
        first_name=a.first_name,
        last_name=a.last_name,
        date_of_birth=a.date_of_birth,
        gender=a.gender,
        guardian_name=a.guardian_name,
        guardian_phone=a.guardian_phone,
        guardian_email=a.guardian_email,
        class_id=class_id,
        admission_date=payload.admission_date or datetime.now(timezone.utc).date(),
        is_active=True,
        org_id=current_user.org_id,
    )
    db.add(student)
    await db.flush()

    a.admitted_student_id = student.id
    a.status = "admitted"
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="Student", resource_id=student.id,
        resource_label=f"admitted {a.first_name} {a.last_name}",
        metadata={"application_id": a.id, "student_code": student_code}, request=request,
    )
    name = (await _class_names(db, current_user.org_id, {a.applying_for_class_id})).get(a.applying_for_class_id)
    return _application_response(a, name)


# ── Entrance Exams ─────────────────────────────────────────────────────────────

def _exam_response(e: EntranceExam, result_count: int = 0) -> EntranceExamResponse:
    return EntranceExamResponse(
        id=e.id, title=e.title, exam_date=e.exam_date, subject=e.subject,
        max_score=e.max_score, status=e.status, notes=e.notes,
        result_count=result_count, created_at=e.created_at, org_id=e.org_id,
    )


async def _load_exam(db: AsyncSession, exam_id: str, org_id: str) -> EntranceExam:
    e = (await db.execute(
        select(EntranceExam).where(
            EntranceExam.id == exam_id, EntranceExam.org_id == org_id,
            EntranceExam.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="Entrance exam not found.")
    return e


@router.get("/entrance-exams", response_model=EntranceExamListResponse, dependencies=[_adm_read])
async def list_entrance_exams(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = select(EntranceExam).where(
        EntranceExam.org_id == current_user.org_id, EntranceExam.is_deleted == False,  # noqa: E712
    )
    if status:
        base = base.where(EntranceExam.status == status)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(EntranceExam.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    # result counts in one grouped query
    counts: dict[str, int] = {}
    if rows:
        cnt_rows = (await db.execute(
            select(EntranceExamResult.exam_id, func.count(EntranceExamResult.id))
            .where(EntranceExamResult.exam_id.in_([r.id for r in rows]))
            .group_by(EntranceExamResult.exam_id)
        )).all()
        counts = {eid: c for eid, c in cnt_rows}
    return EntranceExamListResponse(
        items=[_exam_response(r, counts.get(r.id, 0)) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/entrance-exams", response_model=EntranceExamResponse, status_code=201, dependencies=[_adm_write])
async def create_entrance_exam(
    payload: EntranceExamCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.status not in EXAM_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(EXAM_STATUSES)}")
    e = EntranceExam(**payload.model_dump(), org_id=current_user.org_id, created_by=current_user.id)
    db.add(e)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="EntranceExam", resource_id=e.id, resource_label=f"entrance exam {e.title}",
        request=request,
    )
    return _exam_response(e, 0)


@router.patch("/entrance-exams/{exam_id}", response_model=EntranceExamResponse, dependencies=[_adm_write])
async def update_entrance_exam(
    exam_id: str,
    payload: EntranceExamUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    e = await _load_exam(db, exam_id, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in EXAM_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(EXAM_STATUSES)}")
    for field, value in data.items():
        setattr(e, field, value)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="EntranceExam", resource_id=e.id, resource_label=f"entrance exam {e.title}",
        request=request,
    )
    return _exam_response(e)


@router.delete("/entrance-exams/{exam_id}", status_code=204, dependencies=[_adm_write])
async def delete_entrance_exam(
    exam_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    e = await _load_exam(db, exam_id, current_user.org_id)
    e.is_deleted = True
    e.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
        resource_type="EntranceExam", resource_id=e.id, resource_label="entrance exam",
        severity="warning", request=request,
    )


def _result_response(r: EntranceExamResult) -> EntranceExamResultResponse:
    return EntranceExamResultResponse(
        id=r.id, exam_id=r.exam_id, application_id=r.application_id,
        candidate_name=r.candidate_name, score=r.score, outcome=r.outcome,
        remark=r.remark, created_at=r.created_at, org_id=r.org_id,
    )


@router.get("/entrance-exams/{exam_id}/results", response_model=list[EntranceExamResultResponse], dependencies=[_adm_read])
async def list_exam_results(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _load_exam(db, exam_id, current_user.org_id)
    rows = (await db.execute(
        select(EntranceExamResult).where(
            EntranceExamResult.exam_id == exam_id,
            EntranceExamResult.org_id == current_user.org_id,
        ).order_by(EntranceExamResult.score.desc().nullslast(), EntranceExamResult.candidate_name)
    )).scalars().all()
    return [_result_response(r) for r in rows]


@router.post("/entrance-exams/{exam_id}/results", response_model=EntranceExamResultResponse, status_code=201, dependencies=[_adm_write])
async def add_exam_result(
    exam_id: str,
    payload: EntranceExamResultCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    exam = await _load_exam(db, exam_id, current_user.org_id)
    if payload.outcome not in EXAM_OUTCOMES:
        raise HTTPException(status_code=422, detail=f"outcome must be one of {sorted(EXAM_OUTCOMES)}")
    if payload.score is not None and payload.score > exam.max_score:
        raise HTTPException(status_code=422, detail=f"score cannot exceed the exam max of {exam.max_score}.")
    if payload.application_id:
        await _load_application(db, payload.application_id, current_user.org_id)
    r = EntranceExamResult(
        exam_id=exam.id, application_id=payload.application_id, candidate_name=payload.candidate_name,
        score=payload.score, outcome=payload.outcome, remark=payload.remark, org_id=current_user.org_id,
    )
    db.add(r)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="EntranceExamResult", resource_id=r.id,
        resource_label=f"result for {r.candidate_name}", request=request,
    )
    return _result_response(r)


async def _load_result(db: AsyncSession, result_id: str, org_id: str) -> EntranceExamResult:
    r = (await db.execute(
        select(EntranceExamResult).where(
            EntranceExamResult.id == result_id, EntranceExamResult.org_id == org_id,
        )
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Result not found.")
    return r


@router.patch("/exam-results/{result_id}", response_model=EntranceExamResultResponse, dependencies=[_adm_write])
async def update_exam_result(
    result_id: str,
    payload: EntranceExamResultUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    r = await _load_result(db, result_id, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    if "outcome" in data and data["outcome"] not in EXAM_OUTCOMES:
        raise HTTPException(status_code=422, detail=f"outcome must be one of {sorted(EXAM_OUTCOMES)}")
    for field, value in data.items():
        setattr(r, field, value)
    await db.flush()
    return _result_response(r)


@router.delete("/exam-results/{result_id}", status_code=204, dependencies=[_adm_write])
async def delete_exam_result(
    result_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    r = await _load_result(db, result_id, current_user.org_id)
    await db.delete(r)


# ── Promotions ─────────────────────────────────────────────────────────────────

def _promotion_response(p: PromotionRecord, student_name: str | None, names: dict[str, str]) -> PromotionRecordResponse:
    return PromotionRecordResponse(
        id=p.id, batch_id=p.batch_id, student_id=p.student_id, student_name=student_name,
        from_class_id=p.from_class_id, from_class_name=names.get(p.from_class_id),
        to_class_id=p.to_class_id, to_class_name=names.get(p.to_class_id),
        academic_year=p.academic_year, outcome=p.outcome, reverted_at=p.reverted_at,
        created_at=p.created_at, org_id=p.org_id,
    )


async def _load_promotion_students(db: AsyncSession, org_id: str, student_ids: list[str]) -> list[Student]:
    """Load the selected students (de-duped, order preserved). Raises 404 if any
    id is unknown in the org — the whole run is rejected so nothing half-applies."""
    ordered = list(dict.fromkeys(student_ids))
    rows = (await db.execute(
        select(Student).where(
            Student.org_id == org_id, Student.id.in_(ordered), Student.is_deleted == False,  # noqa: E712
        )
    )).scalars().all()
    by_id = {s.id: s for s in rows}
    missing = [sid for sid in ordered if sid not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"student(s) not found in your organisation: {missing}")
    return [by_id[sid] for sid in ordered]


@router.get("/promotions", response_model=PromotionListResponse, dependencies=[_stu_read])
async def list_promotions(
    student_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = select(PromotionRecord).where(PromotionRecord.org_id == current_user.org_id)
    if student_id:
        base = base.where(PromotionRecord.student_id == student_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(PromotionRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    class_names = await _class_names(
        db, current_user.org_id,
        {r.from_class_id for r in rows} | {r.to_class_id for r in rows},
    )
    student_names = await _student_names(db, current_user.org_id, {r.student_id for r in rows})
    return PromotionListResponse(
        items=[_promotion_response(r, student_names.get(r.student_id), class_names) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/promotions/preview", response_model=PromotionPreviewResponse, dependencies=[_stu_read])
async def preview_promotions(
    payload: PromotionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Dry-run: show exactly who would be affected (and who'd be skipped, with the
    reason) WITHOUT writing anything. Lets staff confirm a mass run before commit."""
    if payload.outcome not in PROMOTION_OUTCOMES:
        raise HTTPException(status_code=422, detail=f"outcome must be one of {sorted(PROMOTION_OUTCOMES)}")
    to_class_name = None
    if payload.to_class_id:
        to_class_name = (await _require_class(db, current_user.org_id, payload.to_class_id)).name

    students = await _load_promotion_students(db, current_user.org_id, payload.student_ids)
    class_names = await _class_names(db, current_user.org_id, {s.class_id for s in students})
    items: list[PromotionPreviewItem] = []
    eligible = skipped = 0
    for s in students:
        ok = bool(s.is_active)  # inactive students (graduated/transferred) are ineligible
        eligible, skipped = (eligible + 1, skipped) if ok else (eligible, skipped + 1)
        items.append(PromotionPreviewItem(
            student_id=s.id, student_name=f"{s.first_name} {s.last_name}".strip(),
            from_class_id=s.class_id, from_class_name=class_names.get(s.class_id),
            eligible=ok, reason=None if ok else "student is not on the active roster",
        ))
    return PromotionPreviewResponse(
        outcome=payload.outcome, to_class_id=payload.to_class_id, to_class_name=to_class_name,
        eligible_count=eligible, skipped_count=skipped, items=items,
    )


@router.post("/promotions", response_model=list[PromotionRecordResponse], status_code=201, dependencies=[_stu_write])
async def create_promotions(
    payload: PromotionCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Bulk class roll-over. Validate-all-then-apply: every student is loaded and
    checked BEFORE any mutation, so a bad/ineligible id rejects the whole run with
    nothing half-applied (atomicity). Inactive students are refused (idempotency —
    a graduated/transferred student can't be re-processed). Each roster change is
    written to the immutable audit log with before/after state, and the run shares
    one ``batch_id`` so it can be reverted as a unit (reversibility)."""
    if payload.outcome not in PROMOTION_OUTCOMES:
        raise HTTPException(status_code=422, detail=f"outcome must be one of {sorted(PROMOTION_OUTCOMES)}")
    if payload.outcome == "promoted" and not payload.to_class_id:
        raise HTTPException(status_code=422, detail="to_class_id is required when outcome is 'promoted'.")
    if payload.to_class_id:
        await _require_class(db, current_user.org_id, payload.to_class_id)

    # ── Phase 1: load + validate EVERYTHING before mutating anything ──────────
    students = await _load_promotion_students(db, current_user.org_id, payload.student_ids)
    inactive = [f"{s.first_name} {s.last_name}".strip() for s in students if not s.is_active]
    if inactive:
        raise HTTPException(
            status_code=409,
            detail=f"cannot promote inactive (graduated/transferred) students: {inactive}",
        )

    # ── Phase 2: apply — no validation past this point, so no partial state ───
    batch_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    created: list[PromotionRecord] = []
    audit_entries: list[tuple] = []
    for student in students:
        from_class_id = student.class_id
        prev_active = bool(student.is_active)
        rec = PromotionRecord(
            batch_id=batch_id, student_id=student.id, from_class_id=from_class_id,
            to_class_id=payload.to_class_id, academic_year=payload.academic_year,
            outcome=payload.outcome, prev_is_active=prev_active,
            promoted_by=current_user.id, org_id=current_user.org_id,
        )
        db.add(rec)
        if payload.outcome == "promoted":
            student.class_id = payload.to_class_id
        elif payload.outcome == "graduated":
            student.is_active = False
            student.class_id = None
            student.graduation_date = now.date()
        # "repeated" leaves the student in place; the record captures the decision.
        audit_entries.append((
            student.id, from_class_id, prev_active, student.class_id, bool(student.is_active),
        ))
        created.append(rec)

    await db.flush()

    # ── Phase 3: immutable per-student audit (who/when/before→after) ──────────
    for sid, old_class, old_active, new_class, new_active in audit_entries:
        await log_action(
            db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
            resource_type="Student", resource_id=sid,
            resource_label=f"promotion ({payload.outcome})",
            old_values={"class_id": old_class, "is_active": old_active},
            new_values={"class_id": new_class, "is_active": new_active},
            metadata={"batch_id": batch_id, "outcome": payload.outcome},
            request=request,
        )

    class_names = await _class_names(
        db, current_user.org_id,
        {r.from_class_id for r in created} | {r.to_class_id for r in created},
    )
    student_names = await _student_names(db, current_user.org_id, {r.student_id for r in created})
    return [_promotion_response(r, student_names.get(r.student_id), class_names) for r in created]


@router.post("/promotions/{batch_id}/revert", response_model=PromotionRevertResponse, dependencies=[_stu_write])
async def revert_promotion_batch(
    batch_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Undo a whole promotion run: restore each student's class + active flag to
    its pre-run snapshot and mark the records reverted. Idempotent — a batch with
    no un-reverted records returns 404."""
    records = (await db.execute(
        select(PromotionRecord).where(
            PromotionRecord.batch_id == batch_id,
            PromotionRecord.org_id == current_user.org_id,
            PromotionRecord.reverted_at.is_(None),
        )
    )).scalars().all()
    if not records:
        raise HTTPException(status_code=404, detail="No reversible promotion run found for that batch.")

    now = datetime.now(timezone.utc)
    student_rows = {
        s.id: s for s in (await db.execute(
            select(Student).where(
                Student.org_id == current_user.org_id,
                Student.id.in_([r.student_id for r in records]),
            )
        )).scalars().all()
    }
    for rec in records:
        student = student_rows.get(rec.student_id)
        if student is not None:
            old_class, old_active = student.class_id, bool(student.is_active)
            student.class_id = rec.from_class_id
            student.is_active = rec.prev_is_active
            if rec.outcome == "graduated" and rec.prev_is_active:
                student.graduation_date = None
            await log_action(
                db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
                resource_type="Student", resource_id=student.id,
                resource_label=f"revert promotion ({rec.outcome})",
                old_values={"class_id": old_class, "is_active": old_active},
                new_values={"class_id": student.class_id, "is_active": bool(student.is_active)},
                metadata={"batch_id": batch_id, "reverted": True}, request=request,
            )
        rec.reverted_at = now
    await db.flush()
    return PromotionRevertResponse(batch_id=batch_id, reverted=len(records))


# ── Transfers ──────────────────────────────────────────────────────────────────

def _transfer_response(t: TransferRecord, student_name: str | None) -> TransferRecordResponse:
    return TransferRecordResponse(
        id=t.id, student_id=t.student_id, student_name=student_name,
        transfer_type=t.transfer_type, destination_school=t.destination_school,
        reason=t.reason, transfer_date=t.transfer_date, status=t.status,
        created_at=t.created_at, org_id=t.org_id,
    )


async def _load_transfer(db: AsyncSession, transfer_id: str, org_id: str) -> TransferRecord:
    t = (await db.execute(
        select(TransferRecord).where(
            TransferRecord.id == transfer_id, TransferRecord.org_id == org_id,
        )
    )).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Transfer not found.")
    return t


@router.get("/transfers", response_model=TransferListResponse, dependencies=[_stu_read])
async def list_transfers(
    status: str | None = Query(default=None),
    transfer_type: str | None = None,  # transfer_out | withdrawal
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = select(TransferRecord).where(TransferRecord.org_id == current_user.org_id)
    if status:
        base = base.where(TransferRecord.status == status)
    # Powers the Withdrawal List view — filters to type=withdrawal (or transfer_out).
    if transfer_type:
        base = base.where(TransferRecord.transfer_type == transfer_type)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(TransferRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    names = await _student_names(db, current_user.org_id, {r.student_id for r in rows})
    return TransferListResponse(
        items=[_transfer_response(r, names.get(r.student_id)) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/transfers", response_model=TransferRecordResponse, status_code=201, dependencies=[_stu_write])
async def create_transfer(
    payload: TransferCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.transfer_type not in TRANSFER_TYPES:
        raise HTTPException(status_code=422, detail=f"transfer_type must be one of {sorted(TRANSFER_TYPES)}")
    if payload.status not in TRANSFER_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(TRANSFER_STATUSES)}")
    student = await _require_student(db, current_user.org_id, payload.student_id)
    # Idempotency: a student already off the active roster can't be transferred
    # again — prevents double-processing the same departure.
    if not student.is_active:
        raise HTTPException(status_code=409, detail="student is already off the active roster.")
    prev_active = bool(student.is_active)
    t = TransferRecord(
        student_id=student.id, transfer_type=payload.transfer_type,
        destination_school=payload.destination_school, reason=payload.reason,
        transfer_date=payload.transfer_date, status=payload.status,
        processed_by=current_user.id, org_id=current_user.org_id,
    )
    db.add(t)
    # A completed transfer removes the student from the active roster.
    if payload.status == "completed":
        student.is_active = False
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="TransferRecord", resource_id=t.id,
        resource_label=f"{t.transfer_type} for student {student.id}",
        old_values={"is_active": prev_active},
        new_values={"is_active": bool(student.is_active)},
        metadata={"status": t.status, "student_id": student.id}, request=request,
    )
    name = (await _student_names(db, current_user.org_id, {student.id})).get(student.id)
    return _transfer_response(t, name)


@router.patch("/transfers/{transfer_id}", response_model=TransferRecordResponse, dependencies=[_stu_write])
async def update_transfer(
    transfer_id: str,
    payload: TransferUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    t = await _load_transfer(db, transfer_id, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    if "transfer_type" in data and data["transfer_type"] not in TRANSFER_TYPES:
        raise HTTPException(status_code=422, detail=f"transfer_type must be one of {sorted(TRANSFER_TYPES)}")
    if "status" in data and data["status"] not in TRANSFER_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(TRANSFER_STATUSES)}")

    was_completed = t.status == "completed"
    for field, value in data.items():
        setattr(t, field, value)

    # Deactivate the student only on the TRANSITION into completed — re-saving an
    # already-completed transfer is a no-op for the roster (no double-apply).
    old_active = new_active = None
    if data.get("status") == "completed" and not was_completed:
        student = await _require_student(db, current_user.org_id, t.student_id)
        old_active, new_active = bool(student.is_active), False
        student.is_active = False
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="TransferRecord", resource_id=t.id, resource_label="transfer",
        old_values={"is_active": old_active} if old_active is not None else None,
        new_values={"is_active": new_active} if new_active is not None else None,
        metadata={"status": t.status, "student_id": t.student_id}, request=request,
    )
    name = (await _student_names(db, current_user.org_id, {t.student_id})).get(t.student_id)
    return _transfer_response(t, name)


# ── Authorized Pickups (Manage Students Pickup) ────────────────────────────────
# Registry of people allowed to collect a student. Registry only — no per-day
# pickup log. Deactivate-not-delete: DELETE flips is_active, keeping the row.

def _pickup_response(p: StudentAuthorizedPickup, student_name: str | None) -> AuthorizedPickupResponse:
    return AuthorizedPickupResponse(
        id=p.id, student_id=p.student_id, student_name=student_name,
        full_name=p.full_name, relationship_type=p.relationship_type,
        phone=p.phone, id_document=p.id_document, photo_url=p.photo_url,
        is_active=bool(p.is_active), created_at=p.created_at, org_id=p.org_id,
    )


async def _load_pickup(db: AsyncSession, pickup_id: str, org_id: str) -> StudentAuthorizedPickup:
    p = (await db.execute(
        select(StudentAuthorizedPickup).where(
            StudentAuthorizedPickup.id == pickup_id, StudentAuthorizedPickup.org_id == org_id,
        )
    )).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="pickup authorisation not found in your organisation.")
    return p


@router.get("/pickups", response_model=AuthorizedPickupListResponse, dependencies=[_stu_read])
async def list_pickups(
    student_id: str | None = None,
    active_only: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = select(StudentAuthorizedPickup).where(StudentAuthorizedPickup.org_id == current_user.org_id)
    if student_id:
        base = base.where(StudentAuthorizedPickup.student_id == student_id)
    if active_only:
        base = base.where(StudentAuthorizedPickup.is_active == True)  # noqa: E712
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(StudentAuthorizedPickup.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    names = await _student_names(db, current_user.org_id, {r.student_id for r in rows})
    return AuthorizedPickupListResponse(
        items=[_pickup_response(r, names.get(r.student_id)) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/pickups", response_model=AuthorizedPickupResponse, status_code=201, dependencies=[_stu_write])
async def create_pickup(
    payload: AuthorizedPickupCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not payload.full_name.strip():
        raise HTTPException(status_code=422, detail="full_name is required.")
    # Validates the student exists in the caller's org (tenant guard).
    student = await _require_student(db, current_user.org_id, payload.student_id)
    p = StudentAuthorizedPickup(
        student_id=student.id, full_name=payload.full_name.strip(),
        relationship_type=payload.relationship_type, phone=payload.phone,
        id_document=payload.id_document, photo_url=payload.photo_url,
        created_by=current_user.id, org_id=current_user.org_id,
    )
    db.add(p)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="StudentAuthorizedPickup", resource_id=p.id,
        resource_label=f"pickup {p.full_name} for student {student.id}",
        metadata={"student_id": student.id}, request=request,
    )
    name = (await _student_names(db, current_user.org_id, {student.id})).get(student.id)
    return _pickup_response(p, name)


@router.patch("/pickups/{pickup_id}", response_model=AuthorizedPickupResponse, dependencies=[_stu_write])
async def update_pickup(
    pickup_id: str,
    payload: AuthorizedPickupUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    p = await _load_pickup(db, pickup_id, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    if "full_name" in data and not (data["full_name"] or "").strip():
        raise HTTPException(status_code=422, detail="full_name cannot be blank.")
    for field, value in data.items():
        setattr(p, field, value)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="StudentAuthorizedPickup", resource_id=p.id,
        resource_label=f"pickup {p.full_name}",
        metadata={"student_id": p.student_id}, request=request,
    )
    name = (await _student_names(db, current_user.org_id, {p.student_id})).get(p.student_id)
    return _pickup_response(p, name)


@router.delete("/pickups/{pickup_id}", status_code=204, dependencies=[_stu_write])
async def delete_pickup(
    pickup_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Deactivate-not-delete — flip is_active, preserve the row + audit history.
    p = await _load_pickup(db, pickup_id, current_user.org_id)
    p.is_active = False
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="StudentAuthorizedPickup", resource_id=p.id,
        resource_label=f"deactivated pickup {p.full_name}",
        metadata={"student_id": p.student_id, "is_active": False}, request=request,
    )
