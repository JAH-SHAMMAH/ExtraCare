"""eClassroom module router, prefix ``/eclassroom``.

Setup (settings), Programs, and Schedules. A schedule going live REUSES the
existing LiveSession/WebRTC stack — go-live creates a LiveSession and links it, so
the frontend joins the same live room the rest of the portal already uses.

Gating: reads school:read, admin writes school:write.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.live import LiveSession
from app.models.modules.platform import SchoolSection, AcademicSession
from app.models.modules.school import YearGroup
from app.models.modules.eclassroom import EClassroomSettings, EClassroomProgram, EClassroomSchedule
from app.schemas.eclassroom import (
    SettingsResponse, SettingsUpdate,
    ProgramCreate, ProgramUpdate, ProgramResponse,
    ScheduleCreate, ScheduleUpdate, ScheduleResponse,
)

router = APIRouter(prefix="/eclassroom", tags=["eClassroom"])

_can_read = Depends(PermissionChecker("school:read"))
_can_write = Depends(PermissionChecker("school:write"))


async def _names(db: AsyncSession, org_id: str) -> tuple[dict, dict, dict]:
    """Batch id→name maps for sections / sessions / year groups (for display)."""
    sections = dict((r.id, r.name) for r in (await db.execute(
        select(SchoolSection).where(SchoolSection.org_id == org_id))).scalars().all())
    sessions = dict((r.id, r.name) for r in (await db.execute(
        select(AcademicSession).where(AcademicSession.org_id == org_id))).scalars().all())
    year_groups = dict((r.id, r.name) for r in (await db.execute(
        select(YearGroup).where(YearGroup.org_id == org_id))).scalars().all())
    return sections, sessions, year_groups


# ── Setup ─────────────────────────────────────────────────────────────────────

async def _get_settings(db: AsyncSession, org_id: str) -> EClassroomSettings | None:
    return (await db.execute(select(EClassroomSettings).where(EClassroomSettings.org_id == org_id))).scalar_one_or_none()


def _settings_response(s: EClassroomSettings | None) -> SettingsResponse:
    if not s:
        return SettingsResponse(can_teacher_publish=True, automatic_approval=False, learning_program_enabled=False)
    return SettingsResponse(can_teacher_publish=s.can_teacher_publish, automatic_approval=s.automatic_approval,
                            learning_program_enabled=s.learning_program_enabled)


@router.get("/settings", response_model=SettingsResponse, dependencies=[_can_read])
async def get_settings(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return _settings_response(await _get_settings(db, current_user.org_id))


@router.put("/settings", response_model=SettingsResponse, dependencies=[_can_write])
async def update_settings(payload: SettingsUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_settings(db, current_user.org_id)
    if not s:
        s = EClassroomSettings(org_id=current_user.org_id)
        db.add(s)
    for f, v in payload.model_dump().items():
        setattr(s, f, v)
    await db.flush()
    return _settings_response(s)


# ── Programs ──────────────────────────────────────────────────────────────────

def _program_response(p: EClassroomProgram, sections: dict, sessions: dict) -> ProgramResponse:
    return ProgramResponse(
        id=p.id, name=p.name, description=p.description, cbt_type=p.cbt_type,
        section_id=p.section_id, section_name=sections.get(p.section_id),
        session_id=p.session_id, session_name=sessions.get(p.session_id),
        is_active=p.is_active, created_at=p.created_at, org_id=p.org_id,
    )


@router.get("/programs", response_model=list[ProgramResponse], dependencies=[_can_read])
async def list_programs(
    session_id: str | None = Query(default=None),
    section_id: str | None = Query(default=None),
    cbt_type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    q = select(EClassroomProgram).where(EClassroomProgram.org_id == current_user.org_id, EClassroomProgram.is_deleted == False)  # noqa: E712
    if session_id:
        q = q.where(EClassroomProgram.session_id == session_id)
    if section_id:
        q = q.where(EClassroomProgram.section_id == section_id)
    if cbt_type:
        q = q.where(EClassroomProgram.cbt_type == cbt_type)
    rows = (await db.execute(q.order_by(EClassroomProgram.created_at.desc()))).scalars().all()
    sections, sessions, _ = await _names(db, current_user.org_id)
    return [_program_response(p, sections, sessions) for p in rows]


@router.post("/programs", response_model=ProgramResponse, status_code=201, dependencies=[_can_write])
async def create_program(payload: ProgramCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = EClassroomProgram(org_id=current_user.org_id, name=payload.name.strip(), description=(payload.description or None),
                          cbt_type=payload.cbt_type, section_id=payload.section_id, session_id=payload.session_id,
                          is_active=payload.is_active)
    db.add(p)
    await db.flush()
    sections, sessions, _ = await _names(db, current_user.org_id)
    return _program_response(p, sections, sessions)


async def _get_program(db, org_id, pid) -> EClassroomProgram:
    p = (await db.execute(select(EClassroomProgram).where(
        EClassroomProgram.id == pid, EClassroomProgram.org_id == org_id, EClassroomProgram.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not p:
        raise HTTPException(status_code=404, detail="Program not found.")
    return p


@router.patch("/programs/{pid}", response_model=ProgramResponse, dependencies=[_can_write])
async def update_program(pid: str, payload: ProgramUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = await _get_program(db, current_user.org_id, pid)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
    for f, v in data.items():
        setattr(p, f, v)
    await db.flush()
    sections, sessions, _ = await _names(db, current_user.org_id)
    return _program_response(p, sections, sessions)


@router.delete("/programs/{pid}", status_code=204, dependencies=[_can_write])
async def delete_program(pid: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = await _get_program(db, current_user.org_id, pid)
    p.is_deleted = True
    p.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Schedules (Manage eClassrooms + Live Broadcast) ───────────────────────────

def _schedule_response(s: EClassroomSchedule, sections: dict, sessions: dict, ygs: dict) -> ScheduleResponse:
    return ScheduleResponse(
        id=s.id, title=s.title, description=s.description,
        section_id=s.section_id, section_name=sections.get(s.section_id),
        session_id=s.session_id, session_name=sessions.get(s.session_id),
        year_group_id=s.year_group_id, year_group_name=ygs.get(s.year_group_id),
        scheduled_at=s.scheduled_at, status=s.status, live_session_id=s.live_session_id,
        created_at=s.created_at, org_id=s.org_id,
    )


@router.get("/schedules", response_model=list[ScheduleResponse], dependencies=[_can_read])
async def list_schedules(
    status: str | None = Query(default=None),
    year_group_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    q = select(EClassroomSchedule).where(EClassroomSchedule.org_id == current_user.org_id, EClassroomSchedule.is_deleted == False)  # noqa: E712
    if status == "live_new":                                # Educare's "Live & New" filter
        q = q.where(EClassroomSchedule.status.in_(("new", "live")))
    elif status:
        q = q.where(EClassroomSchedule.status == status)
    if year_group_id:
        q = q.where(EClassroomSchedule.year_group_id == year_group_id)
    if session_id:
        q = q.where(EClassroomSchedule.session_id == session_id)
    rows = (await db.execute(q.order_by(EClassroomSchedule.created_at.desc()))).scalars().all()
    sections, sessions, ygs = await _names(db, current_user.org_id)
    return [_schedule_response(s, sections, sessions, ygs) for s in rows]


@router.post("/schedules", response_model=ScheduleResponse, status_code=201, dependencies=[_can_write])
async def create_schedule(payload: ScheduleCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = EClassroomSchedule(
        org_id=current_user.org_id, title=payload.title.strip(), description=(payload.description or None),
        section_id=payload.section_id, session_id=payload.session_id, year_group_id=payload.year_group_id,
        scheduled_at=payload.scheduled_at, status="new",
    )
    db.add(s)
    await db.flush()
    sections, sessions, ygs = await _names(db, current_user.org_id)
    return _schedule_response(s, sections, sessions, ygs)


async def _get_schedule(db, org_id, sid) -> EClassroomSchedule:
    s = (await db.execute(select(EClassroomSchedule).where(
        EClassroomSchedule.id == sid, EClassroomSchedule.org_id == org_id, EClassroomSchedule.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found.")
    return s


@router.patch("/schedules/{sid}", response_model=ScheduleResponse, dependencies=[_can_write])
async def update_schedule(sid: str, payload: ScheduleUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_schedule(db, current_user.org_id, sid)
    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        data["title"] = data["title"].strip()
    for f, v in data.items():
        setattr(s, f, v)
    await db.flush()
    sections, sessions, ygs = await _names(db, current_user.org_id)
    return _schedule_response(s, sections, sessions, ygs)


@router.delete("/schedules/{sid}", status_code=204, dependencies=[_can_write])
async def delete_schedule(sid: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_schedule(db, current_user.org_id, sid)
    s.is_deleted = True
    s.deleted_at = datetime.now(timezone.utc)
    await db.flush()


@router.post("/schedules/{sid}/go-live", response_model=ScheduleResponse, dependencies=[_can_write])
async def go_live(sid: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Start a broadcast: create a real LiveSession (existing WebRTC infra), link
    it, and flip status → live. The frontend then joins the live room."""
    s = await _get_schedule(db, current_user.org_id, sid)
    if s.status == "live" and s.live_session_id:
        raise HTTPException(status_code=409, detail="This broadcast is already live.")
    now = datetime.now(timezone.utc)
    session = LiveSession(
        org_id=current_user.org_id, host_user_id=current_user.id,
        title=s.title, description=s.description, is_active=True, started_at=now,
    )
    db.add(session)
    await db.flush()
    s.live_session_id = session.id
    s.status = "live"
    await db.flush()
    sections, sessions, ygs = await _names(db, current_user.org_id)
    return _schedule_response(s, sections, sessions, ygs)


@router.post("/schedules/{sid}/end", response_model=ScheduleResponse, dependencies=[_can_write])
async def end_broadcast(sid: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_schedule(db, current_user.org_id, sid)
    now = datetime.now(timezone.utc)
    if s.live_session_id:
        live = (await db.execute(select(LiveSession).where(LiveSession.id == s.live_session_id))).scalar_one_or_none()
        if live and live.is_active:
            live.is_active = False
            live.ended_at = now
    s.status = "ended"
    await db.flush()
    sections, sessions, ygs = await _names(db, current_user.org_id)
    return _schedule_response(s, sections, sessions, ygs)
