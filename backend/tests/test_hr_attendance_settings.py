"""Access Control › Configuration — staff clock settings + geofence enforcement.

Settings persist (defaults until saved); geofencing, when enabled, is enforced at
self clock-in: inside the radius is allowed, outside (or missing coords) is refused.
Settings read is open to any staff (the clock UI needs them); write is hr:write.
"""
from __future__ import annotations

import uuid
from datetime import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.core.permissions import PermissionChecker
from app.models.hr_attendance import StaffClockType
from app.routers.hr_attendance import get_settings, update_settings, clock_self
from app.schemas.hr_attendance import AttendanceSettingsUpdate, SelfClockCreate

pytestmark = pytest.mark.asyncio


async def _staff(db, org, name) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{name}-{uuid.uuid4().hex[:5]}@example.com",
             full_name=name, status=UserStatus.ACTIVE, org_id=org.id)
    db.add(u)
    await db.commit()
    return u


async def _preset_user(db, org, slug) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def test_settings_defaults_and_persist(db, org, teacher):
    defaults = await get_settings(db=db, current_user=teacher)
    assert defaults.late_grace_minutes == 0 and defaults.geofence_enabled is False

    saved = await update_settings(AttendanceSettingsUpdate(work_start_time=time(8, 0), work_end_time=time(16, 0), late_grace_minutes=15),
                                  db=db, current_user=teacher)
    assert saved.work_start_time == time(8, 0) and saved.late_grace_minutes == 15
    # Re-read reflects it (upsert, single row per org).
    again = await get_settings(db=db, current_user=teacher)
    assert again.late_grace_minutes == 15 and again.work_end_time == time(16, 0)


async def test_geofence_enforced_inside_outside_missing(db, org, teacher):
    await update_settings(AttendanceSettingsUpdate(geofence_enabled=True, geofence_lat=6.5, geofence_lng=3.4, geofence_radius_m=100),
                          db=db, current_user=teacher)
    staff = await _staff(db, org, "Clocker")

    # Inside (~15 m away) → allowed.
    ev = await clock_self(SelfClockCreate(event_type=StaffClockType.CLOCK_IN, lat=6.5001, lng=3.4001), db=db, current_user=staff)
    assert ev.event_type == "clock_in"

    # Outside (~11 km away) → refused.
    with pytest.raises(HTTPException) as exc:
        await clock_self(SelfClockCreate(event_type=StaffClockType.CLOCK_IN, lat=6.6, lng=3.5), db=db, current_user=staff)
    assert exc.value.status_code == 422

    # Missing coordinates while geofencing is on → refused.
    with pytest.raises(HTTPException) as exc2:
        await clock_self(SelfClockCreate(event_type=StaffClockType.CLOCK_IN), db=db, current_user=staff)
    assert exc2.value.status_code == 422


async def test_geofence_disabled_ignores_coords(db, org, teacher):
    await update_settings(AttendanceSettingsUpdate(geofence_enabled=False), db=db, current_user=teacher)
    staff = await _staff(db, org, "Free Clocker")
    ev = await clock_self(SelfClockCreate(event_type=StaffClockType.CLOCK_IN), db=db, current_user=staff)  # no coords, still fine
    assert ev.staff_user_id == staff.id


async def _run_gate(user, org, db):
    checker = PermissionChecker("hr:write")
    request = SimpleNamespace(state=SimpleNamespace(org=org, org_id=org.id))
    return await checker(request=request, current_user=user, db=db)


async def test_settings_write_is_hr_write(db, org):
    tchr = await _preset_user(db, org, "teacher")
    assert not tchr.has_permission("hr:write")
    with pytest.raises(HTTPException) as exc:
        await _run_gate(tchr, org, db)
    assert exc.value.status_code == 403
    for slug in ("org_admin", "manager"):
        u = await _preset_user(db, org, slug)
        assert (await _run_gate(u, org, db)).id == u.id
