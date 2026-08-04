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

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
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
    HouseMaster, HouseWeek, StudentPastoralAssignment, PointType, AwardType,
    HostelManager, HostelLifeGrade, HostelCommentBank,
    HostelLifeComment, HostelReport,
    SanctionGroup, DisciplinaryAction, DisciplinaryCommittee,
    DisciplinaryCommitteeMember, StudentDisciplinaryCase,
    PastoralLeadershipRole, PastoralHead,
    HostelRollCall, PastoralRemarkBank, PastoralRemark,
)
from app.models.modules.academics import Recognition
from app.services.import_files import rows_from_upload
from app.schemas.pastoral import (
    HostelCreate, HostelUpdate, HostelResponse, HostelListResponse,
    AllocationCreate, AllocationResponse,
    ExeatCreate, ExeatUpdate, ExeatDecision, ExeatResponse, ExeatListResponse,
    MentorReportCreate, MentorReportUpdate, MentorReportResponse, MentorReportListResponse,
    PastoralSettingsUpdate, PastoralSettingsResponse,
    HouseMasterCreate, HouseMasterResponse, HouseWeekCreate, HouseWeekUpdate, HouseWeekResponse,
    PastoralStudentAssign, PastoralBulkAssign, PastoralStudentRow,
    PointTypeCreate, PointTypeUpdate, PointTypeResponse,
    AwardTypeCreate, AwardTypeUpdate, AwardTypeResponse,
    PointEntryCreate, PointEntryResponse, PointsAnalysisRow,
    HostelManagerCreate, HostelManagerResponse,
    HostelLifeGradeCreate, HostelLifeGradeUpdate, HostelLifeGradeResponse,
    HostelCommentBankCreate, HostelCommentBankUpdate, HostelCommentBankResponse,
    HostelStudentRow, HostelImportResult,
    HostelLifeCommentCreate, HostelLifeCommentResponse, HostelResultRow,
    HostelReportCreate, HostelReportUpdate, HostelReportResponse, REPORT_TYPES,
    SanctionGroupCreate, SanctionGroupUpdate, SanctionGroupResponse,
    DisciplinaryActionCreate, DisciplinaryActionUpdate, DisciplinaryActionResponse,
    CommitteeCreate, CommitteeUpdate, CommitteeResponse, CommitteeMemberInfo, CommitteeMemberCreate,
    DisciplinaryCaseCreate, DisciplinaryCaseUpdate, DisciplinaryCaseResponse,
    SEVERITIES, CASE_STATUSES,
    LeadershipRoleCreate, LeadershipRoleUpdate, LeadershipRoleResponse,
    PastoralHeadCreate, PastoralHeadUpdate, PastoralHeadResponse, HeadDashboard,
    RollCallRow, RollCallMark, RemarkBankCreate, RemarkBankUpdate, RemarkBankResponse,
    PastoralRemarkCreate, PastoralRemarkResponse, PastoralReport,
    ROLL_SESSIONS, ROLL_STATUSES,
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
# The NON-boarding pastoral slice (a form/pastoral teacher's own group: dashboard,
# students, report, remarks). Split out of school:hostel:read so the classroom tier
# can reach it WITHOUT gaining the boarding cluster (hostels, allocations, exeats,
# roll-call, house masters). Admin/manager still reach both via school:read.
_pastoral_read = Depends(PermissionChecker("school:pastoral:read"))
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


@router.get("/students", response_model=list[PastoralStudentRow], dependencies=[_pastoral_read])
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


@router.get("/students/export", dependencies=[_pastoral_read])
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


# ── Point System Setup (point types) ─────────────────────────────────────────

def _pt_response(p: PointType) -> PointTypeResponse:
    return PointTypeResponse(id=p.id, name=p.name, scope=p.scope, max_point=p.max_point,
                             category=p.category, description=p.description, is_active=p.is_active)


@router.get("/point-types", response_model=list[PointTypeResponse], dependencies=[_beh_read])
async def list_point_types(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(PointType).where(PointType.org_id == current_user.org_id).order_by(PointType.name))).scalars().all()
    return [_pt_response(p) for p in rows]


@router.post("/point-types", response_model=PointTypeResponse, status_code=201, dependencies=[_beh_write])
async def create_point_type(payload: PointTypeCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = PointType(org_id=current_user.org_id, **payload.model_dump())
    db.add(p)
    await db.flush()
    return _pt_response(p)


@router.patch("/point-types/{type_id}", response_model=PointTypeResponse, dependencies=[_beh_write])
async def update_point_type(type_id: str, payload: PointTypeUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = (await db.execute(select(PointType).where(PointType.id == type_id, PointType.org_id == current_user.org_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Point type not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, f, v)
    await db.flush()
    return _pt_response(p)


@router.delete("/point-types/{type_id}", status_code=204, dependencies=[_beh_write])
async def delete_point_type(type_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = (await db.execute(select(PointType).where(PointType.id == type_id, PointType.org_id == current_user.org_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Point type not found.")
    await db.delete(p)


# ── Award System Setup (award types) ─────────────────────────────────────────

def _at_response(a: AwardType) -> AwardTypeResponse:
    return AwardTypeResponse(id=a.id, name=a.name, min_point=a.min_point, max_point=a.max_point,
                             description=a.description, is_active=a.is_active)


@router.get("/award-types", response_model=list[AwardTypeResponse], dependencies=[_beh_read])
async def list_award_types(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(AwardType).where(AwardType.org_id == current_user.org_id).order_by(AwardType.name))).scalars().all()
    return [_at_response(a) for a in rows]


@router.post("/award-types", response_model=AwardTypeResponse, status_code=201, dependencies=[_beh_write])
async def create_award_type(payload: AwardTypeCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    a = AwardType(org_id=current_user.org_id, **payload.model_dump())
    db.add(a)
    await db.flush()
    return _at_response(a)


@router.patch("/award-types/{type_id}", response_model=AwardTypeResponse, dependencies=[_beh_write])
async def update_award_type(type_id: str, payload: AwardTypeUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    a = (await db.execute(select(AwardType).where(AwardType.id == type_id, AwardType.org_id == current_user.org_id))).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Award type not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(a, f, v)
    await db.flush()
    return _at_response(a)


@router.delete("/award-types/{type_id}", status_code=204, dependencies=[_beh_write])
async def delete_award_type(type_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    a = (await db.execute(select(AwardType).where(AwardType.id == type_id, AwardType.org_id == current_user.org_id))).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Award type not found.")
    await db.delete(a)


# ── Point Entry (writes the Recognition conduct-point ledger) ────────────────

@router.post("/points", response_model=PointEntryResponse, status_code=201, dependencies=[_beh_write])
async def add_point_entry(payload: PointEntryCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Record a conduct point against a student — a Recognition(type=conduct_point)."""
    from datetime import date as _date
    await _require_student(db, current_user.org_id, payload.student_id)
    r = Recognition(
        org_id=current_user.org_id, type="conduct_point", student_id=payload.student_id,
        title=payload.title, reason=payload.reason, points=payload.points,
        house=payload.house, category=payload.category, term=payload.term,
        awarded_on=_date.today(), recorded_by=current_user.id,
    )
    db.add(r)
    await db.flush()
    names = await _student_names(db, current_user.org_id, {r.student_id})
    return PointEntryResponse(id=r.id, student_id=r.student_id, student_name=names.get(r.student_id),
                              points=r.points, title=r.title, category=r.category, reason=r.reason, term=r.term,
                              house=r.house, awarded_on=r.awarded_on)


@router.get("/points", response_model=list[PointEntryResponse], dependencies=[_beh_read])
async def list_point_entries(student_id: str | None = None, term: str | None = None,
                             db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(Recognition).where(Recognition.org_id == current_user.org_id, Recognition.type == "conduct_point")
    if student_id:
        q = q.where(Recognition.student_id == student_id)
    if term:
        q = q.where(Recognition.term == term)
    rows = (await db.execute(q.order_by(Recognition.awarded_on.desc().nullslast()).limit(500))).scalars().all()
    names = await _student_names(db, current_user.org_id, {r.student_id for r in rows})
    return [PointEntryResponse(id=r.id, student_id=r.student_id, student_name=names.get(r.student_id),
                               points=r.points or 0, title=r.title, category=r.category, reason=r.reason, term=r.term,
                               house=r.house, awarded_on=r.awarded_on) for r in rows]


# ── Points Analysis (per-student term breakdown) ─────────────────────────────

def _term_bucket(term: str | None) -> str:
    t = (term or "").strip().lower()
    if "autumn" in t or "first" in t:
        return "autumn"
    if "spring" in t or "second" in t:
        return "spring"
    if "summer" in t or "third" in t:
        return "summer"
    return "opening_point"


async def _analysis_rows(db: AsyncSession, org_id: str, section: str | None, house: str | None) -> list[PointsAnalysisRow]:
    # Students in scope.
    sq = select(Student).where(Student.org_id == org_id, Student.is_deleted == False)  # noqa: E712
    if section:
        sq = sq.where(Student.section_id == section)
    students = (await db.execute(sq)).scalars().all()
    sids = [s.id for s in students]
    agg: dict[str, PointsAnalysisRow] = {
        s.id: PointsAnalysisRow(student_id=s.id, student_name=f"{s.first_name} {s.last_name}".strip())
        for s in students
    }
    if sids:
        recs = (await db.execute(
            select(Recognition.student_id, Recognition.points, Recognition.term, Recognition.house)
            .where(Recognition.org_id == org_id, Recognition.type == "conduct_point", Recognition.student_id.in_(sids))
        )).all()
        for sid, pts, term, hse in recs:
            row = agg.get(sid)
            if not row:
                continue
            if house and hse != house:
                continue
            p = int(pts or 0)
            bucket = _term_bucket(term)
            setattr(row, bucket, getattr(row, bucket) + p)
            if p >= 0:
                row.total_pg += p
            else:
                row.total_pl += -p
            row.total += p
            if hse and not row.house_name:
                row.house_name = hse
    rows = list(agg.values())
    if house:
        rows = [r for r in rows if r.house_name == house or r.total != 0 or r.total_pg or r.total_pl]
    rows.sort(key=lambda r: r.total, reverse=True)
    return rows


@router.get("/points-analysis", response_model=list[PointsAnalysisRow], dependencies=[_beh_read])
async def points_analysis(section: str | None = None, house: str | None = None,
                          db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return await _analysis_rows(db, current_user.org_id, section, house)


@router.get("/points-analysis/export", dependencies=[_beh_read])
async def export_points_analysis(section: str | None = None, house: str | None = None,
                                 db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = await _analysis_rows(db, current_user.org_id, section, house)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Student", "House", "Opening", "Autumn", "Spring", "Summer", "Total PG", "Total PL", "Total"])
    for r in rows:
        w.writerow([r.student_name or "", r.house_name or "", r.opening_point, r.autumn, r.spring, r.summer, r.total_pg, r.total_pl, r.total])
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="points-analysis.csv"'})


# ── Batch D-1: Hostel Setup (Managers / Life Grades / Comment Bank) ──────────

@router.get("/hostel-managers", response_model=list[HostelManagerResponse], dependencies=[_hostel_read])
async def list_hostel_managers(hostel_id: str | None = None, db: AsyncSession = Depends(get_db),
                               current_user: User = Depends(get_current_active_user)):
    q = select(HostelManager).where(HostelManager.org_id == current_user.org_id)
    if hostel_id:
        q = q.where(HostelManager.hostel_id == hostel_id)
    rows = (await db.execute(q)).scalars().all()
    hostels = {h.id: h.name for h in (await db.execute(
        select(Hostel).where(Hostel.org_id == current_user.org_id))).scalars().all()}
    users = await _user_names(db, current_user.org_id, {r.user_id for r in rows})
    return [HostelManagerResponse(id=r.id, hostel_id=r.hostel_id, hostel_name=hostels.get(r.hostel_id),
                                  user_id=r.user_id, user_name=users.get(r.user_id)) for r in rows]


@router.post("/hostel-managers", response_model=HostelManagerResponse, status_code=201, dependencies=[_hostel_write])
async def add_hostel_manager(payload: HostelManagerCreate, db: AsyncSession = Depends(get_db),
                             current_user: User = Depends(get_current_active_user)):
    hostel = await _load_hostel(db, payload.hostel_id, current_user.org_id)
    user = (await db.execute(select(User.id).where(User.id == payload.user_id, User.org_id == current_user.org_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=422, detail="user_id: not a user in your organisation")
    existing = (await db.execute(select(HostelManager).where(
        HostelManager.org_id == current_user.org_id, HostelManager.hostel_id == payload.hostel_id,
        HostelManager.user_id == payload.user_id))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Already a manager of this hostel.")
    m = HostelManager(org_id=current_user.org_id, hostel_id=payload.hostel_id, user_id=payload.user_id)
    db.add(m)
    await db.flush()
    users = await _user_names(db, current_user.org_id, {payload.user_id})
    return HostelManagerResponse(id=m.id, hostel_id=m.hostel_id, hostel_name=hostel.name,
                                 user_id=m.user_id, user_name=users.get(m.user_id))


@router.delete("/hostel-managers/{manager_id}", status_code=204, dependencies=[_hostel_write])
async def remove_hostel_manager(manager_id: str, db: AsyncSession = Depends(get_db),
                                current_user: User = Depends(get_current_active_user)):
    m = (await db.execute(select(HostelManager).where(HostelManager.id == manager_id, HostelManager.org_id == current_user.org_id))).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Hostel manager not found.")
    await db.delete(m)


def _grade_response(g: HostelLifeGrade) -> HostelLifeGradeResponse:
    return HostelLifeGradeResponse(id=g.id, name=g.name, description=g.description,
                                   sort_order=g.sort_order, is_active=g.is_active)


@router.get("/hostel-life-grades", response_model=list[HostelLifeGradeResponse], dependencies=[_hostel_read])
async def list_hostel_life_grades(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(HostelLifeGrade).where(HostelLifeGrade.org_id == current_user.org_id)
                             .order_by(HostelLifeGrade.sort_order, HostelLifeGrade.name))).scalars().all()
    return [_grade_response(g) for g in rows]


@router.post("/hostel-life-grades", response_model=HostelLifeGradeResponse, status_code=201, dependencies=[_hostel_write])
async def create_hostel_life_grade(payload: HostelLifeGradeCreate, db: AsyncSession = Depends(get_db),
                                   current_user: User = Depends(get_current_active_user)):
    g = HostelLifeGrade(org_id=current_user.org_id, **payload.model_dump())
    db.add(g)
    await db.flush()
    return _grade_response(g)


@router.patch("/hostel-life-grades/{grade_id}", response_model=HostelLifeGradeResponse, dependencies=[_hostel_write])
async def update_hostel_life_grade(grade_id: str, payload: HostelLifeGradeUpdate, db: AsyncSession = Depends(get_db),
                                   current_user: User = Depends(get_current_active_user)):
    g = (await db.execute(select(HostelLifeGrade).where(HostelLifeGrade.id == grade_id, HostelLifeGrade.org_id == current_user.org_id))).scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Grade not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(g, f, v)
    await db.flush()
    return _grade_response(g)


@router.delete("/hostel-life-grades/{grade_id}", status_code=204, dependencies=[_hostel_write])
async def delete_hostel_life_grade(grade_id: str, db: AsyncSession = Depends(get_db),
                                   current_user: User = Depends(get_current_active_user)):
    g = (await db.execute(select(HostelLifeGrade).where(HostelLifeGrade.id == grade_id, HostelLifeGrade.org_id == current_user.org_id))).scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Grade not found.")
    await db.delete(g)


def _cb_response(c: HostelCommentBank) -> HostelCommentBankResponse:
    return HostelCommentBankResponse(id=c.id, text=c.text, category=c.category, is_active=c.is_active)


@router.get("/hostel-comment-bank", response_model=list[HostelCommentBankResponse], dependencies=[_hostel_read])
async def list_hostel_comment_bank(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(HostelCommentBank).where(HostelCommentBank.org_id == current_user.org_id)
                             .order_by(HostelCommentBank.category.nullslast(), HostelCommentBank.created_at))).scalars().all()
    return [_cb_response(c) for c in rows]


@router.post("/hostel-comment-bank", response_model=HostelCommentBankResponse, status_code=201, dependencies=[_hostel_write])
async def create_hostel_comment(payload: HostelCommentBankCreate, db: AsyncSession = Depends(get_db),
                                current_user: User = Depends(get_current_active_user)):
    c = HostelCommentBank(org_id=current_user.org_id, **payload.model_dump())
    db.add(c)
    await db.flush()
    return _cb_response(c)


@router.patch("/hostel-comment-bank/{comment_id}", response_model=HostelCommentBankResponse, dependencies=[_hostel_write])
async def update_hostel_comment(comment_id: str, payload: HostelCommentBankUpdate, db: AsyncSession = Depends(get_db),
                                current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(HostelCommentBank).where(HostelCommentBank.id == comment_id, HostelCommentBank.org_id == current_user.org_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Comment not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(c, f, v)
    await db.flush()
    return _cb_response(c)


@router.delete("/hostel-comment-bank/{comment_id}", status_code=204, dependencies=[_hostel_write])
async def delete_hostel_comment(comment_id: str, db: AsyncSession = Depends(get_db),
                                current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(HostelCommentBank).where(HostelCommentBank.id == comment_id, HostelCommentBank.org_id == current_user.org_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Comment not found.")
    await db.delete(c)


# ── Hostel Students (roster over boarding_allocations) ───────────────────────

async def _hostel_student_rows(db: AsyncSession, org_id: str, hostel_id: str | None,
                               search: str | None) -> list[HostelStudentRow]:
    q = (
        select(BoardingAllocation, Student, Hostel.name)
        .join(Student, Student.id == BoardingAllocation.student_id)
        .join(Hostel, Hostel.id == BoardingAllocation.hostel_id)
        .where(BoardingAllocation.org_id == org_id, BoardingAllocation.is_active == True)  # noqa: E712
    )
    if hostel_id:
        q = q.where(BoardingAllocation.hostel_id == hostel_id)
    if search:
        term = f"%{search}%"
        q = q.where(or_(Student.first_name.ilike(term), Student.last_name.ilike(term), Student.student_id.ilike(term)))
    rows = (await db.execute(q.order_by(Student.first_name, Student.last_name).limit(1000))).all()
    return [
        HostelStudentRow(
            allocation_id=a.id, student_id=s.id, student_name=f"{s.first_name} {s.last_name}".strip(),
            admission_no=s.student_id, hostel_id=a.hostel_id, hostel_name=hname,
            room=a.room, bed=a.bed, allocated_on=a.allocated_on,
        )
        for a, s, hname in rows
    ]


@router.get("/hostel-students", response_model=list[HostelStudentRow], dependencies=[_hostel_read])
async def list_hostel_students(hostel_id: str | None = None, search: str | None = None,
                               db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return await _hostel_student_rows(db, current_user.org_id, hostel_id, search)


@router.get("/hostel-students/export", dependencies=[_hostel_read])
async def export_hostel_students(hostel_id: str | None = None, search: str | None = None,
                                 db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = await _hostel_student_rows(db, current_user.org_id, hostel_id, search)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Student", "Admission No", "Hostel", "Room", "Bed", "Allocated On"])
    for r in rows:
        w.writerow([r.student_name or "", r.admission_no or "", r.hostel_name or "", r.room or "", r.bed or "",
                    r.allocated_on.isoformat() if r.allocated_on else ""])
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="hostel-students.csv"'})


@router.post("/hostel-students/import", response_model=HostelImportResult, dependencies=[_hostel_write])
async def import_hostel_students(file: UploadFile = File(...), db: AsyncSession = Depends(get_db),
                                 current_user: User = Depends(get_current_active_user)):
    """Bulk-allocate boarders from a CSV / Excel / Word / PDF table. Columns
    (case-insensitive): student (name) or admission_no, hostel (name), room, bed.
    Students are matched by admission_no first, else by exact full name; the hostel
    is matched by name. Re-allocation deactivates any prior active allocation."""
    content = await file.read()
    try:
        parsed = rows_from_upload(file.filename or "", content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    students = (await db.execute(select(Student).where(
        Student.org_id == current_user.org_id, Student.is_deleted == False))).scalars().all()  # noqa: E712
    by_adm = {(s.student_id or "").strip().lower(): s for s in students if s.student_id}
    by_name = {f"{s.first_name} {s.last_name}".strip().lower(): s for s in students}
    hostels = {h.name.strip().lower(): h for h in (await db.execute(
        select(Hostel).where(Hostel.org_id == current_user.org_id, Hostel.is_deleted == False))).scalars().all()}  # noqa: E712

    imported = 0
    errors: list[str] = []
    for i, raw in enumerate(parsed, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        adm = (row.get("admission_no") or row.get("admission") or row.get("admission no") or "").lower()
        name = (row.get("student") or row.get("name") or row.get("student name") or "").lower()
        hostel_name = (row.get("hostel") or row.get("hostel name") or "").lower()
        student = by_adm.get(adm) if adm else None
        if not student and name:
            student = by_name.get(name)
        if not student:
            errors.append(f"row {i}: student not found ({row.get('student') or row.get('admission_no') or '—'})")
            continue
        hostel = hostels.get(hostel_name) if hostel_name else None
        if not hostel:
            errors.append(f"row {i}: hostel not found ({row.get('hostel') or '—'})")
            continue
        prior = (await db.execute(select(BoardingAllocation).where(
            BoardingAllocation.student_id == student.id, BoardingAllocation.org_id == current_user.org_id,
            BoardingAllocation.is_active == True))).scalars().all()  # noqa: E712
        for p in prior:
            p.is_active = False
        db.add(BoardingAllocation(
            student_id=student.id, hostel_id=hostel.id, room=(row.get("room") or None),
            bed=(row.get("bed") or None), is_active=True, allocated_by=current_user.id,
            org_id=current_user.org_id,
        ))
        imported += 1
    await db.flush()
    return HostelImportResult(imported=imported, errors=errors[:50])


# ── Batch D-2: Hostel life comments + Result View ────────────────────────────

@router.post("/hostel-life-comments", response_model=HostelLifeCommentResponse, status_code=201, dependencies=[_hostel_write])
async def create_hostel_life_comment(payload: HostelLifeCommentCreate, db: AsyncSession = Depends(get_db),
                                     current_user: User = Depends(get_current_active_user)):
    from datetime import date as _date
    student = await _require_student(db, current_user.org_id, payload.student_id)
    hostel_name = None
    if payload.hostel_id:
        hostel = await _load_hostel(db, payload.hostel_id, current_user.org_id)
        hostel_name = hostel.name
    c = HostelLifeComment(
        org_id=current_user.org_id, student_id=student.id, hostel_id=payload.hostel_id,
        term=payload.term, grade=payload.grade, comment=payload.comment,
        recorded_on=_date.today(), recorded_by=current_user.id,
    )
    db.add(c)
    await db.flush()
    return HostelLifeCommentResponse(
        id=c.id, student_id=c.student_id, student_name=f"{student.first_name} {student.last_name}".strip(),
        hostel_id=c.hostel_id, hostel_name=hostel_name, term=c.term, grade=c.grade, comment=c.comment,
        recorded_on=c.recorded_on, recorded_by_name=current_user.full_name,
    )


@router.get("/hostel-life-comments", response_model=list[HostelLifeCommentResponse], dependencies=[_hostel_read])
async def list_hostel_life_comments(student_id: str | None = None, hostel_id: str | None = None,
                                    term: str | None = None, db: AsyncSession = Depends(get_db),
                                    current_user: User = Depends(get_current_active_user)):
    q = select(HostelLifeComment).where(HostelLifeComment.org_id == current_user.org_id)
    if student_id:
        q = q.where(HostelLifeComment.student_id == student_id)
    if hostel_id:
        q = q.where(HostelLifeComment.hostel_id == hostel_id)
    if term:
        q = q.where(HostelLifeComment.term == term)
    rows = (await db.execute(q.order_by(HostelLifeComment.recorded_on.desc().nullslast()).limit(1000))).scalars().all()
    snames = await _student_names(db, current_user.org_id, {r.student_id for r in rows})
    unames = await _user_names(db, current_user.org_id, {r.recorded_by for r in rows})
    hostels = {h.id: h.name for h in (await db.execute(
        select(Hostel).where(Hostel.org_id == current_user.org_id))).scalars().all()}
    return [
        HostelLifeCommentResponse(
            id=r.id, student_id=r.student_id, student_name=snames.get(r.student_id),
            hostel_id=r.hostel_id, hostel_name=(hostels.get(r.hostel_id) if r.hostel_id else None),
            term=r.term, grade=r.grade, comment=r.comment, recorded_on=r.recorded_on,
            recorded_by_name=(unames.get(r.recorded_by) if r.recorded_by else None),
        )
        for r in rows
    ]


@router.delete("/hostel-life-comments/{comment_id}", status_code=204, dependencies=[_hostel_write])
async def delete_hostel_life_comment(comment_id: str, db: AsyncSession = Depends(get_db),
                                     current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(HostelLifeComment).where(
        HostelLifeComment.id == comment_id, HostelLifeComment.org_id == current_user.org_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Comment not found.")
    await db.delete(c)


@router.get("/hostel-results", response_model=list[HostelResultRow], dependencies=[_hostel_read])
async def hostel_results(hostel_id: str | None = None, term: str | None = None,
                         db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Result View: one row per boarder with their latest grade + all comments."""
    q = select(HostelLifeComment).where(HostelLifeComment.org_id == current_user.org_id)
    if hostel_id:
        q = q.where(HostelLifeComment.hostel_id == hostel_id)
    if term:
        q = q.where(HostelLifeComment.term == term)
    rows = (await db.execute(q.order_by(HostelLifeComment.recorded_on.asc().nullsfirst()))).scalars().all()
    snames = await _student_names(db, current_user.org_id, {r.student_id for r in rows})
    hostels = {h.id: h.name for h in (await db.execute(
        select(Hostel).where(Hostel.org_id == current_user.org_id))).scalars().all()}

    agg: dict[str, HostelResultRow] = {}
    for r in rows:
        row = agg.get(r.student_id)
        if not row:
            row = HostelResultRow(student_id=r.student_id, student_name=snames.get(r.student_id),
                                  hostel_name=(hostels.get(r.hostel_id) if r.hostel_id else None))
            agg[r.student_id] = row
        if r.grade:
            row.latest_grade = r.grade   # rows are asc by date → last wins = latest
        if r.comment:
            row.comments.append(r.comment)
        row.comment_count += 1
    return sorted(agg.values(), key=lambda x: (x.student_name or ""))


# ── Batch D-2: Hostel reports (daily / manager) ──────────────────────────────

def _report_response(r: HostelReport, hostel_name: str | None, by_name: str | None) -> HostelReportResponse:
    return HostelReportResponse(
        id=r.id, report_type=r.report_type, hostel_id=r.hostel_id, hostel_name=hostel_name,
        report_date=r.report_date, title=r.title, body=r.body, recorded_by_name=by_name,
        created_at=r.created_at,
    )


@router.post("/hostel-reports", response_model=HostelReportResponse, status_code=201, dependencies=[_hostel_write])
async def create_hostel_report(payload: HostelReportCreate, db: AsyncSession = Depends(get_db),
                               current_user: User = Depends(get_current_active_user)):
    if payload.report_type not in REPORT_TYPES:
        raise HTTPException(status_code=422, detail=f"report_type must be one of {sorted(REPORT_TYPES)}")
    hostel = await _load_hostel(db, payload.hostel_id, current_user.org_id)
    r = HostelReport(
        org_id=current_user.org_id, report_type=payload.report_type, hostel_id=hostel.id,
        report_date=payload.report_date, title=payload.title, body=payload.body, recorded_by=current_user.id,
    )
    db.add(r)
    await db.flush()
    return _report_response(r, hostel.name, current_user.full_name)


@router.get("/hostel-reports", response_model=list[HostelReportResponse], dependencies=[_hostel_read])
async def list_hostel_reports(report_type: str | None = None, hostel_id: str | None = None,
                              db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(HostelReport).where(HostelReport.org_id == current_user.org_id)
    if report_type:
        q = q.where(HostelReport.report_type == report_type)
    if hostel_id:
        q = q.where(HostelReport.hostel_id == hostel_id)
    rows = (await db.execute(q.order_by(HostelReport.report_date.desc().nullslast(), HostelReport.created_at.desc()).limit(500))).scalars().all()
    hostels = {h.id: h.name for h in (await db.execute(
        select(Hostel).where(Hostel.org_id == current_user.org_id))).scalars().all()}
    unames = await _user_names(db, current_user.org_id, {r.recorded_by for r in rows})
    return [_report_response(r, hostels.get(r.hostel_id), (unames.get(r.recorded_by) if r.recorded_by else None)) for r in rows]


@router.patch("/hostel-reports/{report_id}", response_model=HostelReportResponse, dependencies=[_hostel_write])
async def update_hostel_report(report_id: str, payload: HostelReportUpdate, db: AsyncSession = Depends(get_db),
                               current_user: User = Depends(get_current_active_user)):
    r = (await db.execute(select(HostelReport).where(
        HostelReport.id == report_id, HostelReport.org_id == current_user.org_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(r, f, v)
    await db.flush()
    hostel = (await db.execute(select(Hostel).where(Hostel.id == r.hostel_id))).scalar_one_or_none()
    unames = await _user_names(db, current_user.org_id, {r.recorded_by})
    return _report_response(r, hostel.name if hostel else None, unames.get(r.recorded_by) if r.recorded_by else None)


@router.delete("/hostel-reports/{report_id}", status_code=204, dependencies=[_hostel_write])
async def delete_hostel_report(report_id: str, db: AsyncSession = Depends(get_db),
                               current_user: User = Depends(get_current_active_user)):
    r = (await db.execute(select(HostelReport).where(
        HostelReport.id == report_id, HostelReport.org_id == current_user.org_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found.")
    await db.delete(r)


# ── Batch E: Discipline (Disciplinary Setup) ─────────────────────────────────

def _sg_response(g: SanctionGroup) -> SanctionGroupResponse:
    return SanctionGroupResponse(id=g.id, name=g.name, description=g.description, is_active=g.is_active)


@router.get("/sanction-groups", response_model=list[SanctionGroupResponse], dependencies=[_beh_read])
async def list_sanction_groups(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(SanctionGroup).where(SanctionGroup.org_id == current_user.org_id).order_by(SanctionGroup.name))).scalars().all()
    return [_sg_response(g) for g in rows]


@router.post("/sanction-groups", response_model=SanctionGroupResponse, status_code=201, dependencies=[_beh_write])
async def create_sanction_group(payload: SanctionGroupCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    g = SanctionGroup(org_id=current_user.org_id, **payload.model_dump())
    db.add(g)
    await db.flush()
    return _sg_response(g)


@router.patch("/sanction-groups/{group_id}", response_model=SanctionGroupResponse, dependencies=[_beh_write])
async def update_sanction_group(group_id: str, payload: SanctionGroupUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    g = (await db.execute(select(SanctionGroup).where(SanctionGroup.id == group_id, SanctionGroup.org_id == current_user.org_id))).scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Sanction group not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(g, f, v)
    await db.flush()
    return _sg_response(g)


@router.delete("/sanction-groups/{group_id}", status_code=204, dependencies=[_beh_write])
async def delete_sanction_group(group_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    g = (await db.execute(select(SanctionGroup).where(SanctionGroup.id == group_id, SanctionGroup.org_id == current_user.org_id))).scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Sanction group not found.")
    await db.delete(g)


async def _group_names(db: AsyncSession, org_id: str) -> dict[str, str]:
    return {g.id: g.name for g in (await db.execute(
        select(SanctionGroup).where(SanctionGroup.org_id == org_id))).scalars().all()}


def _da_response(a: DisciplinaryAction, group_name: str | None) -> DisciplinaryActionResponse:
    return DisciplinaryActionResponse(id=a.id, name=a.name, sanction_group_id=a.sanction_group_id,
                                      sanction_group_name=group_name, severity=a.severity,
                                      description=a.description, is_active=a.is_active)


@router.get("/disciplinary-actions", response_model=list[DisciplinaryActionResponse], dependencies=[_beh_read])
async def list_disciplinary_actions(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(DisciplinaryAction).where(DisciplinaryAction.org_id == current_user.org_id).order_by(DisciplinaryAction.name))).scalars().all()
    groups = await _group_names(db, current_user.org_id)
    return [_da_response(a, groups.get(a.sanction_group_id) if a.sanction_group_id else None) for a in rows]


@router.post("/disciplinary-actions", response_model=DisciplinaryActionResponse, status_code=201, dependencies=[_beh_write])
async def create_disciplinary_action(payload: DisciplinaryActionCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.severity not in SEVERITIES:
        raise HTTPException(status_code=422, detail=f"severity must be one of {sorted(SEVERITIES)}")
    a = DisciplinaryAction(org_id=current_user.org_id, **payload.model_dump())
    db.add(a)
    await db.flush()
    groups = await _group_names(db, current_user.org_id)
    return _da_response(a, groups.get(a.sanction_group_id) if a.sanction_group_id else None)


@router.patch("/disciplinary-actions/{action_id}", response_model=DisciplinaryActionResponse, dependencies=[_beh_write])
async def update_disciplinary_action(action_id: str, payload: DisciplinaryActionUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    a = (await db.execute(select(DisciplinaryAction).where(DisciplinaryAction.id == action_id, DisciplinaryAction.org_id == current_user.org_id))).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Action not found.")
    data = payload.model_dump(exclude_unset=True)
    if data.get("severity") and data["severity"] not in SEVERITIES:
        raise HTTPException(status_code=422, detail=f"severity must be one of {sorted(SEVERITIES)}")
    for f, v in data.items():
        setattr(a, f, v)
    await db.flush()
    groups = await _group_names(db, current_user.org_id)
    return _da_response(a, groups.get(a.sanction_group_id) if a.sanction_group_id else None)


@router.delete("/disciplinary-actions/{action_id}", status_code=204, dependencies=[_beh_write])
async def delete_disciplinary_action(action_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    a = (await db.execute(select(DisciplinaryAction).where(DisciplinaryAction.id == action_id, DisciplinaryAction.org_id == current_user.org_id))).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Action not found.")
    await db.delete(a)


# ── Disciplinary Committees (+ members) ──────────────────────────────────────

async def _committee_response(db: AsyncSession, org_id: str, c: DisciplinaryCommittee) -> CommitteeResponse:
    members = (await db.execute(select(DisciplinaryCommitteeMember).where(
        DisciplinaryCommitteeMember.committee_id == c.id, DisciplinaryCommitteeMember.org_id == org_id))).scalars().all()
    unames = await _user_names(db, org_id, {m.user_id for m in members})
    return CommitteeResponse(
        id=c.id, name=c.name, description=c.description, is_active=c.is_active,
        members=[CommitteeMemberInfo(id=m.id, user_id=m.user_id, user_name=unames.get(m.user_id), role_label=m.role_label) for m in members],
    )


@router.get("/committees", response_model=list[CommitteeResponse], dependencies=[_beh_read])
async def list_committees(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(DisciplinaryCommittee).where(DisciplinaryCommittee.org_id == current_user.org_id).order_by(DisciplinaryCommittee.name))).scalars().all()
    return [await _committee_response(db, current_user.org_id, c) for c in rows]


@router.post("/committees", response_model=CommitteeResponse, status_code=201, dependencies=[_beh_write])
async def create_committee(payload: CommitteeCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = DisciplinaryCommittee(org_id=current_user.org_id, **payload.model_dump())
    db.add(c)
    await db.flush()
    return await _committee_response(db, current_user.org_id, c)


@router.patch("/committees/{committee_id}", response_model=CommitteeResponse, dependencies=[_beh_write])
async def update_committee(committee_id: str, payload: CommitteeUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(DisciplinaryCommittee).where(DisciplinaryCommittee.id == committee_id, DisciplinaryCommittee.org_id == current_user.org_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Committee not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(c, f, v)
    await db.flush()
    return await _committee_response(db, current_user.org_id, c)


@router.delete("/committees/{committee_id}", status_code=204, dependencies=[_beh_write])
async def delete_committee(committee_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(DisciplinaryCommittee).where(DisciplinaryCommittee.id == committee_id, DisciplinaryCommittee.org_id == current_user.org_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Committee not found.")
    await db.delete(c)


@router.post("/committees/{committee_id}/members", response_model=CommitteeResponse, status_code=201, dependencies=[_beh_write])
async def add_committee_member(committee_id: str, payload: CommitteeMemberCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(DisciplinaryCommittee).where(DisciplinaryCommittee.id == committee_id, DisciplinaryCommittee.org_id == current_user.org_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Committee not found.")
    user = (await db.execute(select(User.id).where(User.id == payload.user_id, User.org_id == current_user.org_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=422, detail="user_id: not a user in your organisation")
    existing = (await db.execute(select(DisciplinaryCommitteeMember).where(
        DisciplinaryCommitteeMember.org_id == current_user.org_id, DisciplinaryCommitteeMember.committee_id == committee_id,
        DisciplinaryCommitteeMember.user_id == payload.user_id))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Already on this committee.")
    db.add(DisciplinaryCommitteeMember(org_id=current_user.org_id, committee_id=committee_id,
                                       user_id=payload.user_id, role_label=payload.role_label))
    await db.flush()
    return await _committee_response(db, current_user.org_id, c)


@router.delete("/committee-members/{member_id}", status_code=204, dependencies=[_beh_write])
async def remove_committee_member(member_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    m = (await db.execute(select(DisciplinaryCommitteeMember).where(
        DisciplinaryCommitteeMember.id == member_id, DisciplinaryCommitteeMember.org_id == current_user.org_id))).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Member not found.")
    await db.delete(m)


# ── Behaviour & Sanction (disciplinary cases) ────────────────────────────────

async def _case_response(db: AsyncSession, org_id: str, c: StudentDisciplinaryCase, snames, cnames, anames, unames) -> DisciplinaryCaseResponse:
    return DisciplinaryCaseResponse(
        id=c.id, student_id=c.student_id, student_name=snames.get(c.student_id),
        committee_id=c.committee_id, committee_name=(cnames.get(c.committee_id) if c.committee_id else None),
        action_id=c.action_id, action_name=(anames.get(c.action_id) if c.action_id else None),
        sanction_group_id=c.sanction_group_id, offence=c.offence, sanction=c.sanction, status=c.status,
        case_date=c.case_date, recorded_by_name=(unames.get(c.recorded_by) if c.recorded_by else None),
        created_at=c.created_at,
    )


@router.get("/disciplinary-cases", response_model=list[DisciplinaryCaseResponse], dependencies=[_beh_read])
async def list_disciplinary_cases(student_id: str | None = None, status: str | None = None,
                                  db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(StudentDisciplinaryCase).where(StudentDisciplinaryCase.org_id == current_user.org_id)
    if student_id:
        q = q.where(StudentDisciplinaryCase.student_id == student_id)
    if status:
        q = q.where(StudentDisciplinaryCase.status == status)
    rows = (await db.execute(q.order_by(StudentDisciplinaryCase.case_date.desc().nullslast(), StudentDisciplinaryCase.created_at.desc()).limit(1000))).scalars().all()
    snames = await _student_names(db, current_user.org_id, {r.student_id for r in rows})
    cnames = {c.id: c.name for c in (await db.execute(select(DisciplinaryCommittee).where(DisciplinaryCommittee.org_id == current_user.org_id))).scalars().all()}
    anames = {a.id: a.name for a in (await db.execute(select(DisciplinaryAction).where(DisciplinaryAction.org_id == current_user.org_id))).scalars().all()}
    unames = await _user_names(db, current_user.org_id, {r.recorded_by for r in rows})
    return [await _case_response(db, current_user.org_id, r, snames, cnames, anames, unames) for r in rows]


@router.post("/disciplinary-cases", response_model=DisciplinaryCaseResponse, status_code=201, dependencies=[_beh_write])
async def create_disciplinary_case(payload: DisciplinaryCaseCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.status not in CASE_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(CASE_STATUSES)}")
    student = await _require_student(db, current_user.org_id, payload.student_id)
    c = StudentDisciplinaryCase(org_id=current_user.org_id, recorded_by=current_user.id, **payload.model_dump())
    db.add(c)
    await db.flush()
    snames = {student.id: f"{student.first_name} {student.last_name}".strip()}
    cnames = {cm.id: cm.name for cm in (await db.execute(select(DisciplinaryCommittee).where(DisciplinaryCommittee.org_id == current_user.org_id))).scalars().all()}
    anames = {a.id: a.name for a in (await db.execute(select(DisciplinaryAction).where(DisciplinaryAction.org_id == current_user.org_id))).scalars().all()}
    return await _case_response(db, current_user.org_id, c, snames, cnames, anames, {current_user.id: current_user.full_name})


@router.patch("/disciplinary-cases/{case_id}", response_model=DisciplinaryCaseResponse, dependencies=[_beh_write])
async def update_disciplinary_case(case_id: str, payload: DisciplinaryCaseUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(StudentDisciplinaryCase).where(StudentDisciplinaryCase.id == case_id, StudentDisciplinaryCase.org_id == current_user.org_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Case not found.")
    data = payload.model_dump(exclude_unset=True)
    if data.get("status") and data["status"] not in CASE_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(CASE_STATUSES)}")
    for f, v in data.items():
        setattr(c, f, v)
    await db.flush()
    snames = await _student_names(db, current_user.org_id, {c.student_id})
    cnames = {cm.id: cm.name for cm in (await db.execute(select(DisciplinaryCommittee).where(DisciplinaryCommittee.org_id == current_user.org_id))).scalars().all()}
    anames = {a.id: a.name for a in (await db.execute(select(DisciplinaryAction).where(DisciplinaryAction.org_id == current_user.org_id))).scalars().all()}
    unames = await _user_names(db, current_user.org_id, {c.recorded_by})
    return await _case_response(db, current_user.org_id, c, snames, cnames, anames, unames)


@router.delete("/disciplinary-cases/{case_id}", status_code=204, dependencies=[_beh_write])
async def delete_disciplinary_case(case_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(StudentDisciplinaryCase).where(StudentDisciplinaryCase.id == case_id, StudentDisciplinaryCase.org_id == current_user.org_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Case not found.")
    await db.delete(c)


# ── Batch F-1: Leadership Roles (Leadership Roles setup) ─────────────────────

def _lr_response(r: PastoralLeadershipRole) -> LeadershipRoleResponse:
    return LeadershipRoleResponse(id=r.id, name=r.name, description=r.description,
                                  sort_order=r.sort_order, is_active=r.is_active)


@router.get("/leadership-roles", response_model=list[LeadershipRoleResponse], dependencies=[_hostel_read])
async def list_leadership_roles(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(PastoralLeadershipRole).where(PastoralLeadershipRole.org_id == current_user.org_id)
                             .order_by(PastoralLeadershipRole.sort_order, PastoralLeadershipRole.name))).scalars().all()
    return [_lr_response(r) for r in rows]


@router.post("/leadership-roles", response_model=LeadershipRoleResponse, status_code=201, dependencies=[_hostel_write])
async def create_leadership_role(payload: LeadershipRoleCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = PastoralLeadershipRole(org_id=current_user.org_id, **payload.model_dump())
    db.add(r)
    await db.flush()
    return _lr_response(r)


@router.patch("/leadership-roles/{role_id}", response_model=LeadershipRoleResponse, dependencies=[_hostel_write])
async def update_leadership_role(role_id: str, payload: LeadershipRoleUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = (await db.execute(select(PastoralLeadershipRole).where(PastoralLeadershipRole.id == role_id, PastoralLeadershipRole.org_id == current_user.org_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Leadership role not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(r, f, v)
    await db.flush()
    return _lr_response(r)


@router.delete("/leadership-roles/{role_id}", status_code=204, dependencies=[_hostel_write])
async def delete_leadership_role(role_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = (await db.execute(select(PastoralLeadershipRole).where(PastoralLeadershipRole.id == role_id, PastoralLeadershipRole.org_id == current_user.org_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Leadership role not found.")
    await db.delete(r)


# ── Pastoral Heads (Pastoral Heads setup) ────────────────────────────────────

def _head_response(h: PastoralHead, name: str | None) -> PastoralHeadResponse:
    return PastoralHeadResponse(id=h.id, user_id=h.user_id, user_name=name, title=h.title,
                                scope=h.scope, is_active=h.is_active)


@router.get("/pastoral-heads", response_model=list[PastoralHeadResponse], dependencies=[_hostel_read])
async def list_pastoral_heads(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(PastoralHead).where(PastoralHead.org_id == current_user.org_id).order_by(PastoralHead.title))).scalars().all()
    names = await _user_names(db, current_user.org_id, {r.user_id for r in rows})
    return [_head_response(h, names.get(h.user_id)) for h in rows]


@router.post("/pastoral-heads", response_model=PastoralHeadResponse, status_code=201, dependencies=[_hostel_write])
async def create_pastoral_head(payload: PastoralHeadCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    user = (await db.execute(select(User.id).where(User.id == payload.user_id, User.org_id == current_user.org_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=422, detail="user_id: not a user in your organisation")
    h = PastoralHead(org_id=current_user.org_id, **payload.model_dump())
    db.add(h)
    await db.flush()
    names = await _user_names(db, current_user.org_id, {payload.user_id})
    return _head_response(h, names.get(h.user_id))


@router.patch("/pastoral-heads/{head_id}", response_model=PastoralHeadResponse, dependencies=[_hostel_write])
async def update_pastoral_head(head_id: str, payload: PastoralHeadUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    h = (await db.execute(select(PastoralHead).where(PastoralHead.id == head_id, PastoralHead.org_id == current_user.org_id))).scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="Pastoral head not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(h, f, v)
    await db.flush()
    names = await _user_names(db, current_user.org_id, {h.user_id})
    return _head_response(h, names.get(h.user_id))


@router.delete("/pastoral-heads/{head_id}", status_code=204, dependencies=[_hostel_write])
async def delete_pastoral_head(head_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    h = (await db.execute(select(PastoralHead).where(PastoralHead.id == head_id, PastoralHead.org_id == current_user.org_id))).scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=404, detail="Pastoral head not found.")
    await db.delete(h)


# ── Pastoral Head Dashboard ──────────────────────────────────────────────────

async def _count(db: AsyncSession, model, *conds) -> int:
    q = select(func.count()).select_from(model)
    for c in conds:
        q = q.where(c)
    return (await db.execute(q)).scalar() or 0


@router.get("/head-dashboard", response_model=HeadDashboard, dependencies=[_pastoral_read])
async def head_dashboard(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    org = current_user.org_id
    hostels = await _count(db, Hostel, Hostel.org_id == org, Hostel.is_deleted == False)          # noqa: E712
    boarders = await _count(db, BoardingAllocation, BoardingAllocation.org_id == org, BoardingAllocation.is_active == True)  # noqa: E712
    houses = await _count(db, SchoolHouse, SchoolHouse.org_id == org)
    pending_exeats = await _count(db, ExeatRequest, ExeatRequest.org_id == org, ExeatRequest.status == "pending")
    open_cases = await _count(db, StudentDisciplinaryCase, StudentDisciplinaryCase.org_id == org, StudentDisciplinaryCase.status == "pending")
    lr = await _count(db, PastoralLeadershipRole, PastoralLeadershipRole.org_id == org)
    ph = await _count(db, PastoralHead, PastoralHead.org_id == org)

    head_rows = (await db.execute(select(PastoralHead).where(PastoralHead.org_id == org, PastoralHead.is_active == True).order_by(PastoralHead.title))).scalars().all()  # noqa: E712
    hnames = await _user_names(db, org, {h.user_id for h in head_rows})

    case_rows = (await db.execute(select(StudentDisciplinaryCase).where(StudentDisciplinaryCase.org_id == org)
                                  .order_by(StudentDisciplinaryCase.created_at.desc()).limit(5))).scalars().all()
    snames = await _student_names(db, org, {c.student_id for c in case_rows})
    anames = {a.id: a.name for a in (await db.execute(select(DisciplinaryAction).where(DisciplinaryAction.org_id == org))).scalars().all()}
    cnames = {cm.id: cm.name for cm in (await db.execute(select(DisciplinaryCommittee).where(DisciplinaryCommittee.org_id == org))).scalars().all()}
    unames = await _user_names(db, org, {c.recorded_by for c in case_rows})

    return HeadDashboard(
        hostels=hostels, boarders=boarders, houses=houses, pending_exeats=pending_exeats,
        open_cases=open_cases, leadership_roles=lr, pastoral_heads=ph,
        heads=[_head_response(h, hnames.get(h.user_id)) for h in head_rows],
        recent_cases=[await _case_response(db, org, c, snames, cnames, anames, unames) for c in case_rows],
    )


# ── Batch F-2: Pastoral Roll Call ────────────────────────────────────────────

@router.get("/roll-call", response_model=list[RollCallRow], dependencies=[_hostel_read])
async def get_roll_call(hostel_id: str, roll_date: date, session: str = "evening",
                        db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Boarders of a hostel with their mark for the given date + session (status
    None = not yet marked)."""
    if session not in ROLL_SESSIONS:
        raise HTTPException(status_code=422, detail=f"session must be one of {sorted(ROLL_SESSIONS)}")
    await _load_hostel(db, hostel_id, current_user.org_id)
    allocs = (await db.execute(select(BoardingAllocation).where(
        BoardingAllocation.hostel_id == hostel_id, BoardingAllocation.org_id == current_user.org_id,
        BoardingAllocation.is_active == True))).scalars().all()  # noqa: E712
    snames = await _student_names(db, current_user.org_id, {a.student_id for a in allocs})
    existing = {r.student_id: r for r in (await db.execute(select(HostelRollCall).where(
        HostelRollCall.org_id == current_user.org_id, HostelRollCall.roll_date == roll_date,
        HostelRollCall.session == session,
        HostelRollCall.student_id.in_([a.student_id for a in allocs] or ["_none_"])))).scalars().all()}
    return [
        RollCallRow(student_id=a.student_id, student_name=snames.get(a.student_id), room=a.room,
                    status=(existing[a.student_id].status if a.student_id in existing else None),
                    roll_call_id=(existing[a.student_id].id if a.student_id in existing else None))
        for a in allocs
    ]


@router.post("/roll-call/mark", dependencies=[_hostel_write])
async def mark_roll_call(payload: RollCallMark, db: AsyncSession = Depends(get_db),
                         current_user: User = Depends(get_current_active_user)):
    """Upsert roll-call marks for a hostel/date/session. One mark per student per
    date+session (idempotent via the unique constraint)."""
    if payload.session not in ROLL_SESSIONS:
        raise HTTPException(status_code=422, detail=f"session must be one of {sorted(ROLL_SESSIONS)}")
    await _load_hostel(db, payload.hostel_id, current_user.org_id)
    ids = [m.student_id for m in payload.marks]
    existing = {r.student_id: r for r in (await db.execute(select(HostelRollCall).where(
        HostelRollCall.org_id == current_user.org_id, HostelRollCall.roll_date == payload.roll_date,
        HostelRollCall.session == payload.session,
        HostelRollCall.student_id.in_(ids or ["_none_"])))).scalars().all()}
    saved = 0
    for m in payload.marks:
        if m.status not in ROLL_STATUSES:
            raise HTTPException(status_code=422, detail=f"status must be one of {sorted(ROLL_STATUSES)}")
        row = existing.get(m.student_id)
        if row:
            row.status = m.status
            row.recorded_by = current_user.id
        else:
            db.add(HostelRollCall(org_id=current_user.org_id, hostel_id=payload.hostel_id,
                                  student_id=m.student_id, roll_date=payload.roll_date,
                                  session=payload.session, status=m.status, recorded_by=current_user.id))
        saved += 1
    await db.flush()
    return {"saved": saved}


# ── Pastoral Report Setup (remark bank) ──────────────────────────────────────

def _rb_response(r: PastoralRemarkBank) -> RemarkBankResponse:
    return RemarkBankResponse(id=r.id, text=r.text, category=r.category, is_active=r.is_active)


@router.get("/remark-bank", response_model=list[RemarkBankResponse], dependencies=[_pastoral_read])
async def list_remark_bank(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(PastoralRemarkBank).where(PastoralRemarkBank.org_id == current_user.org_id)
                             .order_by(PastoralRemarkBank.category.nullslast(), PastoralRemarkBank.created_at))).scalars().all()
    return [_rb_response(r) for r in rows]


@router.post("/remark-bank", response_model=RemarkBankResponse, status_code=201, dependencies=[_hostel_write])
async def create_remark_bank(payload: RemarkBankCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = PastoralRemarkBank(org_id=current_user.org_id, **payload.model_dump())
    db.add(r)
    await db.flush()
    return _rb_response(r)


@router.patch("/remark-bank/{remark_id}", response_model=RemarkBankResponse, dependencies=[_hostel_write])
async def update_remark_bank(remark_id: str, payload: RemarkBankUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = (await db.execute(select(PastoralRemarkBank).where(PastoralRemarkBank.id == remark_id, PastoralRemarkBank.org_id == current_user.org_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Remark not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(r, f, v)
    await db.flush()
    return _rb_response(r)


@router.delete("/remark-bank/{remark_id}", status_code=204, dependencies=[_hostel_write])
async def delete_remark_bank(remark_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = (await db.execute(select(PastoralRemarkBank).where(PastoralRemarkBank.id == remark_id, PastoralRemarkBank.org_id == current_user.org_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Remark not found.")
    await db.delete(r)


# ── Pastoral Remarks (per-student term remark) ───────────────────────────────

@router.get("/pastoral-remarks", response_model=list[PastoralRemarkResponse], dependencies=[_pastoral_read])
async def list_pastoral_remarks(student_id: str | None = None, term: str | None = None,
                                db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(PastoralRemark).where(PastoralRemark.org_id == current_user.org_id)
    if student_id:
        q = q.where(PastoralRemark.student_id == student_id)
    if term:
        q = q.where(PastoralRemark.term == term)
    rows = (await db.execute(q.order_by(PastoralRemark.recorded_on.desc().nullslast()).limit(500))).scalars().all()
    snames = await _student_names(db, current_user.org_id, {r.student_id for r in rows})
    unames = await _user_names(db, current_user.org_id, {r.recorded_by for r in rows})
    return [
        PastoralRemarkResponse(id=r.id, student_id=r.student_id, student_name=snames.get(r.student_id),
                               term=r.term, category=r.category, remark=r.remark, recorded_on=r.recorded_on,
                               recorded_by_name=(unames.get(r.recorded_by) if r.recorded_by else None))
        for r in rows
    ]


@router.post("/pastoral-remarks", response_model=PastoralRemarkResponse, status_code=201, dependencies=[_hostel_write])
async def create_pastoral_remark(payload: PastoralRemarkCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    from datetime import date as _date
    student = await _require_student(db, current_user.org_id, payload.student_id)
    r = PastoralRemark(org_id=current_user.org_id, recorded_on=_date.today(), recorded_by=current_user.id, **payload.model_dump())
    db.add(r)
    await db.flush()
    return PastoralRemarkResponse(id=r.id, student_id=r.student_id,
                                  student_name=f"{student.first_name} {student.last_name}".strip(),
                                  term=r.term, category=r.category, remark=r.remark, recorded_on=r.recorded_on,
                                  recorded_by_name=current_user.full_name)


@router.delete("/pastoral-remarks/{remark_id}", status_code=204, dependencies=[_hostel_write])
async def delete_pastoral_remark(remark_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = (await db.execute(select(PastoralRemark).where(PastoralRemark.id == remark_id, PastoralRemark.org_id == current_user.org_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Remark not found.")
    await db.delete(r)


# ── Pastoral Report (per-student aggregation) ────────────────────────────────

@router.get("/pastoral-report", response_model=PastoralReport, dependencies=[_pastoral_read])
async def pastoral_report(student_id: str, term: str | None = None,
                          db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    org = current_user.org_id
    student = await _require_student(db, org, student_id)

    # House (from pastoral assignment) + hostel (from active allocation).
    assign = (await db.execute(select(StudentPastoralAssignment).where(
        StudentPastoralAssignment.student_id == student_id, StudentPastoralAssignment.org_id == org))).scalar_one_or_none()
    house_name = None
    if assign and assign.house_id:
        house_name = (await db.execute(select(SchoolHouse.name).where(SchoolHouse.id == assign.house_id))).scalar_one_or_none()
    alloc = (await db.execute(select(BoardingAllocation).where(
        BoardingAllocation.student_id == student_id, BoardingAllocation.org_id == org,
        BoardingAllocation.is_active == True))).scalar_one_or_none()  # noqa: E712
    hostel_name = None
    if alloc:
        hostel_name = (await db.execute(select(Hostel.name).where(Hostel.id == alloc.hostel_id))).scalar_one_or_none()

    # Conduct points from the Recognition ledger.
    pq = select(Recognition.points).where(
        Recognition.org_id == org, Recognition.type == "conduct_point", Recognition.student_id == student_id)
    if term:
        pq = pq.where(Recognition.term == term)
    pts = [p or 0 for p in (await db.execute(pq)).scalars().all()]
    gained = sum(p for p in pts if p > 0)
    lost = sum(-p for p in pts if p < 0)

    total_cases = await _count(db, StudentDisciplinaryCase, StudentDisciplinaryCase.org_id == org, StudentDisciplinaryCase.student_id == student_id)
    open_cases = await _count(db, StudentDisciplinaryCase, StudentDisciplinaryCase.org_id == org,
                              StudentDisciplinaryCase.student_id == student_id, StudentDisciplinaryCase.status == "pending")

    life = await list_hostel_life_comments(student_id=student_id, hostel_id=None, term=term, db=db, current_user=current_user)
    remarks = await list_pastoral_remarks(student_id=student_id, term=term, db=db, current_user=current_user)

    return PastoralReport(
        student_id=student_id, student_name=f"{student.first_name} {student.last_name}".strip(),
        house_name=house_name, hostel_name=hostel_name,
        total_points=gained - lost, points_gained=gained, points_lost=lost,
        open_cases=open_cases, total_cases=total_cases, life_comments=life, remarks=remarks,
    )
