"""School Attendance — Setup fields + the live Monitor.

Proves the extended settings (departure cutoff + notify toggles) round-trip, and
that the live monitor derives the right presence picture from check-in/out events:
who's on-site vs departed, late arrivals (after the min clock-in) and late
departures (after the max departure), plus the students-in-school + recent feeds.
"""
import uuid
from datetime import datetime, timezone, date, time

import pytest

from app.models.user import User, UserStatus
from app.models.role import Role
from app.models.modules.school import (
    AttendanceEvent, AttendanceEventType, AttendanceEventSource, AttendanceSettings, Student,
)
from app.routers.modules.school import get_attendance_settings, update_attendance_settings
from app.routers.modules.attendance import live_monitor
from app.schemas.attendance_config import AttendanceSettingsUpdate

pytestmark = pytest.mark.asyncio

DAY = date(2026, 6, 5)   # Lagos is UTC+1, so local = UTC + 1h


async def _staff(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"s-{uuid.uuid4().hex[:6]}@x.com", full_name="Staff",
             status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="admin", slug="org_admin",
                permissions=["school:students:read", "school:attendance:read"], org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _student(db, org, first, cls_id=None) -> Student:
    s = Student(id=str(uuid.uuid4()), student_id=f"S{uuid.uuid4().hex[:5]}", first_name=first,
                last_name="Test", class_id=cls_id, org_id=org.id, is_active=True)
    db.add(s)
    await db.flush()
    return s


def _ev(org, student, kind, hh_utc, mm_utc):
    return AttendanceEvent(
        id=str(uuid.uuid4()), student_id=student.id, event_type=kind,
        event_time=datetime(2026, 6, 5, hh_utc, mm_utc, tzinfo=timezone.utc),
        source=AttendanceEventSource.MANUAL, org_id=org.id,
    )


# ── Setup fields ────────────────────────────────────────────────────────────────

async def test_settings_departure_and_notify_roundtrip(db, org):
    staff = await _staff(db, org)
    s = await get_attendance_settings(db=db, current_user=staff)
    assert s.max_departure_time is None and s.notify_email is False and s.notify_sms is False

    upd = await update_attendance_settings(
        AttendanceSettingsUpdate(max_departure_time="17:00", notify_email=True, notify_sms=True),
        request=None, db=db, current_user=staff)
    assert upd.max_departure_time == "17:00" and upd.notify_email is True and upd.notify_sms is True
    # late_after_time (min clock-in) untouched by a partial update.
    assert upd.late_after_time


# ── Live monitor ────────────────────────────────────────────────────────────────

async def test_monitor_presence_late_arrival_and_late_departure(db, org, school_class):
    staff = await _staff(db, org)
    db.add(AttendanceSettings(id=str(uuid.uuid4()), org_id=org.id,
                              late_after_time=time(8, 0), max_departure_time=time(17, 0)))
    a = await _student(db, org, "Ada", school_class.id)     # on-site (no check-out)
    b = await _student(db, org, "Bola", school_class.id)    # late arrival, on-time departure
    c = await _student(db, org, "Chidi", school_class.id)   # on-time arrival, LATE departure
    db.add_all([
        _ev(org, a, AttendanceEventType.CHECK_IN, 6, 0),    # 07:00 Lagos
        _ev(org, b, AttendanceEventType.CHECK_IN, 7, 45),   # 08:45 Lagos → late
        _ev(org, b, AttendanceEventType.CHECK_OUT, 14, 15),  # 15:15 Lagos → on-time
        _ev(org, c, AttendanceEventType.CHECK_IN, 6, 0),    # 07:00 Lagos
        _ev(org, c, AttendanceEventType.CHECK_OUT, 16, 30),  # 17:30 Lagos → late departure
    ])
    await db.commit()

    m = await live_monitor(date=DAY, db=db, current_user=staff)
    assert m["checked_in"] == 3
    assert m["departed"] == 2 and m["remaining"] == 1
    assert m["late_arrivals"] == 1 and m["present_on_time"] == 2
    assert m["late_departures"] == 1 and m["early_departures"] == 1
    # On-site list is exactly Ada; late-departure log is exactly Chidi.
    assert [x["student_name"] for x in m["students_in_school"]] == ["Ada Test"]
    assert [x["student_name"] for x in m["late_departures_log"]] == ["Chidi Test"]
    assert m["min_clock_in"] == "08:00" and m["max_departure"] == "17:00"
    assert m["recent"]   # non-empty activity feed


async def test_monitor_is_staff_only(db, org):
    from fastapi import HTTPException
    u = User(id=str(uuid.uuid4()), email=f"p-{uuid.uuid4().hex[:6]}@x.com", full_name="Parent",
             status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="parent", slug="parent", permissions=["school:attendance:read"],
                org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    with pytest.raises(HTTPException) as ei:
        await live_monitor(date=DAY, db=db, current_user=u)
    assert ei.value.status_code == 403
