"""Pastoral & Boarding router (Batch 4), prefix ``/pastoral``.

  /pastoral/hostels                 GET/POST          school:hostel:read/write
  /pastoral/hostels/{id}            PATCH/DELETE
  /pastoral/hostels/{id}/allocations GET
  /pastoral/allocations             POST              school:hostel:write
  /pastoral/allocations/{id}        DELETE
  /pastoral/exeats                  GET/POST          school:hostel:read/write
  /pastoral/exeats/{id}             PATCH
  /pastoral/exeats/{id}/approve     POST              school_admin:write  ← approver
  /pastoral/exeats/{id}/reject      POST              school_admin:write  ← approver
  /pastoral/exeats/{id}/return      POST              school:hostel:write
  /pastoral/mentor-reports          GET/POST          school:behaviour:read/write
  /pastoral/mentor-reports/{id}     PATCH/DELETE

Exeat APPROVAL is the safety-sensitive action: authorising a child to leave
campus requires the explicit approver tier ``school_admin:write`` (org_admin /
manager) — a regular teacher can request but NOT approve — and every decision is
written to the immutable audit log with the approver + timestamp.
"""
from __future__ import annotations

from datetime import datetime, timezone

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.role import Role
from app.models.modules.school import Student, SchoolClass
from app.models.modules.platform import SchoolHouse
from app.models.modules.pastoral import (
    Hostel, BoardingAllocation, ExeatRequest, MentorReport, PastoralSettings,
    HouseMaster, HouseWeek, StudentPastoralAssignment,
)
from app.schemas.pastoral import (
    HostelCreate, HostelUpdate, HostelResponse, HostelListResponse,
    AllocationCreate, AllocationResponse,
    ExeatCreate, ExeatUpdate, ExeatDecision, ExeatResponse, ExeatListResponse,
    MentorReportCreate, MentorReportUpdate, MentorReportResponse, MentorReportListResponse,
    PastoralSettingsUpdate, PastoralSettingsResponse,
    HouseMasterCreate, HouseMasterResponse, HouseWeekCreate, HouseWeekUpdate, HouseWeekResponse,
    PastoralStudentAssign, PastoralBulkAssign, PastoralStudentRow,
    HOSTEL_GENDERS, EXEAT_STATUSES,
)
from app.services.audit_service import log_action
from app.models.audit import AuditAction

router = APIRouter(
    prefix="/pastoral",
    tags=["Pastoral & Boarding"],
    dependencies=[Depends(require_role_module("school"))],
)

_hostel_read = Depends(PermissionChecker("school:hostel:read"))
_hostel_write = Depends(PermissionChecker("school:hostel:write"))
_approve = Depends(PermissionChecker("school_admin:write"))  # explicit exeat approver tier
_beh_read = Depends(PermissionChecker("school:behaviour:read"))
_beh_write = Depends(PermissionChecker("school:behaviour:write"))


async def _student_names(db: AsyncSession, org_id: str, ids: set[str]) -> dict[str, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(
        select(Student.id, Student.first_name, Student.last_name).where(
            Student.org_id == org_id, Student.id.in_(ids))
    )).all()
    return {r.id: f"{r.first_name} {r.last_name}".strip() for r in rows}


async def _user_names(db: AsyncSession, org_id: str, ids: set[str]) -> dict[str, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(
        select(User.id, User.full_name).where(User.org_id == org_id, User.id.in_(ids))
    )).all()
    return {r.id: r.full_name for r in rows}


async def _require_student(db: AsyncSession, org_id: str, student_id: str) -> Student:
    s = (await db.execute(
        select(Student).where(
            Student.id == student_id, Student.org_id == org_id, Student.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="student not found in your organisation.")
    return s


# ── Hostels ────────────────────────────────────────────────────────────────────

async def _occupancy(db: AsyncSession, hostel_ids: list[str]) -> dict[str, int]:
    if not hostel_ids:
        return {}
    rows = (await db.execute(
        select(BoardingAllocation.hostel_id, func.count(BoardingAllocation.id))
        .where(BoardingAllocation.hostel_id.in_(hostel_ids), BoardingAllocation.is_active == True)  # noqa: E712
        .group_by(BoardingAllocation.hostel_id)
    )).all()
    return {hid: c for hid, c in rows}


def _hostel_response(h: Hostel, warden: str | None, occ: int) -> HostelResponse:
    return HostelResponse(
        id=h.id, name=h.name, gender=h.gender, capacity=h.capacity,
        warden_id=h.warden_id, warden_name=warden, notes=h.notes,
        occupancy=occ, created_at=h.created_at, org_id=h.org_id,
    )


async def _load_hostel(db: AsyncSession, hid: str, org_id: str) -> Hostel:
    h = (await db.execute(
        select(Hostel).where(Hostel.id == hid, Hostel.org_id == org_id, Hostel.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="Hostel not found.")
    return h


@router.get("/hostels", response_model=HostelListResponse, dependencies=[_hostel_read])
async def list_hostels(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = select(Hostel).where(Hostel.org_id == current_user.org_id, Hostel.is_deleted == False)  # noqa: E712
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(Hostel.name).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    wardens = await _user_names(db, current_user.org_id, {r.warden_id for r in rows})
    occ = await _occupancy(db, [r.id for r in rows])
    return HostelListResponse(
        items=[_hostel_response(r, wardens.get(r.warden_id), occ.get(r.id, 0)) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/hostels", response_model=HostelResponse, status_code=201, dependencies=[_hostel_write])
async def create_hostel(
    payload: HostelCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.gender and payload.gender not in HOSTEL_GENDERS:
        raise HTTPException(status_code=422, detail=f"gender must be one of {sorted(HOSTEL_GENDERS)}")
    h = Hostel(**payload.model_dump(), org_id=current_user.org_id)
    db.add(h)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="Hostel", resource_id=h.id, resource_label=f"hostel {h.name}", request=request,
    )
    wardens = await _user_names(db, current_user.org_id, {h.warden_id})
    return _hostel_response(h, wardens.get(h.warden_id), 0)


@router.patch("/hostels/{hostel_id}", response_model=HostelResponse, dependencies=[_hostel_write])
async def update_hostel(
    hostel_id: str,
    payload: HostelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    h = await _load_hostel(db, hostel_id, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("gender") and data["gender"] not in HOSTEL_GENDERS:
        raise HTTPException(status_code=422, detail=f"gender must be one of {sorted(HOSTEL_GENDERS)}")
    for field, value in data.items():
        setattr(h, field, value)
    await db.flush()
    wardens = await _user_names(db, current_user.org_id, {h.warden_id})
    occ = (await _occupancy(db, [h.id])).get(h.id, 0)
    return _hostel_response(h, wardens.get(h.warden_id), occ)


@router.delete("/hostels/{hostel_id}", status_code=204, dependencies=[_hostel_write])
async def delete_hostel(
    hostel_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    h = await _load_hostel(db, hostel_id, current_user.org_id)
    h.is_deleted = True
    h.deleted_at = datetime.now(timezone.utc)
    await db.flush()


def _allocation_response(a: BoardingAllocation, sname: str | None, hname: str | None) -> AllocationResponse:
    return AllocationResponse(
        id=a.id, student_id=a.student_id, student_name=sname, hostel_id=a.hostel_id, hostel_name=hname,
        room=a.room, bed=a.bed, allocated_on=a.allocated_on, is_active=a.is_active,
        created_at=a.created_at, org_id=a.org_id,
    )


@router.get("/hostels/{hostel_id}/allocations", response_model=list[AllocationResponse], dependencies=[_hostel_read])
async def list_allocations(
    hostel_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    h = await _load_hostel(db, hostel_id, current_user.org_id)
    rows = (await db.execute(
        select(BoardingAllocation).where(
            BoardingAllocation.hostel_id == h.id, BoardingAllocation.org_id == current_user.org_id,
            BoardingAllocation.is_active == True,  # noqa: E712
        )
    )).scalars().all()
    snames = await _student_names(db, current_user.org_id, {r.student_id for r in rows})
    return [_allocation_response(r, snames.get(r.student_id), h.name) for r in rows]


@router.post("/allocations", response_model=AllocationResponse, status_code=201, dependencies=[_hostel_write])
async def create_allocation(
    payload: AllocationCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    student = await _require_student(db, current_user.org_id, payload.student_id)
    hostel = await _load_hostel(db, payload.hostel_id, current_user.org_id)
    # One active allocation per student — deactivate any prior so a re-allocation
    # never leaves a boarder counted in two houses.
    prior = (await db.execute(
        select(BoardingAllocation).where(
            BoardingAllocation.student_id == student.id, BoardingAllocation.org_id == current_user.org_id,
            BoardingAllocation.is_active == True,  # noqa: E712
        )
    )).scalars().all()
    for p in prior:
        p.is_active = False
    a = BoardingAllocation(
        student_id=student.id, hostel_id=hostel.id, room=payload.room, bed=payload.bed,
        allocated_on=payload.allocated_on, is_active=True, allocated_by=current_user.id,
        org_id=current_user.org_id,
    )
    db.add(a)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="BoardingAllocation", resource_id=a.id,
        resource_label=f"boarding allocation for {student.first_name} {student.last_name}", request=request,
    )
    return _allocation_response(a, f"{student.first_name} {student.last_name}".strip(), hostel.name)


@router.delete("/allocations/{allocation_id}", status_code=204, dependencies=[_hostel_write])
async def delete_allocation(
    allocation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    a = (await db.execute(
        select(BoardingAllocation).where(
            BoardingAllocation.id == allocation_id, BoardingAllocation.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Allocation not found.")
    a.is_active = False
    await db.flush()


# ── Exeat ──────────────────────────────────────────────────────────────────────

def _exeat_response(e: ExeatRequest, sname: str | None, approver: str | None) -> ExeatResponse:
    return ExeatResponse(
        id=e.id, student_id=e.student_id, student_name=sname, reason=e.reason, destination=e.destination,
        depart_at=e.depart_at, expected_return_at=e.expected_return_at, actual_return_at=e.actual_return_at,
        status=e.status, requested_by=e.requested_by, approved_by=e.approved_by, approved_by_name=approver,
        decided_at=e.decided_at, decision_note=e.decision_note, created_at=e.created_at, org_id=e.org_id,
    )


async def _load_exeat(db: AsyncSession, eid: str, org_id: str) -> ExeatRequest:
    e = (await db.execute(
        select(ExeatRequest).where(ExeatRequest.id == eid, ExeatRequest.org_id == org_id)
    )).scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="Exeat request not found.")
    return e


async def _exeat_with_names(db: AsyncSession, e: ExeatRequest, org_id: str) -> ExeatResponse:
    snames = await _student_names(db, org_id, {e.student_id})
    approver = (await _user_names(db, org_id, {e.approved_by})).get(e.approved_by) if e.approved_by else None
    return _exeat_response(e, snames.get(e.student_id), approver)


@router.get("/exeats", response_model=ExeatListResponse, dependencies=[_hostel_read])
async def list_exeats(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = select(ExeatRequest).where(ExeatRequest.org_id == current_user.org_id)
    if status:
        base = base.where(ExeatRequest.status == status)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(ExeatRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    snames = await _student_names(db, current_user.org_id, {r.student_id for r in rows})
    approvers = await _user_names(db, current_user.org_id, {r.approved_by for r in rows})
    return ExeatListResponse(
        items=[_exeat_response(r, snames.get(r.student_id), approvers.get(r.approved_by)) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/exeats", response_model=ExeatResponse, status_code=201, dependencies=[_hostel_write])
async def create_exeat(
    payload: ExeatCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    student = await _require_student(db, current_user.org_id, payload.student_id)
    e = ExeatRequest(
        student_id=student.id, reason=payload.reason, destination=payload.destination,
        depart_at=payload.depart_at, expected_return_at=payload.expected_return_at,
        status="pending", requested_by=current_user.id, org_id=current_user.org_id,
    )
    db.add(e)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="ExeatRequest", resource_id=e.id,
        resource_label=f"exeat request for {student.first_name} {student.last_name}", request=request,
    )
    return await _exeat_with_names(db, e, current_user.org_id)


@router.patch("/exeats/{exeat_id}", response_model=ExeatResponse, dependencies=[_hostel_write])
async def update_exeat(
    exeat_id: str,
    payload: ExeatUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    e = await _load_exeat(db, exeat_id, current_user.org_id)
    if e.status != "pending":
        raise HTTPException(status_code=409, detail="Only a pending exeat can be edited.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(e, field, value)
    await db.flush()
    return await _exeat_with_names(db, e, current_user.org_id)


async def _decide_exeat(db, e: ExeatRequest, user: User, decision: str, note: str | None, request) -> None:
    """Shared approve/reject: stamp approver + time, audit the authorisation."""
    if e.status != "pending":
        raise HTTPException(status_code=409, detail=f"Exeat is already {e.status}.")
    old = e.status
    e.status = decision
    e.approved_by = user.id
    e.decided_at = datetime.now(timezone.utc)
    e.decision_note = note
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, user.org_id, actor=user,
        resource_type="ExeatRequest", resource_id=e.id,
        resource_label=f"exeat {decision} (student {e.student_id})",
        old_values={"status": old}, new_values={"status": decision, "approved_by": user.id},
        metadata={"decision_note": note}, severity="warning", request=request,
    )


@router.post("/exeats/{exeat_id}/approve", response_model=ExeatResponse, dependencies=[_approve])
async def approve_exeat(
    exeat_id: str,
    payload: ExeatDecision = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    e = await _load_exeat(db, exeat_id, current_user.org_id)
    await _decide_exeat(db, e, current_user, "approved", (payload or ExeatDecision()).decision_note, request)
    return await _exeat_with_names(db, e, current_user.org_id)


@router.post("/exeats/{exeat_id}/reject", response_model=ExeatResponse, dependencies=[_approve])
async def reject_exeat(
    exeat_id: str,
    payload: ExeatDecision = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    e = await _load_exeat(db, exeat_id, current_user.org_id)
    await _decide_exeat(db, e, current_user, "rejected", (payload or ExeatDecision()).decision_note, request)
    return await _exeat_with_names(db, e, current_user.org_id)


@router.post("/exeats/{exeat_id}/return", response_model=ExeatResponse, dependencies=[_hostel_write])
async def return_exeat(
    exeat_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    e = await _load_exeat(db, exeat_id, current_user.org_id)
    if e.status != "approved":
        raise HTTPException(status_code=409, detail="Only an approved exeat can be marked returned.")
    e.status = "returned"
    e.actual_return_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="ExeatRequest", resource_id=e.id, resource_label="exeat returned", request=request,
    )
    return await _exeat_with_names(db, e, current_user.org_id)


# ── Mentor Reports ─────────────────────────────────────────────────────────────

def _mentor_response(m: MentorReport, sname: str | None, mentor: str | None) -> MentorReportResponse:
    return MentorReportResponse(
        id=m.id, student_id=m.student_id, student_name=sname, mentor_id=m.mentor_id, mentor_name=mentor,
        term=m.term, period=m.period, summary=m.summary, strengths=m.strengths, concerns=m.concerns,
        recommendations=m.recommendations, created_at=m.created_at, org_id=m.org_id,
    )


@router.get("/mentor-reports", response_model=MentorReportListResponse, dependencies=[_beh_read])
async def list_mentor_reports(
    student_id: str | None = Query(default=None),
    mentor_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = select(MentorReport).where(MentorReport.org_id == current_user.org_id)
    if student_id:
        base = base.where(MentorReport.student_id == student_id)
    if mentor_id:
        base = base.where(MentorReport.mentor_id == mentor_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(MentorReport.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    snames = await _student_names(db, current_user.org_id, {r.student_id for r in rows})
    mentors = await _user_names(db, current_user.org_id, {r.mentor_id for r in rows})
    return MentorReportListResponse(
        items=[_mentor_response(r, snames.get(r.student_id), mentors.get(r.mentor_id)) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/mentor-reports", response_model=MentorReportResponse, status_code=201, dependencies=[_beh_write])
async def create_mentor_report(
    payload: MentorReportCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    student = await _require_student(db, current_user.org_id, payload.student_id)
    m = MentorReport(
        student_id=student.id, mentor_id=current_user.id, term=payload.term, period=payload.period,
        summary=payload.summary, strengths=payload.strengths, concerns=payload.concerns,
        recommendations=payload.recommendations, org_id=current_user.org_id,
    )
    db.add(m)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="MentorReport", resource_id=m.id, resource_label="mentor report", request=request,
    )
    mentors = await _user_names(db, current_user.org_id, {m.mentor_id})
    return _mentor_response(m, f"{student.first_name} {student.last_name}".strip(), mentors.get(m.mentor_id))


@router.patch("/mentor-reports/{report_id}", response_model=MentorReportResponse, dependencies=[_beh_write])
async def update_mentor_report(
    report_id: str,
    payload: MentorReportUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    m = (await db.execute(
        select(MentorReport).where(MentorReport.id == report_id, MentorReport.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Mentor report not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(m, field, value)
    await db.flush()
    snames = await _student_names(db, current_user.org_id, {m.student_id})
    mentors = await _user_names(db, current_user.org_id, {m.mentor_id})
    return _mentor_response(m, snames.get(m.student_id), mentors.get(m.mentor_id))


@router.delete("/mentor-reports/{report_id}", status_code=204, dependencies=[_beh_write])
async def delete_mentor_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    m = (await db.execute(
        select(MentorReport).where(MentorReport.id == report_id, MentorReport.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Mentor report not found.")
    await db.delete(m)


# ── Pastoral Setup: settings (Exeat Settings + Default Settings) ──────────────

_FLAG_FIELDS = (
    "enable_head_only_approval", "notify_parent_on_exeat_approval",
    "notify_house_parent_on_exeat_approval", "notify_pastoral_head_on_new_request",
    "enable_tutorial_week", "email_parent_on_new_point_entry", "enable_academic_cohesion",
    "show_award_in_point_analysis", "allow_referral_in_mentor_comment", "enable_point_category",
    "enable_mentor_report_assessment", "allow_only_merits_in_point_entry",
    "allow_observation_in_mentor_comment",
)


async def _get_or_create_settings(db: AsyncSession, org_id: str) -> PastoralSettings:
    s = (await db.execute(
        select(PastoralSettings).where(PastoralSettings.org_id == org_id)
    )).scalar_one_or_none()
    if not s:
        s = PastoralSettings(org_id=org_id)
        db.add(s)
        await db.flush()
    return s


async def _settings_response(db: AsyncSession, s: PastoralSettings) -> PastoralSettingsResponse:
    role_name = None
    if s.school_nurse_role_id:
        role_name = (await db.execute(
            select(Role.name).where(Role.id == s.school_nurse_role_id, Role.org_id == s.org_id)
        )).scalar_one_or_none()
    return PastoralSettingsResponse(
        **{f: getattr(s, f) for f in _FLAG_FIELDS},
        school_nurse_role_id=s.school_nurse_role_id,
        school_nurse_role_name=role_name,
    )


@router.get("/settings", response_model=PastoralSettingsResponse, dependencies=[_hostel_read])
async def get_pastoral_settings(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_or_create_settings(db, current_user.org_id)
    return await _settings_response(db, s)


@router.put("/settings", response_model=PastoralSettingsResponse, dependencies=[_hostel_write])
async def update_pastoral_settings(
    payload: PastoralSettingsUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    s = await _get_or_create_settings(db, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    # Nurse role: validate it's a role in this org (empty string clears it).
    if "school_nurse_role_id" in data:
        rid = data.pop("school_nurse_role_id") or None
        if rid:
            ok = (await db.execute(select(Role.id).where(Role.id == rid, Role.org_id == current_user.org_id))).scalar_one_or_none()
            if not ok:
                raise HTTPException(status_code=422, detail="school_nurse_role_id: not a role in your organisation")
        s.school_nurse_role_id = rid
    for f in _FLAG_FIELDS:
        if f in data and data[f] is not None:
            setattr(s, f, bool(data[f]))
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="PastoralSettings", resource_id=s.id, resource_label="Pastoral settings",
        request=request,
    )
    return await _settings_response(db, s)


# ── House Masters (Pastoral House Setup → House Masters) ──────────────────────

@router.get("/house-masters", response_model=list[HouseMasterResponse], dependencies=[_hostel_read])
async def list_house_masters(house_id: str | None = None, db: AsyncSession = Depends(get_db),
                             current_user: User = Depends(get_current_active_user)):
    q = select(HouseMaster).where(HouseMaster.org_id == current_user.org_id)
    if house_id:
        q = q.where(HouseMaster.house_id == house_id)
    rows = (await db.execute(q)).scalars().all()
    houses = {h.id: h.name for h in (await db.execute(
        select(SchoolHouse).where(SchoolHouse.org_id == current_user.org_id))).scalars().all()}
    users = await _user_names(db, current_user.org_id, {r.user_id for r in rows})
    return [HouseMasterResponse(id=r.id, house_id=r.house_id, house_name=houses.get(r.house_id),
                                user_id=r.user_id, user_name=users.get(r.user_id)) for r in rows]


@router.post("/house-masters", response_model=HouseMasterResponse, status_code=201, dependencies=[_hostel_write])
async def add_house_master(payload: HouseMasterCreate, db: AsyncSession = Depends(get_db),
                           current_user: User = Depends(get_current_active_user)):
    house = (await db.execute(select(SchoolHouse).where(SchoolHouse.id == payload.house_id, SchoolHouse.org_id == current_user.org_id))).scalar_one_or_none()
    if not house:
        raise HTTPException(status_code=404, detail="House not found.")
    user = (await db.execute(select(User.id).where(User.id == payload.user_id, User.org_id == current_user.org_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=422, detail="user_id: not a user in your organisation")
    m = HouseMaster(org_id=current_user.org_id, house_id=payload.house_id, user_id=payload.user_id)
    db.add(m)
    await db.flush()
    users = await _user_names(db, current_user.org_id, {payload.user_id})
    return HouseMasterResponse(id=m.id, house_id=m.house_id, house_name=house.name,
                               user_id=m.user_id, user_name=users.get(m.user_id))


@router.delete("/house-masters/{master_id}", status_code=204, dependencies=[_hostel_write])
async def remove_house_master(master_id: str, db: AsyncSession = Depends(get_db),
                              current_user: User = Depends(get_current_active_user)):
    m = (await db.execute(select(HouseMaster).where(HouseMaster.id == master_id, HouseMaster.org_id == current_user.org_id))).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="House master not found.")
    await db.delete(m)


# ── House Weeks (Pastoral House Setup → House Week Management) ─────────────────

def _week_response(w: HouseWeek) -> HouseWeekResponse:
    return HouseWeekResponse(id=w.id, name=w.name, start_date=w.start_date, end_date=w.end_date, is_active=w.is_active)


@router.get("/house-weeks", response_model=list[HouseWeekResponse], dependencies=[_hostel_read])
async def list_house_weeks(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(
        select(HouseWeek).where(HouseWeek.org_id == current_user.org_id).order_by(HouseWeek.start_date.desc().nullslast())
    )).scalars().all()
    return [_week_response(w) for w in rows]


@router.post("/house-weeks", response_model=HouseWeekResponse, status_code=201, dependencies=[_hostel_write])
async def create_house_week(payload: HouseWeekCreate, db: AsyncSession = Depends(get_db),
                            current_user: User = Depends(get_current_active_user)):
    w = HouseWeek(org_id=current_user.org_id, **payload.model_dump())
    db.add(w)
    await db.flush()
    return _week_response(w)


@router.patch("/house-weeks/{week_id}", response_model=HouseWeekResponse, dependencies=[_hostel_write])
async def update_house_week(week_id: str, payload: HouseWeekUpdate, db: AsyncSession = Depends(get_db),
                            current_user: User = Depends(get_current_active_user)):
    w = (await db.execute(select(HouseWeek).where(HouseWeek.id == week_id, HouseWeek.org_id == current_user.org_id))).scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="House week not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(w, f, v)
    await db.flush()
    return _week_response(w)


@router.delete("/house-weeks/{week_id}", status_code=204, dependencies=[_hostel_write])
async def delete_house_week(week_id: str, db: AsyncSession = Depends(get_db),
                            current_user: User = Depends(get_current_active_user)):
    w = (await db.execute(select(HouseWeek).where(HouseWeek.id == week_id, HouseWeek.org_id == current_user.org_id))).scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="House week not found.")
    await db.delete(w)


# ── Pastoral Students (roster: mentor / house / leaders) ─────────────────────

async def _pastoral_rows(db: AsyncSession, org_id: str, section: str | None, class_id: str | None,
                         house: str | None, search: str | None) -> list[PastoralStudentRow]:
    # All (non-deleted) students LEFT-joined to their pastoral assignment, so the
    # roster shows everyone even before a "Sync".
    q = (
        select(Student, StudentPastoralAssignment, SchoolClass.name)
        .outerjoin(StudentPastoralAssignment,
                   (StudentPastoralAssignment.student_id == Student.id) & (StudentPastoralAssignment.org_id == org_id))
        .outerjoin(SchoolClass, SchoolClass.id == Student.class_id)
        .where(Student.org_id == org_id, Student.is_deleted == False)  # noqa: E712
    )
    if section:
        q = q.where(Student.section_id == section)
    if class_id:
        q = q.where(Student.class_id == class_id)
    if house:
        q = q.where(StudentPastoralAssignment.house_id == house)
    if search:
        term = f"%{search}%"
        q = q.where(or_(Student.first_name.ilike(term), Student.last_name.ilike(term)))
    rows = (await db.execute(q.order_by(Student.first_name, Student.last_name).limit(500))).all()

    houses = {h.id: h.name for h in (await db.execute(
        select(SchoolHouse).where(SchoolHouse.org_id == org_id))).scalars().all()}
    mentor_ids = {a.mentor_id for _s, a, _c in rows if a and a.mentor_id}
    mentors = await _user_names(db, org_id, mentor_ids)

    out = []
    for s, a, class_name in rows:
        out.append(PastoralStudentRow(
            student_id=s.id, student_name=f"{s.first_name} {s.last_name}".strip(), class_name=class_name,
            house_id=(a.house_id if a else None), house_name=(houses.get(a.house_id) if a and a.house_id else None),
            mentor_id=(a.mentor_id if a else None), mentor_name=(mentors.get(a.mentor_id) if a and a.mentor_id else None),
            is_leader=bool(a.is_leader) if a else False,
        ))
    return out


@router.get("/students", response_model=list[PastoralStudentRow], dependencies=[_hostel_read])
async def list_pastoral_students(
    section: str | None = None, class_id: str | None = None, house: str | None = None, search: str | None = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    return await _pastoral_rows(db, current_user.org_id, section, class_id, house, search)


async def _upsert_assignment(db: AsyncSession, org_id: str, student_id: str) -> StudentPastoralAssignment:
    a = (await db.execute(select(StudentPastoralAssignment).where(
        StudentPastoralAssignment.org_id == org_id, StudentPastoralAssignment.student_id == student_id))).scalar_one_or_none()
    if not a:
        a = StudentPastoralAssignment(org_id=org_id, student_id=student_id)
        db.add(a)
        await db.flush()
    return a


@router.patch("/students/{student_id}", dependencies=[_hostel_write])
async def assign_pastoral_student(
    student_id: str, payload: PastoralStudentAssign, db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _require_student(db, current_user.org_id, student_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("house_id"):
        ok = (await db.execute(select(SchoolHouse.id).where(SchoolHouse.id == data["house_id"], SchoolHouse.org_id == current_user.org_id))).scalar_one_or_none()
        if not ok:
            raise HTTPException(status_code=422, detail="house_id: not a house in your organisation")
    if data.get("mentor_id"):
        ok = (await db.execute(select(User.id).where(User.id == data["mentor_id"], User.org_id == current_user.org_id))).scalar_one_or_none()
        if not ok:
            raise HTTPException(status_code=422, detail="mentor_id: not a user in your organisation")
    a = await _upsert_assignment(db, current_user.org_id, student_id)
    for f in ("house_id", "mentor_id", "is_leader"):
        if f in data:
            setattr(a, f, data[f] if f != "is_leader" else bool(data[f]))
    await db.flush()
    return {"ok": True}


@router.post("/students/bulk-assign", dependencies=[_hostel_write])
async def bulk_assign_pastoral_students(
    payload: PastoralBulkAssign, db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Mark-All / bulk assign — set house / mentor / leader for many students."""
    ids = list(dict.fromkeys(payload.student_ids or []))
    valid = set((await db.execute(
        select(Student.id).where(Student.id.in_(ids), Student.org_id == current_user.org_id, Student.is_deleted == False))).scalars().all()) if ids else set()  # noqa: E712
    fields = payload.model_dump(exclude_unset=True)
    fields.pop("student_ids", None)
    for sid in valid:
        a = await _upsert_assignment(db, current_user.org_id, sid)
        for f in ("house_id", "mentor_id", "is_leader"):
            if f in fields:
                setattr(a, f, fields[f] if f != "is_leader" else bool(fields[f]))
    await db.flush()
    return {"updated": len(valid)}


@router.post("/students/sync", dependencies=[_hostel_write])
async def sync_pastoral_students(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Create empty pastoral assignment rows for students that don't have one yet."""
    have = set((await db.execute(
        select(StudentPastoralAssignment.student_id).where(StudentPastoralAssignment.org_id == current_user.org_id))).scalars().all())
    all_ids = set((await db.execute(
        select(Student.id).where(Student.org_id == current_user.org_id, Student.is_deleted == False))).scalars().all())  # noqa: E712
    missing = all_ids - have
    for sid in missing:
        db.add(StudentPastoralAssignment(org_id=current_user.org_id, student_id=sid))
    await db.flush()
    return {"synced": len(missing)}


@router.get("/students/export", dependencies=[_hostel_read])
async def export_pastoral_students(
    section: str | None = None, db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows = await _pastoral_rows(db, current_user.org_id, section, None, None, None)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Student", "Class", "House", "Mentor", "Leader"])
    for r in rows:
        w.writerow([r.student_name or "", r.class_name or "", r.house_name or "", r.mentor_name or "", "Yes" if r.is_leader else "No"])
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="student-house.csv"'})
