"""TimeTable module router, prefix ``/timetable``.

Setup (settings + period/subject groups) and Manage Activities. Periods,
schedules, curriculum, and the Time Tabler are added in later batches. Org-wide
(the single-school portal drops Educare's per-school scoping). Gated
``school:read`` / ``school:write``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.tenant import require_module
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.modules.school import TimetableSettings, PeriodGroup, SubjectGroup, SchoolActivity
from app.schemas.timetable import (
    TimetableSettingsResponse, TimetableSettingsUpdate,
    PeriodGroupCreate, PeriodGroupUpdate, PeriodGroupResponse,
    SubjectGroupCreate, SubjectGroupUpdate, SubjectGroupResponse,
    SchoolActivityCreate, SchoolActivityUpdate, SchoolActivityResponse,
)

router = APIRouter(
    prefix="/timetable",
    tags=["TimeTable"],
    dependencies=[Depends(require_module("school"))],
)

_can_read = Depends(PermissionChecker("school:timetable:read"))
_can_write = Depends(PermissionChecker("school:timetable:write"))


# ── Settings ──────────────────────────────────────────────────────────────────

async def _get_or_create_settings(db: AsyncSession, org_id: str) -> TimetableSettings:
    s = (await db.execute(select(TimetableSettings).where(TimetableSettings.org_id == org_id))).scalar_one_or_none()
    if not s:
        s = TimetableSettings(org_id=org_id)
        db.add(s)
        await db.flush()
    return s


@router.get("/settings", response_model=TimetableSettingsResponse, dependencies=[_can_read])
async def get_settings(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return TimetableSettingsResponse.model_validate(await _get_or_create_settings(db, current_user.org_id))


@router.put("/settings", response_model=TimetableSettingsResponse, dependencies=[_can_write])
async def update_settings(payload: TimetableSettingsUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_or_create_settings(db, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("default_period_group_id"):
        pg = (await db.execute(select(PeriodGroup).where(PeriodGroup.id == data["default_period_group_id"], PeriodGroup.org_id == current_user.org_id))).scalar_one_or_none()
        if not pg:
            raise HTTPException(status_code=404, detail="Period group not found.")
    for k, v in data.items():
        setattr(s, k, v)
    await db.flush()
    return TimetableSettingsResponse.model_validate(s)


# ── Period groups ─────────────────────────────────────────────────────────────

@router.get("/period-groups", dependencies=[_can_read])
async def list_period_groups(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(PeriodGroup).where(PeriodGroup.org_id == current_user.org_id).order_by(PeriodGroup.name))).scalars().all()
    return {"items": [PeriodGroupResponse.model_validate(r).model_dump() for r in rows]}


@router.post("/period-groups", status_code=201, dependencies=[_can_write])
async def create_period_group(payload: PeriodGroupCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    pg = PeriodGroup(**payload.model_dump(), org_id=current_user.org_id)
    db.add(pg)
    await db.flush()
    return PeriodGroupResponse.model_validate(pg).model_dump()


@router.patch("/period-groups/{group_id}", dependencies=[_can_write])
async def update_period_group(group_id: str, payload: PeriodGroupUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    pg = (await db.execute(select(PeriodGroup).where(PeriodGroup.id == group_id, PeriodGroup.org_id == current_user.org_id))).scalar_one_or_none()
    if not pg:
        raise HTTPException(status_code=404, detail="Period group not found.")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(pg, k, v)
    await db.flush()
    return PeriodGroupResponse.model_validate(pg).model_dump()


@router.delete("/period-groups/{group_id}", status_code=204, dependencies=[_can_write])
async def delete_period_group(group_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    pg = (await db.execute(select(PeriodGroup).where(PeriodGroup.id == group_id, PeriodGroup.org_id == current_user.org_id))).scalar_one_or_none()
    if not pg:
        raise HTTPException(status_code=404, detail="Period group not found.")
    await db.delete(pg)


# ── Subject groups ────────────────────────────────────────────────────────────

@router.get("/subject-groups", dependencies=[_can_read])
async def list_subject_groups(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(SubjectGroup).where(SubjectGroup.org_id == current_user.org_id).order_by(SubjectGroup.name))).scalars().all()
    return {"items": [SubjectGroupResponse.model_validate(r).model_dump() for r in rows]}


@router.post("/subject-groups", status_code=201, dependencies=[_can_write])
async def create_subject_group(payload: SubjectGroupCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    sg = SubjectGroup(**payload.model_dump(), org_id=current_user.org_id)
    db.add(sg)
    await db.flush()
    return SubjectGroupResponse.model_validate(sg).model_dump()


@router.patch("/subject-groups/{group_id}", dependencies=[_can_write])
async def update_subject_group(group_id: str, payload: SubjectGroupUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    sg = (await db.execute(select(SubjectGroup).where(SubjectGroup.id == group_id, SubjectGroup.org_id == current_user.org_id))).scalar_one_or_none()
    if not sg:
        raise HTTPException(status_code=404, detail="Subject group not found.")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(sg, k, v)
    await db.flush()
    return SubjectGroupResponse.model_validate(sg).model_dump()


@router.delete("/subject-groups/{group_id}", status_code=204, dependencies=[_can_write])
async def delete_subject_group(group_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    sg = (await db.execute(select(SubjectGroup).where(SubjectGroup.id == group_id, SubjectGroup.org_id == current_user.org_id))).scalar_one_or_none()
    if not sg:
        raise HTTPException(status_code=404, detail="Subject group not found.")
    await db.delete(sg)


# ── Activities ────────────────────────────────────────────────────────────────

@router.get("/activities", dependencies=[_can_read])
async def list_activities(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(SchoolActivity).where(SchoolActivity.org_id == current_user.org_id).order_by(SchoolActivity.name))).scalars().all()
    return {"items": [SchoolActivityResponse.model_validate(r).model_dump() for r in rows]}


@router.post("/activities", status_code=201, dependencies=[_can_write])
async def create_activity(payload: SchoolActivityCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    a = SchoolActivity(**payload.model_dump(), org_id=current_user.org_id)
    db.add(a)
    await db.flush()
    return SchoolActivityResponse.model_validate(a).model_dump()


@router.patch("/activities/{activity_id}", dependencies=[_can_write])
async def update_activity(activity_id: str, payload: SchoolActivityUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    a = (await db.execute(select(SchoolActivity).where(SchoolActivity.id == activity_id, SchoolActivity.org_id == current_user.org_id))).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Activity not found.")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    await db.flush()
    return SchoolActivityResponse.model_validate(a).model_dump()


@router.delete("/activities/{activity_id}", status_code=204, dependencies=[_can_write])
async def delete_activity(activity_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    a = (await db.execute(select(SchoolActivity).where(SchoolActivity.id == activity_id, SchoolActivity.org_id == current_user.org_id))).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Activity not found.")
    await db.delete(a)
