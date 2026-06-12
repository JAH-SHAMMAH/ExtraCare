"""
Attendance ingestion service tests.

Exercises the event-sourced core directly (the layer a future ZKTeco adapter
calls): event creation, daily-record derivation, idempotent dedup, and the
parent arrival/departure notification copy required by the brief.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.modules.school import (
    AttendanceEvent,
    AttendanceRecord,
    AttendanceStatus,
    ParentGuardian,
    Student,
)
from app.models.notification import Notification, TYPE_ATTENDANCE
from app.schemas.attendance import AttendanceEventIn
from app.services import attendance as attendance_service


async def _student_with_guardian(db, org, school_class, first="Ferdinand"):
    # Notification copy uses org.name; mirror the production org name here.
    org.name = "Fairview School"
    db.add(org)
    student = Student(
        id=str(uuid.uuid4()), student_id="FV-001", first_name=first, last_name="Okafor",
        class_id=school_class.id, org_id=org.id,
    )
    parent = User(
        id=str(uuid.uuid4()), email="parent@fairviewschoolng.com", full_name="Parent Okafor",
        status=UserStatus.ACTIVE, org_id=org.id,
    )
    db.add_all([student, parent])
    await db.flush()
    db.add(ParentGuardian(
        id=str(uuid.uuid4()), user_id=parent.id, student_id=student.id, org_id=org.id, is_primary=True,
    ))
    await db.commit()
    return student, parent


@pytest.mark.asyncio
async def test_check_in_creates_event_daily_record_and_parent_notification(db, org, school_class):
    student, parent = await _student_with_guardian(db, org, school_class)

    # 07:32 Africa/Lagos (UTC+1) == 06:32 UTC — before the 08:00 late cutoff.
    ev = AttendanceEventIn(
        student_id=student.id, event_type="check_in",
        event_time=datetime(2026, 6, 5, 6, 32, tzinfo=timezone.utc),
        source="zkteco", external_ref="PUNCH-1", device_id="DEV-1",
    )
    result = await attendance_service.ingest(db, org, [ev])
    await db.commit()

    assert result.created == 1
    assert result.notified == 1
    assert result.errors == []

    events = (await db.execute(select(AttendanceEvent).where(AttendanceEvent.student_id == student.id))).scalars().all()
    assert len(events) == 1

    recs = (await db.execute(select(AttendanceRecord).where(AttendanceRecord.student_id == student.id))).scalars().all()
    assert len(recs) == 1
    assert recs[0].status == AttendanceStatus.PRESENT  # 07:32 < 08:00

    notifs = (await db.execute(
        select(Notification).where(Notification.type == TYPE_ATTENDANCE, Notification.user_id == parent.id)
    )).scalars().all()
    assert len(notifs) == 1
    assert notifs[0].message == "Ferdinand has successfully checked into Fairview School at 7:32 AM."


@pytest.mark.asyncio
async def test_late_check_in_marks_record_late(db, org, school_class):
    student, _ = await _student_with_guardian(db, org, school_class)
    # 08:45 Lagos == 07:45 UTC — after the 08:00 cutoff.
    ev = AttendanceEventIn(
        student_id=student.id, event_type="check_in",
        event_time=datetime(2026, 6, 5, 7, 45, tzinfo=timezone.utc), source="manual",
    )
    await attendance_service.ingest(db, org, [ev])
    await db.commit()
    rec = (await db.execute(select(AttendanceRecord).where(AttendanceRecord.student_id == student.id))).scalar_one()
    assert rec.status == AttendanceStatus.LATE


@pytest.mark.asyncio
async def test_check_out_notification_copy(db, org, school_class):
    student, parent = await _student_with_guardian(db, org, school_class)
    # 15:15 Lagos == 14:15 UTC.
    ev = AttendanceEventIn(
        student_id=student.id, event_type="check_out",
        event_time=datetime(2026, 6, 5, 14, 15, tzinfo=timezone.utc), source="zkteco", external_ref="OUT-1",
    )
    result = await attendance_service.ingest(db, org, [ev])
    await db.commit()
    assert result.notified == 1
    notif = (await db.execute(
        select(Notification).where(Notification.type == TYPE_ATTENDANCE, Notification.user_id == parent.id)
    )).scalar_one()
    assert notif.message == "Ferdinand has successfully checked out of Fairview School at 3:15 PM."


@pytest.mark.asyncio
async def test_ingest_is_idempotent_on_external_ref(db, org, school_class):
    student, _ = await _student_with_guardian(db, org, school_class)
    ev = AttendanceEventIn(
        student_id=student.id, event_type="check_in",
        event_time=datetime(2026, 6, 5, 6, 30, tzinfo=timezone.utc),
        source="zkteco", external_ref="PUNCH-DUP",
    )
    r1 = await attendance_service.ingest(db, org, [ev])
    await db.commit()
    r2 = await attendance_service.ingest(db, org, [ev])
    await db.commit()

    assert r1.created == 1
    assert r2.created == 0
    assert r2.duplicates == 1
    events = (await db.execute(select(AttendanceEvent).where(AttendanceEvent.student_id == student.id))).scalars().all()
    assert len(events) == 1


@pytest.mark.asyncio
async def test_unknown_student_is_reported_not_raised(db, org, school_class):
    ev = AttendanceEventIn(student_id="does-not-exist", event_type="check_in", source="manual")
    result = await attendance_service.ingest(db, org, [ev])
    await db.commit()
    assert result.created == 0
    assert len(result.errors) == 1
    assert result.errors[0]["reason"] == "student_not_found"
