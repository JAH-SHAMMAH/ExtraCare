"""Recruitment + Disciplinary router (Phase 4 Batch 1), prefix ``/hr``.

Confidential HR admin — every endpoint is gated ``hr:write`` so hr:read-only
roles (teachers/staff) can't see the candidate pipeline or disciplinary cases.

NEW ENDPOINTS:
  Recruitment:  GET/POST /hr/recruitment/jobs · PATCH/DELETE /hr/recruitment/jobs/{id}
                GET/POST /hr/recruitment/applicants · PATCH/DELETE /hr/recruitment/applicants/{id}
  Disciplinary: GET/POST /hr/disciplinary/cases · PATCH/DELETE /hr/disciplinary/cases/{id}
  Stats:        GET /hr/stats  (open jobs / applicants / open disciplinary — for the HR dashboard cards)
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.hr_extended import JobOpening, Applicant, DisciplinaryCase, StaffAppointment
from app.schemas.hr_extended import (
    JobOpeningCreate, JobOpeningUpdate, JobOpeningResponse,
    ApplicantCreate, ApplicantUpdate, ApplicantResponse,
    DisciplinaryCreate, DisciplinaryUpdate, DisciplinaryResponse,
    HrExtendedStats,
    AppointmentCreate, AppointmentUpdate, AppointmentResponse, APPOINTMENT_TYPES,
)
from app.services.audit_service import log_action
from app.models.audit import AuditAction

router = APIRouter(prefix="/hr", tags=["HR — Recruitment & Disciplinary"])

_can_hr = Depends(PermissionChecker("hr:write"))
_OPEN_CASE = ("open", "under_review")


# ── Recruitment: Job openings ─────────────────────────────────────────────────────

def _job_response(j: JobOpening, applicant_count: int = 0) -> JobOpeningResponse:
    return JobOpeningResponse(
        id=j.id, title=j.title, department=j.department, description=j.description,
        employment_type=j.employment_type, positions=j.positions, status=j.status,
        posted_on=j.posted_on, closes_on=j.closes_on, applicant_count=applicant_count,
        created_at=j.created_at, org_id=j.org_id,
    )


@router.get("/recruitment/jobs", response_model=list[JobOpeningResponse], dependencies=[_can_hr])
async def list_jobs(status: str | None = Query(default=None), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(JobOpening).where(JobOpening.org_id == current_user.org_id, JobOpening.is_deleted == False)  # noqa: E712
    if status:
        q = q.where(JobOpening.status == status)
    jobs = (await db.execute(q.order_by(JobOpening.created_at.desc()))).scalars().all()
    counts = dict((jid, c) for jid, c in (await db.execute(
        select(Applicant.job_id, func.count(Applicant.id)).where(
            Applicant.org_id == current_user.org_id, Applicant.is_deleted == False  # noqa: E712
        ).group_by(Applicant.job_id)
    )).all())
    return [_job_response(j, counts.get(j.id, 0)) for j in jobs]


@router.post("/recruitment/jobs", response_model=JobOpeningResponse, status_code=201, dependencies=[_can_hr])
async def create_job(payload: JobOpeningCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    j = JobOpening(**payload.model_dump(), status="open", org_id=current_user.org_id)
    db.add(j)
    await db.flush()
    return _job_response(j, 0)


@router.patch("/recruitment/jobs/{job_id}", response_model=JobOpeningResponse, dependencies=[_can_hr])
async def update_job(job_id: str, payload: JobOpeningUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    j = (await db.execute(select(JobOpening).where(JobOpening.id == job_id, JobOpening.org_id == current_user.org_id, JobOpening.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not j:
        raise HTTPException(status_code=404, detail="Job opening not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(j, f, v)
    await db.flush()
    cnt = (await db.execute(select(func.count(Applicant.id)).where(Applicant.job_id == j.id, Applicant.is_deleted == False))).scalar() or 0  # noqa: E712
    return _job_response(j, cnt)


@router.delete("/recruitment/jobs/{job_id}", status_code=204, dependencies=[_can_hr])
async def delete_job(job_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    j = (await db.execute(select(JobOpening).where(JobOpening.id == job_id, JobOpening.org_id == current_user.org_id, JobOpening.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not j:
        raise HTTPException(status_code=404, detail="Job opening not found.")
    j.is_deleted = True
    j.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Recruitment: Applicants ───────────────────────────────────────────────────────

def _applicant_response(a: Applicant) -> ApplicantResponse:
    return ApplicantResponse(
        id=a.id, job_id=a.job_id, name=a.name, email=a.email, phone=a.phone, stage=a.stage,
        rating=a.rating, resume_url=a.resume_url, notes=a.notes, applied_on=a.applied_on,
        created_at=a.created_at, org_id=a.org_id,
    )


@router.get("/recruitment/applicants", response_model=list[ApplicantResponse], dependencies=[_can_hr])
async def list_applicants(job_id: str | None = Query(default=None), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(Applicant).where(Applicant.org_id == current_user.org_id, Applicant.is_deleted == False)  # noqa: E712
    if job_id:
        q = q.where(Applicant.job_id == job_id)
    rows = (await db.execute(q.order_by(Applicant.created_at.desc()))).scalars().all()
    return [_applicant_response(a) for a in rows]


@router.post("/recruitment/applicants", response_model=ApplicantResponse, status_code=201, dependencies=[_can_hr])
async def create_applicant(payload: ApplicantCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    job = (await db.execute(select(JobOpening).where(JobOpening.id == payload.job_id, JobOpening.org_id == current_user.org_id, JobOpening.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not job:
        raise HTTPException(status_code=404, detail="Job opening not found.")
    a = Applicant(**payload.model_dump(), org_id=current_user.org_id)
    db.add(a)
    await db.flush()
    return _applicant_response(a)


@router.patch("/recruitment/applicants/{applicant_id}", response_model=ApplicantResponse, dependencies=[_can_hr])
async def update_applicant(applicant_id: str, payload: ApplicantUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    a = (await db.execute(select(Applicant).where(Applicant.id == applicant_id, Applicant.org_id == current_user.org_id, Applicant.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not a:
        raise HTTPException(status_code=404, detail="Applicant not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(a, f, v)
    await db.flush()
    return _applicant_response(a)


@router.delete("/recruitment/applicants/{applicant_id}", status_code=204, dependencies=[_can_hr])
async def delete_applicant(applicant_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    a = (await db.execute(select(Applicant).where(Applicant.id == applicant_id, Applicant.org_id == current_user.org_id, Applicant.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not a:
        raise HTTPException(status_code=404, detail="Applicant not found.")
    a.is_deleted = True
    a.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Disciplinary (audited — sensitive) ────────────────────────────────────────────

async def _staff_name(db, org_id, uid) -> str | None:
    if not uid:
        return None
    u = (await db.execute(select(User.full_name).where(User.id == uid, User.org_id == org_id))).scalar_one_or_none()
    return u


def _case_response(c: DisciplinaryCase, staff_name: str | None) -> DisciplinaryResponse:
    return DisciplinaryResponse(
        id=c.id, staff_user_id=c.staff_user_id, staff_name=staff_name, title=c.title, description=c.description,
        severity=c.severity, status=c.status, action_taken=c.action_taken, reported_by=c.reported_by,
        incident_on=c.incident_on, resolved_on=c.resolved_on, created_at=c.created_at, org_id=c.org_id,
    )


@router.get("/disciplinary/cases", response_model=list[DisciplinaryResponse], dependencies=[_can_hr])
async def list_cases(status: str | None = Query(default=None), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(DisciplinaryCase).where(DisciplinaryCase.org_id == current_user.org_id, DisciplinaryCase.is_deleted == False)  # noqa: E712
    if status:
        q = q.where(DisciplinaryCase.status == status)
    rows = (await db.execute(q.order_by(DisciplinaryCase.created_at.desc()))).scalars().all()
    return [_case_response(c, await _staff_name(db, current_user.org_id, c.staff_user_id)) for c in rows]


@router.post("/disciplinary/cases", response_model=DisciplinaryResponse, status_code=201, dependencies=[_can_hr])
async def create_case(payload: DisciplinaryCreate, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    staff = (await db.execute(select(User).where(User.id == payload.staff_user_id, User.org_id == current_user.org_id))).scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found.")
    c = DisciplinaryCase(
        staff_user_id=payload.staff_user_id, title=payload.title, description=payload.description,
        severity=payload.severity, incident_on=payload.incident_on, status="open",
        reported_by=current_user.id, org_id=current_user.org_id,
    )
    db.add(c)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="DisciplinaryCase", resource_id=c.id, resource_label=staff.full_name,
        new_values={"severity": c.severity, "status": c.status}, severity="warning", request=request,
    )
    return _case_response(c, staff.full_name)


@router.patch("/disciplinary/cases/{case_id}", response_model=DisciplinaryResponse, dependencies=[_can_hr])
async def update_case(case_id: str, payload: DisciplinaryUpdate, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(DisciplinaryCase).where(DisciplinaryCase.id == case_id, DisciplinaryCase.org_id == current_user.org_id, DisciplinaryCase.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not c:
        raise HTTPException(status_code=404, detail="Case not found.")
    old_status = c.status
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(c, f, v)
    await db.flush()
    if payload.status and payload.status != old_status:
        await log_action(
            db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
            resource_type="DisciplinaryCase", resource_id=c.id,
            old_values={"status": old_status}, new_values={"status": c.status}, severity="warning", request=request,
        )
    return _case_response(c, await _staff_name(db, current_user.org_id, c.staff_user_id))


@router.delete("/disciplinary/cases/{case_id}", status_code=204, dependencies=[_can_hr])
async def delete_case(case_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(DisciplinaryCase).where(DisciplinaryCase.id == case_id, DisciplinaryCase.org_id == current_user.org_id, DisciplinaryCase.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not c:
        raise HTTPException(status_code=404, detail="Case not found.")
    c.is_deleted = True
    c.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Stats (HR dashboard cards) ────────────────────────────────────────────────────

@router.get("/stats", response_model=HrExtendedStats, dependencies=[_can_hr])
async def hr_stats(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    org = current_user.org_id
    open_jobs = (await db.execute(select(func.count(JobOpening.id)).where(JobOpening.org_id == org, JobOpening.status == "open", JobOpening.is_deleted == False))).scalar() or 0  # noqa: E712
    applicants = (await db.execute(select(func.count(Applicant.id)).where(Applicant.org_id == org, Applicant.is_deleted == False))).scalar() or 0  # noqa: E712
    open_cases = (await db.execute(select(func.count(DisciplinaryCase.id)).where(DisciplinaryCase.org_id == org, DisciplinaryCase.status.in_(_OPEN_CASE), DisciplinaryCase.is_deleted == False))).scalar() or 0  # noqa: E712
    return HrExtendedStats(open_jobs=open_jobs, total_applicants=applicants, open_disciplinary=open_cases)


# ── Staff Appointments (Appointment Manager) ──────────────────────────────────────
# Employment history (appointment / promotion / salary review / contract / transfer /
# termination) per staff member. Confidential salary data → gated hr:write like the
# rest of this router (so hr:read-only teachers and finance-only accountants can't see
# it). Records only — it does NOT auto-feed payroll (a deliberate future integration).

def _appointment_response(a: StaffAppointment, staff_name: str | None) -> AppointmentResponse:
    return AppointmentResponse(
        id=a.id, staff_user_id=a.staff_user_id, staff_name=staff_name,
        appointment_type=a.appointment_type, title=a.title, grade=a.grade,
        salary=float(a.salary) if a.salary is not None else None, salary_currency=a.salary_currency,
        effective_date=a.effective_date, end_date=a.end_date, status=a.status,
        reference=a.reference, notes=a.notes, created_by=a.created_by,
        created_at=a.created_at, org_id=a.org_id,
    )


async def _load_appointment(db, appointment_id, org_id) -> StaffAppointment:
    a = (await db.execute(select(StaffAppointment).where(
        StaffAppointment.id == appointment_id, StaffAppointment.org_id == org_id,
        StaffAppointment.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not a:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    return a


@router.get("/appointments", response_model=list[AppointmentResponse], dependencies=[_can_hr])
async def list_appointments(
    staff_user_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(StaffAppointment).where(
        StaffAppointment.org_id == current_user.org_id, StaffAppointment.is_deleted == False)  # noqa: E712
    if staff_user_id:
        q = q.where(StaffAppointment.staff_user_id == staff_user_id)
    if status:
        q = q.where(StaffAppointment.status == status)
    # Newest effective first (fall back to created), so the current appointment leads.
    rows = (await db.execute(
        q.order_by(StaffAppointment.effective_date.desc().nullslast(), StaffAppointment.created_at.desc())
    )).scalars().all()
    return [_appointment_response(a, await _staff_name(db, current_user.org_id, a.staff_user_id)) for a in rows]


@router.post("/appointments", response_model=AppointmentResponse, status_code=201, dependencies=[_can_hr])
async def create_appointment(
    payload: AppointmentCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.appointment_type not in APPOINTMENT_TYPES:
        raise HTTPException(status_code=422, detail=f"appointment_type must be one of {sorted(APPOINTMENT_TYPES)}.")
    staff = (await db.execute(
        select(User).where(User.id == payload.staff_user_id, User.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found.")
    if payload.salary is not None and payload.salary < 0:
        raise HTTPException(status_code=422, detail="Salary cannot be negative.")
    a = StaffAppointment(
        staff_user_id=staff.id, appointment_type=payload.appointment_type, title=payload.title,
        grade=payload.grade, salary=payload.salary, salary_currency=payload.salary_currency or "NGN",
        effective_date=payload.effective_date, end_date=payload.end_date, status="active",
        reference=payload.reference, notes=payload.notes, created_by=current_user.id, org_id=current_user.org_id,
    )
    db.add(a)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="StaffAppointment", resource_id=a.id, resource_label=f"{payload.appointment_type} — {staff.full_name}",
        new_values={"type": a.appointment_type, "grade": a.grade}, severity="warning", request=request,
    )
    return _appointment_response(a, staff.full_name)


@router.patch("/appointments/{appointment_id}", response_model=AppointmentResponse, dependencies=[_can_hr])
async def update_appointment(
    appointment_id: str,
    payload: AppointmentUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    a = await _load_appointment(db, appointment_id, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    if "appointment_type" in data and data["appointment_type"] not in APPOINTMENT_TYPES:
        raise HTTPException(status_code=422, detail=f"appointment_type must be one of {sorted(APPOINTMENT_TYPES)}.")
    if data.get("salary") is not None and data["salary"] < 0:
        raise HTTPException(status_code=422, detail="Salary cannot be negative.")
    for f, v in data.items():
        setattr(a, f, v)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="StaffAppointment", resource_id=a.id, resource_label=a.title,
        new_values={k: str(v) for k, v in data.items()}, severity="warning", request=request,
    )
    return _appointment_response(a, await _staff_name(db, current_user.org_id, a.staff_user_id))


@router.delete("/appointments/{appointment_id}", status_code=204, dependencies=[_can_hr])
async def delete_appointment(
    appointment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    a = await _load_appointment(db, appointment_id, current_user.org_id)
    a.is_deleted = True
    a.deleted_at = datetime.now(timezone.utc)
    await db.flush()
