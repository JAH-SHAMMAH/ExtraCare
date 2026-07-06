"""Tests for HR: Appointment Manager (staff appointment / contract history).

Confidential salary data — every endpoint is gated ``hr:write`` (like recruitment
/ disciplinary). These prove the CRUD behaviour AND that the gate excludes
finance-only accountants (who hold payments:write but NOT hr:write) and hr:read
teachers, by exercising the exact PermissionChecker the router uses.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.core.permissions import PermissionChecker
from app.models.hr_extended import StaffAppointment
from app.routers.hr_extended import (
    create_appointment, update_appointment, delete_appointment, list_appointments,
)
from app.schemas.hr_extended import AppointmentCreate, AppointmentUpdate


pytestmark = pytest.mark.asyncio


async def _staff(db, org, name) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{name}-{uuid.uuid4().hex[:6]}@example.com",
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


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def test_create_appointment(db, org, teacher):
    staff = await _staff(db, org, "Grace Bello")
    a = await create_appointment(
        AppointmentCreate(staff_user_id=staff.id, appointment_type="appointment", title="Senior Teacher",
                          grade="TS3", salary=180000, effective_date=None, reference="APT/2026/017"),
        request=None, db=db, current_user=teacher,
    )
    assert a.status == "active"
    assert a.title == "Senior Teacher" and a.grade == "TS3"
    assert a.salary == 180000.0 and a.salary_currency == "NGN"
    assert a.staff_name == "Grace Bello"


async def test_create_unknown_staff_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_appointment(AppointmentCreate(staff_user_id="nope", title="X"),
                                 request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 404


async def test_create_bad_type_422(db, org, teacher):
    staff = await _staff(db, org, "Test One")
    with pytest.raises(HTTPException) as exc:
        await create_appointment(AppointmentCreate(staff_user_id=staff.id, appointment_type="nonsense", title="X"),
                                 request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_create_negative_salary_422(db, org, teacher):
    staff = await _staff(db, org, "Test Two")
    with pytest.raises(HTTPException) as exc:
        await create_appointment(AppointmentCreate(staff_user_id=staff.id, title="X", salary=Decimal("-1")),
                                 request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_list_filters_by_staff(db, org, teacher):
    s1 = await _staff(db, org, "Alpha One")
    s2 = await _staff(db, org, "Beta Two")
    await create_appointment(AppointmentCreate(staff_user_id=s1.id, title="Teacher"), request=None, db=db, current_user=teacher)
    await create_appointment(AppointmentCreate(staff_user_id=s1.id, appointment_type="promotion", title="Head Teacher"), request=None, db=db, current_user=teacher)
    await create_appointment(AppointmentCreate(staff_user_id=s2.id, title="Bursar"), request=None, db=db, current_user=teacher)
    for_s1 = await list_appointments(staff_user_id=s1.id, status=None, db=db, current_user=teacher)
    assert len(for_s1) == 2 and all(x.staff_user_id == s1.id for x in for_s1)


async def test_update_status_and_salary(db, org, teacher):
    staff = await _staff(db, org, "Carl Three")
    a = await create_appointment(AppointmentCreate(staff_user_id=staff.id, title="Teacher", grade="TS2", salary=150000),
                                 request=None, db=db, current_user=teacher)
    updated = await update_appointment(a.id, AppointmentUpdate(status="ended", salary=160000, grade="TS3"),
                                       request=None, db=db, current_user=teacher)
    assert updated.status == "ended" and updated.salary == 160000.0 and updated.grade == "TS3"


async def test_delete_appointment(db, org, teacher):
    staff = await _staff(db, org, "Dora Four")
    a = await create_appointment(AppointmentCreate(staff_user_id=staff.id, title="Teacher"),
                                 request=None, db=db, current_user=teacher)
    await delete_appointment(a.id, db=db, current_user=teacher)
    assert all(x.id != a.id for x in await list_appointments(staff_user_id=None, status=None, db=db, current_user=teacher))
    with pytest.raises(HTTPException) as exc:
        await update_appointment(a.id, AppointmentUpdate(title="Z"), request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 404


# ── RBAC (exercise the exact hr:write gate the router uses) ────────────────────

async def _run_gate(user, org, db):
    checker = PermissionChecker("hr:write")
    request = SimpleNamespace(state=SimpleNamespace(org=org, org_id=org.id))
    return await checker(request=request, current_user=user, db=db)


async def test_appointment_rbac_excludes_accountant_and_teachers(db, org):
    # Gated hr:write. Accountant holds payments:write (can reach a finance route)
    # but NOT hr:write, so they must be blocked from staff-salary data. Teachers
    # hold hr:read only. Managers/admins pass.
    accountant = await _preset_user(db, org, "accountant")
    assert accountant.has_permission("payments:write")     # finance role…
    assert not accountant.has_permission("hr:write")       # …but NOT HR
    with pytest.raises(HTTPException) as exc:
        await _run_gate(accountant, org, db)
    assert exc.value.status_code == 403

    tchr = await _preset_user(db, org, "teacher")
    assert tchr.has_permission("hr:read") and not tchr.has_permission("hr:write")
    with pytest.raises(HTTPException) as exc:
        await _run_gate(tchr, org, db)
    assert exc.value.status_code == 403

    for slug in ("org_admin", "manager"):
        u = await _preset_user(db, org, slug)
        granted = await _run_gate(u, org, db)
        assert granted.id == u.id
