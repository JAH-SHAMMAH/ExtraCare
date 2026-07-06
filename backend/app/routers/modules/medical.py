"""Medicals router (Batch 4) — CONFIDENTIAL student health data, prefix ``/medical``.

  /medical/records        GET/POST       medical:read / medical:write
  /medical/records/{id}   PATCH/DELETE

RBAC — the whole point of this module:
* Gated by the dedicated ``medical`` namespace, which is NOT reachable through
  the broad ``school:read`` hierarchy. Only roles explicitly granted ``medical:*``
  (org_admin, nurse) can read/write. A regular teacher/staff CANNOT see records.
* The router uses ``require_module("school")`` (org-level module check only) NOT
  ``require_role_module("school")`` — so the nurse, who holds no ``school:*``
  scope, still passes the module door; the per-endpoint ``medical:*`` checker
  does the real authorisation. Deletes are soft (health history is preserved).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.tenant import require_module
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.modules.school import Student
from app.models.modules.pastoral import StudentMedicalRecord
from app.schemas.medical import (
    MedicalRecordCreate, MedicalRecordUpdate, MedicalRecordResponse, MedicalRecordListResponse,
    MEDICAL_TYPES, SEVERITIES,
)
from app.services.audit_service import log_action
from app.models.audit import AuditAction

router = APIRouter(
    prefix="/medical",
    tags=["Medicals"],
    dependencies=[Depends(require_module("school"))],
)

_med_read = Depends(PermissionChecker("medical:read"))
_med_write = Depends(PermissionChecker("medical:write"))


async def _student_names(db: AsyncSession, org_id: str, ids: set[str]) -> dict[str, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(
        select(Student.id, Student.first_name, Student.last_name).where(
            Student.org_id == org_id, Student.id.in_(ids))
    )).all()
    return {r.id: f"{r.first_name} {r.last_name}".strip() for r in rows}


def _response(r: StudentMedicalRecord, sname: str | None) -> MedicalRecordResponse:
    return MedicalRecordResponse(
        id=r.id, student_id=r.student_id, student_name=sname, record_type=r.record_type,
        title=r.title, description=r.description, treatment=r.treatment, severity=r.severity,
        recorded_on=r.recorded_on, follow_up_on=r.follow_up_on, recorded_by=r.recorded_by,
        created_at=r.created_at, org_id=r.org_id,
    )


async def _load(db: AsyncSession, rid: str, org_id: str) -> StudentMedicalRecord:
    r = (await db.execute(
        select(StudentMedicalRecord).where(
            StudentMedicalRecord.id == rid, StudentMedicalRecord.org_id == org_id, StudentMedicalRecord.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Medical record not found.")
    return r


@router.get("/records", response_model=MedicalRecordListResponse, dependencies=[_med_read])
async def list_medical_records(
    student_id: str | None = Query(default=None),
    record_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = select(StudentMedicalRecord).where(
        StudentMedicalRecord.org_id == current_user.org_id, StudentMedicalRecord.is_deleted == False)  # noqa: E712
    if student_id:
        base = base.where(StudentMedicalRecord.student_id == student_id)
    if record_type:
        base = base.where(StudentMedicalRecord.record_type == record_type)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(StudentMedicalRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    snames = await _student_names(db, current_user.org_id, {r.student_id for r in rows})
    return MedicalRecordListResponse(
        items=[_response(r, snames.get(r.student_id)) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/records", response_model=MedicalRecordResponse, status_code=201, dependencies=[_med_write])
async def create_medical_record(
    payload: MedicalRecordCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.record_type not in MEDICAL_TYPES:
        raise HTTPException(status_code=422, detail=f"record_type must be one of {sorted(MEDICAL_TYPES)}")
    if payload.severity and payload.severity not in SEVERITIES:
        raise HTTPException(status_code=422, detail=f"severity must be one of {sorted(SEVERITIES)}")
    student = (await db.execute(
        select(Student).where(
            Student.id == payload.student_id, Student.org_id == current_user.org_id,
            Student.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="student not found in your organisation.")
    r = StudentMedicalRecord(
        student_id=student.id, record_type=payload.record_type, title=payload.title,
        description=payload.description, treatment=payload.treatment, severity=payload.severity,
        recorded_on=payload.recorded_on, follow_up_on=payload.follow_up_on,
        recorded_by=current_user.id, org_id=current_user.org_id,
    )
    db.add(r)
    await db.flush()
    # Audit access to confidential data WITHOUT echoing the clinical detail.
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="StudentMedicalRecord", resource_id=r.id,
        resource_label=f"medical record ({r.record_type}) for student {student.id}",
        metadata={"record_type": r.record_type}, severity="warning", request=request,
    )
    return _response(r, f"{student.first_name} {student.last_name}".strip())


@router.patch("/records/{record_id}", response_model=MedicalRecordResponse, dependencies=[_med_write])
async def update_medical_record(
    record_id: str,
    payload: MedicalRecordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    r = await _load(db, record_id, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("record_type") and data["record_type"] not in MEDICAL_TYPES:
        raise HTTPException(status_code=422, detail=f"record_type must be one of {sorted(MEDICAL_TYPES)}")
    if data.get("severity") and data["severity"] not in SEVERITIES:
        raise HTTPException(status_code=422, detail=f"severity must be one of {sorted(SEVERITIES)}")
    for field, value in data.items():
        setattr(r, field, value)
    await db.flush()
    snames = await _student_names(db, current_user.org_id, {r.student_id})
    return _response(r, snames.get(r.student_id))


@router.delete("/records/{record_id}", status_code=204, dependencies=[_med_write])
async def delete_medical_record(
    record_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    r = await _load(db, record_id, current_user.org_id)
    r.is_deleted = True
    r.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
        resource_type="StudentMedicalRecord", resource_id=r.id, resource_label="medical record",
        severity="warning", request=request,
    )
