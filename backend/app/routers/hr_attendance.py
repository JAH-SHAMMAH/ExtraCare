"""Staff attendance router (HR Access Control), prefix ``/hr``.

Two audiences on one clock log:
  • Self-service (any authenticated staff): clock IN/OUT and read your OWN punches.
    Pinned to current_user.id — can't touch anyone else's record.
  • Admin (hr:write): the full staff clock log, add/correct a punch, remove one.

ENDPOINTS:
  POST   /hr/attendance/clock        — clock SELF in/out (self-service)
  GET    /hr/attendance/my           — my own punches (self-service)
  GET    /hr/attendance/events       — full staff log (hr:write; filters)
  POST   /hr/attendance/events       — add a punch for any staff (hr:write)
  DELETE /hr/attendance/events/{id}  — remove a punch (hr:write)
"""
from __future__ import annotations

from datetime import datetime, timezone, date, time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.hr_attendance import StaffAttendanceEvent, StaffClockType, StaffClockSource
from app.schemas.hr_attendance import SelfClockCreate, AdminEventCreate, AttendanceEventResponse

router = APIRouter(prefix="/hr", tags=["HR — Access Control"])

_can_hr = Depends(PermissionChecker("hr:write"))


def _response(e: StaffAttendanceEvent, staff_name: str | None = None) -> AttendanceEventResponse:
    return AttendanceEventResponse(
        id=e.id, staff_user_id=e.staff_user_id, staff_name=staff_name,
        event_type=e.event_type.value if hasattr(e.event_type, "value") else e.event_type,
        event_time=e.event_time,
        source=e.source.value if hasattr(e.source, "value") else e.source,
        note=e.note, created_at=e.created_at,
    )


# ── Self-service ──────────────────────────────────────────────────────────────

@router.post("/attendance/clock", response_model=AttendanceEventResponse, status_code=201)
async def clock_self(payload: SelfClockCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    e = StaffAttendanceEvent(
        staff_user_id=current_user.id, org_id=current_user.org_id,
        event_type=payload.event_type, event_time=datetime.now(timezone.utc),
        source=StaffClockSource.MANUAL, note=payload.note, recorded_by=current_user.id,
    )
    db.add(e)
    await db.flush()
    return _response(e, current_user.full_name)


@router.get("/attendance/my", response_model=list[AttendanceEventResponse])
async def list_my_attendance(
    limit: int = Query(default=200, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows = (await db.execute(
        select(StaffAttendanceEvent).where(
            StaffAttendanceEvent.org_id == current_user.org_id,
            StaffAttendanceEvent.staff_user_id == current_user.id,
        ).order_by(StaffAttendanceEvent.event_time.desc()).limit(limit)
    )).scalars().all()
    return [_response(e, current_user.full_name) for e in rows]


# ── Admin log (hr:write) ──────────────────────────────────────────────────────

@router.get("/attendance/events", response_model=list[AttendanceEventResponse], dependencies=[_can_hr])
async def list_events(
    staff_user_id: str | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    limit: int = Query(default=500, le=2000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(StaffAttendanceEvent).where(StaffAttendanceEvent.org_id == current_user.org_id)
    if staff_user_id:
        q = q.where(StaffAttendanceEvent.staff_user_id == staff_user_id)
    if from_date:
        q = q.where(StaffAttendanceEvent.event_time >= datetime.combine(from_date, time.min, tzinfo=timezone.utc))
    if to_date:
        q = q.where(StaffAttendanceEvent.event_time <= datetime.combine(to_date, time.max, tzinfo=timezone.utc))
    rows = (await db.execute(q.order_by(StaffAttendanceEvent.event_time.desc()).limit(limit))).scalars().all()

    # Resolve staff names in one query.
    ids = {e.staff_user_id for e in rows}
    names = dict((uid, name) for uid, name in (await db.execute(
        select(User.id, User.full_name).where(User.id.in_(ids))
    )).all()) if ids else {}
    return [_response(e, names.get(e.staff_user_id)) for e in rows]


@router.post("/attendance/events", response_model=AttendanceEventResponse, status_code=201, dependencies=[_can_hr])
async def create_event(payload: AdminEventCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    staff = (await db.execute(select(User).where(
        User.id == payload.staff_user_id, User.org_id == current_user.org_id, User.is_deleted == False  # noqa: E712
    ))).scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found.")
    e = StaffAttendanceEvent(
        staff_user_id=staff.id, org_id=current_user.org_id,
        event_type=payload.event_type,
        event_time=payload.event_time or datetime.now(timezone.utc),
        source=StaffClockSource.MANUAL, note=payload.note, recorded_by=current_user.id,
    )
    db.add(e)
    await db.flush()
    return _response(e, staff.full_name)


@router.delete("/attendance/events/{event_id}", status_code=204, dependencies=[_can_hr])
async def delete_event(event_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    e = (await db.execute(select(StaffAttendanceEvent).where(
        StaffAttendanceEvent.id == event_id, StaffAttendanceEvent.org_id == current_user.org_id
    ))).scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="Event not found.")
    await db.delete(e)
    await db.flush()
