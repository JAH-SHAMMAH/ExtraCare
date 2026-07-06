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

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.modules.school import Student
from app.models.modules.pastoral import Hostel, BoardingAllocation, ExeatRequest, MentorReport
from app.schemas.pastoral import (
    HostelCreate, HostelUpdate, HostelResponse, HostelListResponse,
    AllocationCreate, AllocationResponse,
    ExeatCreate, ExeatUpdate, ExeatDecision, ExeatResponse, ExeatListResponse,
    MentorReportCreate, MentorReportUpdate, MentorReportResponse, MentorReportListResponse,
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
