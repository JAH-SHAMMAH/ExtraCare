"""Tests for staff attendance (HR Access Control) — clock log + self-service.

Self endpoints (clock / my) are pinned to current_user.id and can't touch another
staff member's record; the admin log + add/delete are gated hr:write. Proven by
calling the router functions directly and exercising the exact PermissionChecker.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.core.permissions import PermissionChecker
from app.models.hr_attendance import StaffClockType
from app.routers.hr_attendance import (
    clock_self, list_my_attendance, list_events, create_event, delete_event,
)
from app.schemas.hr_attendance import SelfClockCreate, AdminEventCreate

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


# ── Self-service ──────────────────────────────────────────────────────────────

async def test_clock_self_creates_own_event(db, org, teacher):
    ev = await clock_self(SelfClockCreate(event_type=StaffClockType.CLOCK_IN), db=db, current_user=teacher)
    assert ev.staff_user_id == teacher.id
    assert ev.event_type == "clock_in"          # serialised by value
    assert ev.source == "manual"


async def test_my_returns_only_own(db, org, teacher):
    other = await _staff(db, org, "Someone Else")
    await clock_self(SelfClockCreate(event_type=StaffClockType.CLOCK_IN), db=db, current_user=teacher)
    await clock_self(SelfClockCreate(event_type=StaffClockType.CLOCK_OUT), db=db, current_user=teacher)
    await clock_self(SelfClockCreate(event_type=StaffClockType.CLOCK_IN), db=db, current_user=other)

    mine = await list_my_attendance(limit=200, db=db, current_user=teacher)
    assert len(mine) == 2
    assert all(e.staff_user_id == teacher.id for e in mine)


# ── Admin log ─────────────────────────────────────────────────────────────────

async def test_admin_log_sees_all_and_filters_by_staff(db, org, teacher):
    a = await _staff(db, org, "Alpha")
    b = await _staff(db, org, "Beta")
    await clock_self(SelfClockCreate(event_type=StaffClockType.CLOCK_IN), db=db, current_user=a)
    await clock_self(SelfClockCreate(event_type=StaffClockType.CLOCK_IN), db=db, current_user=b)

    all_rows = await list_events(staff_user_id=None, from_date=None, to_date=None, limit=500, db=db, current_user=teacher)
    assert {a.id, b.id} <= {e.staff_user_id for e in all_rows}
    assert any(e.staff_name == "Alpha" for e in all_rows)   # name resolved

    only_a = await list_events(staff_user_id=a.id, from_date=None, to_date=None, limit=500, db=db, current_user=teacher)
    assert only_a and all(e.staff_user_id == a.id for e in only_a)


async def test_admin_add_event_for_staff(db, org, teacher):
    staff = await _staff(db, org, "Grace")
    when = datetime.now(timezone.utc) - timedelta(hours=3)
    ev = await create_event(AdminEventCreate(staff_user_id=staff.id, event_type=StaffClockType.CLOCK_IN, event_time=when, note="Backfill"),
                            db=db, current_user=teacher)
    assert ev.staff_user_id == staff.id and ev.note == "Backfill"


async def test_admin_add_unknown_staff_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_event(AdminEventCreate(staff_user_id="nope", event_type=StaffClockType.CLOCK_IN),
                           db=db, current_user=teacher)
    assert exc.value.status_code == 404


async def test_delete_event(db, org, teacher):
    staff = await _staff(db, org, "Del Me")
    ev = await create_event(AdminEventCreate(staff_user_id=staff.id, event_type=StaffClockType.CLOCK_IN),
                            db=db, current_user=teacher)
    await delete_event(ev.id, db=db, current_user=teacher)
    remaining = await list_events(staff_user_id=staff.id, from_date=None, to_date=None, limit=500, db=db, current_user=teacher)
    assert ev.id not in [e.id for e in remaining]


async def test_admin_log_org_scoped(db, org, teacher):
    staff = await _staff(db, org, "Mine")
    await clock_self(SelfClockCreate(event_type=StaffClockType.CLOCK_IN), db=db, current_user=staff)
    other = SimpleNamespace(org_id=str(uuid.uuid4()))
    rows = await list_events(staff_user_id=None, from_date=None, to_date=None, limit=500, db=db, current_user=other)
    assert staff.id not in [e.staff_user_id for e in rows]


# ── RBAC (the admin log is hr:write) ──────────────────────────────────────────

async def _run_gate(user, org, db):
    checker = PermissionChecker("hr:write")
    request = SimpleNamespace(state=SimpleNamespace(org=org, org_id=org.id))
    return await checker(request=request, current_user=user, db=db)


async def test_admin_log_rbac(db, org):
    tchr = await _preset_user(db, org, "teacher")
    assert tchr.has_permission("hr:read") and not tchr.has_permission("hr:write")
    with pytest.raises(HTTPException) as exc:
        await _run_gate(tchr, org, db)
    assert exc.value.status_code == 403
    for slug in ("org_admin", "manager"):
        u = await _preset_user(db, org, slug)
        assert (await _run_gate(u, org, db)).id == u.id
