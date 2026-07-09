"""Tests for Attendance Setup — per-org late cutoff + absence reason codes."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import (
    Student, AttendanceRecord, AttendanceSettings, AbsenceReason, AttendanceStatus,
)
from app.routers.modules.school import (
    get_attendance_settings, update_attendance_settings,
    list_absence_reasons, create_absence_reason, update_absence_reason, delete_absence_reason,
)
from app.schemas.attendance_config import AttendanceSettingsUpdate, AbsenceReasonCreate, AbsenceReasonUpdate
from app.services.attendance import ingest, _late_after_for_org, default_late_after

pytestmark = pytest.mark.asyncio


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


def _checkin(student_id, dt):
    return SimpleNamespace(student_id=student_id, event_type="check_in", event_time=dt,
                           source="manual", external_ref=None, device_id=None)


# ── Settings ─────────────────────────────────────────────────────────────────────

async def test_settings_get_creates_default_then_update(db, org, teacher):
    s = await get_attendance_settings(db=db, current_user=teacher)
    assert s.late_after_time == default_late_after().strftime("%H:%M")  # env fallback default

    upd = await update_attendance_settings(AttendanceSettingsUpdate(late_after_time="09:15"),
                                           request=None, db=db, current_user=teacher)
    assert upd.late_after_time == "09:15"
    rows = (await db.execute(select(AttendanceSettings).where(AttendanceSettings.org_id == org.id))).scalars().all()
    assert len(rows) == 1 and rows[0].late_after_time == time(9, 15)


async def test_late_after_for_org_fallback_then_override(db, org):
    # no row -> env fallback
    assert await _late_after_for_org(db, org) == default_late_after()
    db.add(AttendanceSettings(org_id=org.id, late_after_time=time(9, 30)))
    await db.commit()
    # row -> per-org value
    assert await _late_after_for_org(db, org) == time(9, 30)


# ── Ingestion honours the configured cutoff ──────────────────────────────────────

async def test_ingest_uses_configured_cutoff(db, org, school_class):
    early = Student(id=str(uuid.uuid4()), student_id=f"STU-{uuid.uuid4().hex[:6]}",
                    first_name="Early", last_name="Bird", class_id=school_class.id, org_id=org.id)
    late = Student(id=str(uuid.uuid4()), student_id=f"STU-{uuid.uuid4().hex[:6]}",
                   first_name="Late", last_name="Riser", class_id=school_class.id, org_id=org.id)
    db.add_all([early, late, AttendanceSettings(org_id=org.id, late_after_time=time(9, 0))])
    await db.commit()

    day = datetime(2026, 5, 1, tzinfo=timezone.utc)
    await ingest(db, org, [
        _checkin(early.id, day.replace(hour=7, minute=30)),   # local before 09:00 -> PRESENT
        _checkin(late.id, day.replace(hour=9, minute=30)),    # local after 09:00 -> LATE
    ], notify_parents=False)
    await db.commit()

    async def _rec(sid):
        return (await db.execute(select(AttendanceRecord).where(
            AttendanceRecord.student_id == sid))).scalar_one()

    assert (await _rec(early.id)).status == AttendanceStatus.PRESENT
    assert (await _rec(late.id)).status == AttendanceStatus.LATE


# ── Absence reasons ──────────────────────────────────────────────────────────────

async def test_reasons_seed_and_crud(db, org, teacher):
    seeded = await list_absence_reasons(active_only=False, db=db, current_user=teacher)
    assert len(seeded) == 7 and any(r.code == "unauthorized" and r.is_authorized is False for r in seeded)

    created = await create_absence_reason(
        AbsenceReasonCreate(code="Sports Fixture", label="Sports fixture", is_authorized=True),
        db=db, current_user=teacher)
    assert created.code == "sports_fixture" and created.is_active is True

    upd = await update_absence_reason(created.id, AbsenceReasonUpdate(is_active=False), db=db, current_user=teacher)
    assert upd.is_active is False

    active = await list_absence_reasons(active_only=True, db=db, current_user=teacher)
    assert all(r.id != created.id for r in active)  # deactivated drops out


async def test_reason_delete_blocked_when_referenced(db, org, teacher, school_class):
    reason = await create_absence_reason(AbsenceReasonCreate(code="sick2", label="Sick"), db=db, current_user=teacher)
    student = Student(id=str(uuid.uuid4()), student_id=f"STU-{uuid.uuid4().hex[:6]}",
                      first_name="Ill", last_name="Kid", class_id=school_class.id, org_id=org.id)
    db.add(student)
    db.add(AttendanceRecord(id=str(uuid.uuid4()), student_id=student.id, class_id=school_class.id,
                            date=date(2026, 5, 1), status=AttendanceStatus.ABSENT,
                            reason_id=reason.id, org_id=org.id))
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await delete_absence_reason(reason.id, db=db, current_user=teacher)
    assert exc.value.status_code == 409  # blocked — deactivate instead

    # an unreferenced reason deletes fine
    spare = await create_absence_reason(AbsenceReasonCreate(code="spare", label="Spare"), db=db, current_user=teacher)
    await delete_absence_reason(spare.id, db=db, current_user=teacher)
    assert (await db.execute(select(AbsenceReason).where(AbsenceReason.id == spare.id))).scalar_one_or_none() is None


async def test_duplicate_reason_code_conflicts(db, org, teacher):
    await create_absence_reason(AbsenceReasonCreate(code="dup", label="Dup"), db=db, current_user=teacher)
    with pytest.raises(HTTPException) as exc:
        await create_absence_reason(AbsenceReasonCreate(code="dup", label="Dup 2"), db=db, current_user=teacher)
    assert exc.value.status_code == 409


# ── RBAC ─────────────────────────────────────────────────────────────────────────

async def test_attendance_config_rbac(db, org):
    admin = await _preset_user(db, org, "org_admin")
    assert admin.has_permission("settings:read") and admin.has_permission("settings:write")
    teacher = await _preset_user(db, org, "teacher")
    # teacher can READ reasons (marks attendance) but cannot MANAGE config
    assert teacher.has_permission("school:attendance:read")
    assert not teacher.has_permission("settings:write")
