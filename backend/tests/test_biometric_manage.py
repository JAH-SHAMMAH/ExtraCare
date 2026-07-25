"""Tests for the enriched Manage Biometric: device specs, staff|student enrolment,
the Home summary, and the device command queue."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role
from app.models.modules.school import AttendanceEvent, AttendanceEventType, AttendanceEventSource
from app.routers.modules.biometric import (
    register_device, update_device, create_enrollment, list_enrollments,
    biometric_summary, generate_command, list_commands, delete_command,
)
from app.schemas.platform import DeviceCreate, DeviceUpdate, EnrollmentCreate, BiometricCommandCreate


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@example.com", full_name="Admin",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def _staff(db, org, name="Elizabeth Nwankwo", role="Super User") -> User:
    u = User(id=str(uuid.uuid4()), email=f"s-{uuid.uuid4().hex[:6]}@example.com", full_name=name,
             status=UserStatus.ACTIVE, org_id=org.id)
    r = Role(id=str(uuid.uuid4()), name=role, slug=f"r-{uuid.uuid4().hex[:6]}", permissions=[], org_id=org.id, is_system=False)
    db.add(r)
    u.roles = [r]
    db.add(u)
    await db.commit()
    return u


# ── Device specs ─────────────────────────────────────────────────────────────────

async def test_device_specs_create_and_update(db, org):
    admin = await _admin(db, org)
    d = await register_device(DeviceCreate(device_id="BQC2235300486", name="Main", model_name="MB360 Plus",
                                           vendor="ZKTeco CO., LTD.", firmware_version="v1.0.8",
                                           fingerprint_version="v10", face_version="v7", volume=90, language="English"),
                              db=db, current_user=admin)
    assert d.model_name == "MB360 Plus" and d.firmware_version == "v1.0.8" and d.fingerprint_version == "v10"
    upd = await update_device(d.id, DeviceUpdate(mac_address="00:17:61:12:f9:74", storage_used_percent=56), db=db, current_user=admin)
    assert upd.mac_address == "00:17:61:12:f9:74" and upd.storage_used_percent == 56 and upd.model_name == "MB360 Plus"


# ── Enrolment: student OR staff ──────────────────────────────────────────────────

async def test_enrollment_student_and_staff(db, org, student):
    admin = await _admin(db, org)
    coach = await _staff(db, org)

    s = await create_enrollment(EnrollmentCreate(biometric_user_id="1007", student_id=student.id, fingerprint_count=2), db=db, current_user=admin)
    assert s.person_type == "student" and s.person_name == "Ada Okafor" and s.fingerprint_count == 2

    t = await create_enrollment(EnrollmentCreate(biometric_user_id="1007E", user_id=coach.id, has_face=True), db=db, current_user=admin)
    assert t.person_type == "staff" and t.person_name == "Elizabeth Nwankwo" and t.role_name == "Super User" and t.has_face is True

    assert len(await list_enrollments(db=db, current_user=admin)) == 2

    # Exactly one target required.
    with pytest.raises(HTTPException) as exc:
        await create_enrollment(EnrollmentCreate(biometric_user_id="x", student_id=student.id, user_id=coach.id), db=db, current_user=admin)
    assert exc.value.status_code == 422
    with pytest.raises(HTTPException) as exc:
        await create_enrollment(EnrollmentCreate(biometric_user_id="y"), db=db, current_user=admin)
    assert exc.value.status_code == 422


# ── Home summary ─────────────────────────────────────────────────────────────────

async def test_summary_counts(db, org, student):
    admin = await _admin(db, org)
    await register_device(DeviceCreate(device_id="D1", name="Main"), db=db, current_user=admin)
    await create_enrollment(EnrollmentCreate(biometric_user_id="u1", student_id=student.id, fingerprint_count=1, has_face=True, has_card=True), db=db, current_user=admin)
    db.add(AttendanceEvent(id=str(uuid.uuid4()), student_id=student.id, event_type=AttendanceEventType.CHECK_IN,
                           event_time=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                           source=AttendanceEventSource.BIOMETRIC if hasattr(AttendanceEventSource, "BIOMETRIC") else AttendanceEventSource.MANUAL,
                           org_id=org.id))
    await db.commit()
    s = await biometric_summary(db=db, current_user=admin)
    assert s.total_devices == 1 and s.total_device_users == 1
    assert s.total_fingerprint == 1 and s.total_face == 1 and s.total_card == 1
    assert s.total_active_users == 1 and s.total_attendance == 1


# ── Commands ─────────────────────────────────────────────────────────────────────

async def test_command_generate_list_delete(db, org):
    admin = await _admin(db, org)
    d = await register_device(DeviceCreate(device_id="D9", name="Main"), db=db, current_user=admin)
    c = await generate_command(d.id, BiometricCommandCreate(command="Backup User Data from device"), db=db, current_user=admin)
    assert c.status == "pending" and c.device_id == "D9" and c.command == "Backup User Data from device"

    listing = await list_commands(device_pk=None, db=db, current_user=admin)
    assert len(listing) == 1 and listing[0].device_id == "D9"

    await delete_command(c.id, db=db, current_user=admin)
    assert len(await list_commands(device_pk=None, db=db, current_user=admin)) == 0
