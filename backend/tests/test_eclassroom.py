"""Tests for the eClassroom module — Setup, Programs, Schedules, Live Broadcast.

The important behaviour: a schedule going live REUSES the existing LiveSession
infra (creates + links a real LiveSession), and ending it deactivates that
session. Gated school:write for admin writes.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.core.permissions import PermissionChecker
from app.models.live import LiveSession
from app.routers.modules.eclassroom import (
    get_settings, update_settings,
    list_programs, create_program, update_program, delete_program,
    list_schedules, create_schedule, update_schedule, delete_schedule, go_live, end_broadcast,
)
from app.schemas.eclassroom import SettingsUpdate, ProgramCreate, ProgramUpdate, ScheduleCreate, ScheduleUpdate

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


# ── Setup ─────────────────────────────────────────────────────────────────────

async def test_settings_roundtrip(db, org, teacher):
    defaults = await get_settings(db=db, current_user=teacher)
    assert defaults.can_teacher_publish is True and defaults.automatic_approval is False

    await update_settings(SettingsUpdate(can_teacher_publish=False, automatic_approval=True, learning_program_enabled=True),
                          db=db, current_user=teacher)
    reloaded = await get_settings(db=db, current_user=teacher)
    assert reloaded.can_teacher_publish is False and reloaded.automatic_approval is True and reloaded.learning_program_enabled is True


# ── Programs ──────────────────────────────────────────────────────────────────

async def test_program_crud(db, org, teacher):
    p = await create_program(ProgramCreate(name="  JSS Maths CBT  ", cbt_type="student"), db=db, current_user=teacher)
    assert p.name == "JSS Maths CBT" and p.cbt_type == "student"
    listed = await list_programs(session_id=None, section_id=None, cbt_type=None, db=db, current_user=teacher)
    assert [x.id for x in listed] == [p.id]
    upd = await update_program(p.id, ProgramUpdate(name="Renamed", is_active=False), db=db, current_user=teacher)
    assert upd.name == "Renamed" and upd.is_active is False
    await delete_program(p.id, db=db, current_user=teacher)
    assert p.id not in [x.id for x in await list_programs(session_id=None, section_id=None, cbt_type=None, db=db, current_user=teacher)]


# ── Schedules + Live Broadcast ────────────────────────────────────────────────

async def test_schedule_crud_and_filter(db, org, teacher):
    s = await create_schedule(ScheduleCreate(title="Year 9 Assembly"), db=db, current_user=teacher)
    assert s.status == "new"
    live_new = await list_schedules(status="live_new", year_group_id=None, session_id=None, db=db, current_user=teacher)
    assert s.id in [x.id for x in live_new]           # "new" is part of Live & New
    await update_schedule(s.id, ScheduleUpdate(title="Renamed Assembly"), db=db, current_user=teacher)
    await delete_schedule(s.id, db=db, current_user=teacher)
    assert s.id not in [x.id for x in await list_schedules(status=None, year_group_id=None, session_id=None, db=db, current_user=teacher)]


async def test_go_live_reuses_livesession(db, org, teacher):
    s = await create_schedule(ScheduleCreate(title="Live Physics"), db=db, current_user=teacher)
    live = await go_live(s.id, db=db, current_user=teacher)
    assert live.status == "live" and live.live_session_id

    # A real LiveSession was created + linked (the existing WebRTC infra).
    sess = (await db.execute(select(LiveSession).where(LiveSession.id == live.live_session_id))).scalar_one()
    assert sess.is_active is True and sess.title == "Live Physics" and sess.host_user_id == teacher.id

    # Going live again is a no-op error.
    with pytest.raises(HTTPException) as exc:
        await go_live(s.id, db=db, current_user=teacher)
    assert exc.value.status_code == 409

    # Ending deactivates the LiveSession + flips status.
    ended = await end_broadcast(s.id, db=db, current_user=teacher)
    assert ended.status == "ended"
    sess2 = (await db.execute(select(LiveSession).where(LiveSession.id == live.live_session_id))).scalar_one()
    assert sess2.is_active is False and sess2.ended_at is not None


async def test_org_isolation(db, org, teacher):
    s = await create_schedule(ScheduleCreate(title="Mine"), db=db, current_user=teacher)
    other = SimpleNamespace(org_id=str(uuid.uuid4()))
    assert s.id not in [x.id for x in await list_schedules(status=None, year_group_id=None, session_id=None, db=db, current_user=other)]
    with pytest.raises(HTTPException) as exc:
        await go_live(s.id, db=db, current_user=other)
    assert exc.value.status_code == 404


# ── RBAC (admin writes gated school:write) ────────────────────────────────────

async def _run_gate(user, org, db):
    checker = PermissionChecker("school:write")
    request = SimpleNamespace(state=SimpleNamespace(org=org, org_id=org.id))
    return await checker(request=request, current_user=user, db=db)


async def test_eclassroom_write_rbac(db, org):
    parent = await _preset_user(db, org, "parent")
    assert not parent.has_permission("school:write")
    with pytest.raises(HTTPException) as exc:
        await _run_gate(parent, org, db)
    assert exc.value.status_code == 403
    tchr = await _preset_user(db, org, "teacher")
    assert (await _run_gate(tchr, org, db)).id == tchr.id
