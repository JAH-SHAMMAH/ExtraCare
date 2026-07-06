"""Operations router (Batch 6, non-financial), prefix ``/operations``.

  /operations/calendar            GET/POST/PATCH/DELETE   school:read / school:write
  /operations/facilities          GET/POST/PATCH/DELETE   school_admin:read / :write
  /operations/facilities/{id}/bookings  GET/POST          (double-booking guarded)
  /operations/bookings/{id}/cancel POST
  /operations/visitors            GET/POST                school_admin:read / :write
  /operations/visitors/{id}/signout POST · DELETE (soft)
  /operations/collections         GET/POST/DELETE         (safeguarding — see below)

Visitor Management is a SAFEGUARDING surface: visitor + child-collection mutations
are written to the immutable audit log, records are soft-deleted only (never
silently removed), and a collection REQUIRES an ``authorized_by`` staff member.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.modules.school import Student
from app.models.modules.operations import (
    CalendarEvent, Facility, FacilityBooking, VisitorLog, StudentCollection,
)
from app.schemas.operations import (
    CalendarEventCreate, CalendarEventUpdate, CalendarEventResponse, CalendarEventListResponse,
    FacilityCreate, FacilityUpdate, FacilityResponse, FacilityListResponse,
    BookingCreate, BookingResponse,
    VisitorCreate, VisitorResponse, VisitorListResponse,
    CollectionCreate, CollectionResponse, CollectionListResponse,
    FACILITY_STATUSES, BOOKING_STATUSES,
)
from app.services.audit_service import log_action
from app.models.audit import AuditAction

router = APIRouter(
    prefix="/operations",
    tags=["Operations"],
    dependencies=[Depends(require_role_module("school"))],
)

_cal_read = Depends(PermissionChecker("school:read"))
_cal_write = Depends(PermissionChecker("school:write"))
_adm_read = Depends(PermissionChecker("school_admin:read"))
_adm_write = Depends(PermissionChecker("school_admin:write"))


async def _user_name(db, org_id, uid) -> str | None:
    if not uid:
        return None
    r = (await db.execute(select(User.full_name).where(User.id == uid, User.org_id == org_id))).first()
    return r[0] if r else None


async def _student_name(db, org_id, sid) -> str | None:
    r = (await db.execute(select(Student.first_name, Student.last_name).where(Student.id == sid, Student.org_id == org_id))).first()
    return f"{r.first_name} {r.last_name}".strip() if r else None


# ── Calendar ────────────────────────────────────────────────────────────────────

def _event_response(e: CalendarEvent) -> CalendarEventResponse:
    return CalendarEventResponse(
        id=e.id, title=e.title, description=e.description, start_at=e.start_at, end_at=e.end_at,
        all_day=e.all_day, category=e.category, location=e.location, audience=e.audience,
        created_at=e.created_at, org_id=e.org_id,
    )


@router.get("/calendar", response_model=CalendarEventListResponse, dependencies=[_cal_read])
async def list_events(
    page: int = Query(default=1, ge=1), page_size: int = Query(default=100, ge=1, le=200),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    base = select(CalendarEvent).where(CalendarEvent.org_id == current_user.org_id, CalendarEvent.is_deleted == False)  # noqa: E712
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(base.order_by(CalendarEvent.start_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return CalendarEventListResponse(items=[_event_response(e) for e in rows], total=total, page=page, page_size=page_size)


@router.post("/calendar", response_model=CalendarEventResponse, status_code=201, dependencies=[_cal_write])
async def create_event(payload: CalendarEventCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    e = CalendarEvent(**payload.model_dump(), created_by=current_user.id, org_id=current_user.org_id)
    db.add(e)
    await db.flush()
    return _event_response(e)


@router.patch("/calendar/{event_id}", response_model=CalendarEventResponse, dependencies=[_cal_write])
async def update_event(event_id: str, payload: CalendarEventUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    e = (await db.execute(select(CalendarEvent).where(CalendarEvent.id == event_id, CalendarEvent.org_id == current_user.org_id, CalendarEvent.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not e:
        raise HTTPException(status_code=404, detail="Event not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(e, field, value)
    await db.flush()
    return _event_response(e)


@router.delete("/calendar/{event_id}", status_code=204, dependencies=[_cal_write])
async def delete_event(event_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    e = (await db.execute(select(CalendarEvent).where(CalendarEvent.id == event_id, CalendarEvent.org_id == current_user.org_id, CalendarEvent.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not e:
        raise HTTPException(status_code=404, detail="Event not found.")
    e.is_deleted = True
    e.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Facility ────────────────────────────────────────────────────────────────────

def _facility_response(f: Facility) -> FacilityResponse:
    return FacilityResponse(
        id=f.id, name=f.name, type=f.type, capacity=f.capacity, location=f.location, status=f.status,
        notes=f.notes, is_active=f.is_active, created_at=f.created_at, org_id=f.org_id,
    )


async def _load_facility(db, fid, org_id) -> Facility:
    f = (await db.execute(select(Facility).where(Facility.id == fid, Facility.org_id == org_id, Facility.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not f:
        raise HTTPException(status_code=404, detail="Facility not found.")
    return f


@router.get("/facilities", response_model=FacilityListResponse, dependencies=[_adm_read])
async def list_facilities(
    page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    base = select(Facility).where(Facility.org_id == current_user.org_id, Facility.is_deleted == False)  # noqa: E712
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(base.order_by(Facility.name).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return FacilityListResponse(items=[_facility_response(f) for f in rows], total=total, page=page, page_size=page_size)


@router.post("/facilities", response_model=FacilityResponse, status_code=201, dependencies=[_adm_write])
async def create_facility(payload: FacilityCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.status not in FACILITY_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(FACILITY_STATUSES)}")
    f = Facility(**payload.model_dump(), is_active=True, org_id=current_user.org_id)
    db.add(f)
    await db.flush()
    return _facility_response(f)


@router.patch("/facilities/{facility_id}", response_model=FacilityResponse, dependencies=[_adm_write])
async def update_facility(facility_id: str, payload: FacilityUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    f = await _load_facility(db, facility_id, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("status") and data["status"] not in FACILITY_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(FACILITY_STATUSES)}")
    for field, value in data.items():
        setattr(f, field, value)
    await db.flush()
    return _facility_response(f)


@router.delete("/facilities/{facility_id}", status_code=204, dependencies=[_adm_write])
async def delete_facility(facility_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    f = await _load_facility(db, facility_id, current_user.org_id)
    f.is_deleted = True
    f.deleted_at = datetime.now(timezone.utc)
    await db.flush()


def _booking_response(b: FacilityBooking) -> BookingResponse:
    return BookingResponse(
        id=b.id, facility_id=b.facility_id, title=b.title, purpose=b.purpose, start_at=b.start_at,
        end_at=b.end_at, status=b.status, booked_by=b.booked_by, created_at=b.created_at, org_id=b.org_id,
    )


@router.get("/facilities/{facility_id}/bookings", response_model=list[BookingResponse], dependencies=[_adm_read])
async def list_bookings(facility_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    await _load_facility(db, facility_id, current_user.org_id)
    rows = (await db.execute(
        select(FacilityBooking).where(FacilityBooking.facility_id == facility_id, FacilityBooking.org_id == current_user.org_id)
        .order_by(FacilityBooking.start_at.desc())
    )).scalars().all()
    return [_booking_response(b) for b in rows]


@router.post("/facilities/{facility_id}/bookings", response_model=BookingResponse, status_code=201, dependencies=[_adm_write])
async def create_booking(facility_id: str, payload: BookingCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    f = await _load_facility(db, facility_id, current_user.org_id)
    if payload.end_at <= payload.start_at:
        raise HTTPException(status_code=422, detail="end_at must be after start_at.")
    # Double-booking guard: refuse an overlapping active booking on the same facility.
    clash = (await db.execute(
        select(func.count()).select_from(FacilityBooking).where(
            FacilityBooking.facility_id == f.id, FacilityBooking.org_id == current_user.org_id,
            FacilityBooking.status == "booked",
            and_(FacilityBooking.start_at < payload.end_at, FacilityBooking.end_at > payload.start_at),
        )
    )).scalar() or 0
    if clash:
        raise HTTPException(status_code=409, detail="That facility is already booked for an overlapping time.")
    b = FacilityBooking(facility_id=f.id, title=payload.title, purpose=payload.purpose, start_at=payload.start_at,
                        end_at=payload.end_at, status="booked", booked_by=current_user.id, org_id=current_user.org_id)
    db.add(b)
    await db.flush()
    return _booking_response(b)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingResponse, dependencies=[_adm_write])
async def cancel_booking(booking_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    b = (await db.execute(select(FacilityBooking).where(FacilityBooking.id == booking_id, FacilityBooking.org_id == current_user.org_id))).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found.")
    b.status = "cancelled"
    await db.flush()
    return _booking_response(b)


# ── Visitor Management (safeguarding) ───────────────────────────────────────────

def _visitor_response(v: VisitorLog) -> VisitorResponse:
    return VisitorResponse(
        id=v.id, visitor_name=v.visitor_name, organization=v.organization, purpose=v.purpose,
        host_name=v.host_name, phone=v.phone, badge_no=v.badge_no, sign_in_at=v.sign_in_at,
        sign_out_at=v.sign_out_at, status=v.status, recorded_by=v.recorded_by, created_at=v.created_at, org_id=v.org_id,
    )


@router.get("/visitors", response_model=VisitorListResponse, dependencies=[_adm_read])
async def list_visitors(
    status: str | None = Query(default=None), page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    base = select(VisitorLog).where(VisitorLog.org_id == current_user.org_id, VisitorLog.is_deleted == False)  # noqa: E712
    if status:
        base = base.where(VisitorLog.status == status)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(base.order_by(VisitorLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return VisitorListResponse(items=[_visitor_response(v) for v in rows], total=total, page=page, page_size=page_size)


@router.post("/visitors", response_model=VisitorResponse, status_code=201, dependencies=[_adm_write])
async def sign_in_visitor(payload: VisitorCreate, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    v = VisitorLog(**payload.model_dump(), sign_in_at=datetime.now(timezone.utc), status="signed_in",
                   recorded_by=current_user.id, org_id=current_user.org_id)
    db.add(v)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="VisitorLog", resource_id=v.id, resource_label=f"visitor sign-in: {v.visitor_name}",
        metadata={"host": v.host_name}, severity="warning", request=request,
    )
    return _visitor_response(v)


@router.post("/visitors/{visitor_id}/signout", response_model=VisitorResponse, dependencies=[_adm_write])
async def sign_out_visitor(visitor_id: str, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    v = (await db.execute(select(VisitorLog).where(VisitorLog.id == visitor_id, VisitorLog.org_id == current_user.org_id, VisitorLog.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not v:
        raise HTTPException(status_code=404, detail="Visitor record not found.")
    v.status = "signed_out"
    v.sign_out_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="VisitorLog", resource_id=v.id, resource_label=f"visitor sign-out: {v.visitor_name}", request=request,
    )
    return _visitor_response(v)


@router.delete("/visitors/{visitor_id}", status_code=204, dependencies=[_adm_write])
async def delete_visitor(visitor_id: str, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    v = (await db.execute(select(VisitorLog).where(VisitorLog.id == visitor_id, VisitorLog.org_id == current_user.org_id, VisitorLog.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not v:
        raise HTTPException(status_code=404, detail="Visitor record not found.")
    # Safeguarding: soft-delete only + audited (never silently removed).
    v.is_deleted = True
    v.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
        resource_type="VisitorLog", resource_id=v.id, resource_label=f"visitor record removed: {v.visitor_name}",
        severity="warning", request=request,
    )


# ── Student Collection (the safeguarding-critical record) ────────────────────────

async def _collection_response(db, c: StudentCollection, org_id: str) -> CollectionResponse:
    return CollectionResponse(
        id=c.id, student_id=c.student_id, student_name=await _student_name(db, org_id, c.student_id),
        collector_name=c.collector_name, relationship_to_student=c.relationship_to_student,
        authorized_by=c.authorized_by, authorized_by_name=await _user_name(db, org_id, c.authorized_by),
        collected_at=c.collected_at, notes=c.notes, recorded_by=c.recorded_by, created_at=c.created_at, org_id=c.org_id,
    )


@router.get("/collections", response_model=CollectionListResponse, dependencies=[_adm_read])
async def list_collections(
    student_id: str | None = Query(default=None), page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    base = select(StudentCollection).where(StudentCollection.org_id == current_user.org_id, StudentCollection.is_deleted == False)  # noqa: E712
    if student_id:
        base = base.where(StudentCollection.student_id == student_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(base.order_by(StudentCollection.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return CollectionListResponse(items=[await _collection_response(db, c, current_user.org_id) for c in rows],
                                  total=total, page=page, page_size=page_size)


@router.post("/collections", response_model=CollectionResponse, status_code=201, dependencies=[_adm_write])
async def record_collection(payload: CollectionCreate, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    student = (await db.execute(select(Student).where(Student.id == payload.student_id, Student.org_id == current_user.org_id, Student.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not student:
        raise HTTPException(status_code=404, detail="student not found in your organisation.")
    # Safeguarding: the authoriser MUST be a real staff member in this org.
    authoriser = (await db.execute(select(User).where(User.id == payload.authorized_by, User.org_id == current_user.org_id, User.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not authoriser:
        raise HTTPException(status_code=404, detail="authorized_by: staff member not found in your organisation.")
    c = StudentCollection(
        student_id=student.id, collector_name=payload.collector_name, relationship_to_student=payload.relationship_to_student,
        authorized_by=authoriser.id, collected_at=payload.collected_at or datetime.now(timezone.utc), notes=payload.notes,
        recorded_by=current_user.id, org_id=current_user.org_id,
    )
    db.add(c)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="StudentCollection", resource_id=c.id,
        resource_label=f"child collection: {student.first_name} {student.last_name} by {c.collector_name}",
        metadata={"authorized_by": authoriser.id, "collector": c.collector_name}, severity="warning", request=request,
    )
    return await _collection_response(db, c, current_user.org_id)


@router.delete("/collections/{collection_id}", status_code=204, dependencies=[_adm_write])
async def delete_collection(collection_id: str, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(StudentCollection).where(StudentCollection.id == collection_id, StudentCollection.org_id == current_user.org_id, StudentCollection.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not c:
        raise HTTPException(status_code=404, detail="Collection record not found.")
    # Safeguarding: NEVER silently removed — soft-delete + audit (severity warning).
    c.is_deleted = True
    c.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
        resource_type="StudentCollection", resource_id=c.id, resource_label="child collection record removed",
        severity="warning", request=request,
    )
