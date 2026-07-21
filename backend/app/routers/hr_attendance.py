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
from math import radians, sin, cos, asin, sqrt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.hr_attendance import StaffAttendanceEvent, StaffClockType, StaffClockSource, StaffAttendanceSettings
from app.schemas.hr_attendance import (
    SelfClockCreate, AdminEventCreate, AttendanceEventResponse,
    AttendanceSettingsResponse, AttendanceSettingsUpdate,
)

router = APIRouter(prefix="/hr", tags=["HR — Access Control"])

_can_hr = Depends(PermissionChecker("hr:write"))


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points, in metres."""
    r = 6371000.0
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * r * asin(sqrt(a))


async def _get_settings(db: AsyncSession, org_id: str) -> StaffAttendanceSettings | None:
    return (await db.execute(select(StaffAttendanceSettings).where(StaffAttendanceSettings.org_id == org_id))).scalar_one_or_none()


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
    settings = await _get_settings(db, current_user.org_id)
    # Geofence enforcement — only when enabled AND a centre + radius are configured.
    if settings and settings.geofence_enabled and settings.geofence_lat is not None and settings.geofence_lng is not None and settings.geofence_radius_m:
        if payload.lat is None or payload.lng is None:
            raise HTTPException(status_code=422, detail="Location is required to clock in/out here.")
        dist = _haversine_m(settings.geofence_lat, settings.geofence_lng, payload.lat, payload.lng)
        if dist > settings.geofence_radius_m:
            raise HTTPException(status_code=422, detail=f"You’re outside the permitted area (about {int(dist)} m away).")

    e = StaffAttendanceEvent(
        staff_user_id=current_user.id, org_id=current_user.org_id,
        event_type=payload.event_type, event_time=datetime.now(timezone.utc),
        source=StaffClockSource.MANUAL, note=payload.note, recorded_by=current_user.id,
    )
    db.add(e)
    await db.flush()
    return _response(e, current_user.full_name)


# ── Configuration (Access Control › Configuration) ────────────────────────────

def _settings_response(s: StaffAttendanceSettings | None) -> AttendanceSettingsResponse:
    if not s:
        return AttendanceSettingsResponse(
            work_start_time=None, work_end_time=None, late_grace_minutes=0,
            geofence_enabled=False, geofence_lat=None, geofence_lng=None, geofence_radius_m=None,
        )
    return AttendanceSettingsResponse(
        work_start_time=s.work_start_time, work_end_time=s.work_end_time, late_grace_minutes=s.late_grace_minutes,
        geofence_enabled=s.geofence_enabled, geofence_lat=s.geofence_lat, geofence_lng=s.geofence_lng,
        geofence_radius_m=s.geofence_radius_m,
    )


@router.get("/attendance/settings", response_model=AttendanceSettingsResponse)
async def get_settings(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Readable by any staff — the clock UI needs work hours + geofence state."""
    return _settings_response(await _get_settings(db, current_user.org_id))


@router.put("/attendance/settings", response_model=AttendanceSettingsResponse, dependencies=[_can_hr])
async def update_settings(payload: AttendanceSettingsUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_settings(db, current_user.org_id)
    if not s:
        s = StaffAttendanceSettings(org_id=current_user.org_id)
        db.add(s)
    for f, v in payload.model_dump().items():
        setattr(s, f, v)
    await db.flush()
    return _settings_response(s)


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
