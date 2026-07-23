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
from app.models.modules.school import (
    TimetableSettings, PeriodGroup, SubjectGroup, SchoolActivity,
    Period, PeriodSchedule, Subject,
)
from app.schemas.timetable import (
    TimetableSettingsResponse, TimetableSettingsUpdate,
    PeriodGroupCreate, PeriodGroupUpdate, PeriodGroupResponse,
    SubjectGroupCreate, SubjectGroupUpdate, SubjectGroupResponse,
    SchoolActivityCreate, SchoolActivityUpdate, SchoolActivityResponse,
    PeriodCreate, PeriodUpdate, PeriodResponse,
    PeriodGenerateRequest, PeriodGenerateResult,
    PeriodScheduleCreate, PeriodScheduleResponse,
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


# ── Periods (Manage Periods) ──────────────────────────────────────────────────

def _add_minutes(hhmm: str, minutes: int) -> str:
    h, m = (int(x) for x in hhmm.split(":")[:2])
    total = (h * 60 + m + minutes) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


async def _load_period_group(db, group_id, org_id) -> PeriodGroup:
    pg = (await db.execute(select(PeriodGroup).where(PeriodGroup.id == group_id, PeriodGroup.org_id == org_id))).scalar_one_or_none()
    if not pg:
        raise HTTPException(status_code=404, detail="Period group not found.")
    return pg


@router.get("/periods", dependencies=[_can_read])
async def list_periods(period_group_id: str, academic_year: str | None = None,
                       db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(Period).where(Period.period_group_id == period_group_id, Period.org_id == current_user.org_id)
    if academic_year:
        q = q.where(Period.academic_year == academic_year)
    rows = (await db.execute(q.order_by(Period.day_of_week, Period.sort_order, Period.start_time))).scalars().all()
    return {"items": [PeriodResponse.model_validate(r).model_dump() for r in rows]}


@router.post("/periods", status_code=201, dependencies=[_can_write])
async def create_period(payload: PeriodCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    await _load_period_group(db, payload.period_group_id, current_user.org_id)
    p = Period(**payload.model_dump(), org_id=current_user.org_id)
    db.add(p)
    await db.flush()
    return PeriodResponse.model_validate(p).model_dump()


@router.patch("/periods/{period_id}", dependencies=[_can_write])
async def update_period(period_id: str, payload: PeriodUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = (await db.execute(select(Period).where(Period.id == period_id, Period.org_id == current_user.org_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Period not found.")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    await db.flush()
    return PeriodResponse.model_validate(p).model_dump()


@router.delete("/periods/{period_id}", status_code=204, dependencies=[_can_write])
async def delete_period(period_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = (await db.execute(select(Period).where(Period.id == period_id, Period.org_id == current_user.org_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Period not found.")
    await db.delete(p)


@router.post("/periods/generate", response_model=PeriodGenerateResult, dependencies=[_can_write])
async def generate_periods(payload: PeriodGenerateRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Generate a day of periods back-to-back from a start time, inserting the
    given non-lesson periods (breaks) after the specified lesson counts."""
    org_id = current_user.org_id
    await _load_period_group(db, payload.period_group_id, org_id)
    if payload.replace_existing:
        existing = (await db.execute(select(Period).where(
            Period.period_group_id == payload.period_group_id, Period.org_id == org_id,
            Period.academic_year == payload.academic_year))).scalars().all()
        for p in existing:
            await db.delete(p)
        await db.flush()

    non_lesson = sorted(payload.non_lesson, key=lambda x: x.after_period)
    created = 0
    for day in payload.days:
        t = payload.start_time
        order = 0

        def _emit(period_type: str, minutes: int):
            nonlocal t, order, created
            end = _add_minutes(t, minutes)
            db.add(Period(period_group_id=payload.period_group_id, academic_year=payload.academic_year,
                          day_of_week=day, start_time=t, end_time=end, period_type=period_type,
                          sort_order=order, org_id=org_id))
            t = end
            order += 1
            created += 1

        for nl in [x for x in non_lesson if x.after_period == 0]:
            _emit(nl.name, nl.minutes)
        for i in range(1, payload.periods_per_day + 1):
            _emit("LESSON", payload.minutes_per_period)
            for nl in [x for x in non_lesson if x.after_period == i]:
                _emit(nl.name, nl.minutes)
    await db.flush()
    return PeriodGenerateResult(created=created)


# ── Schedules (Manage Schedules grid) ─────────────────────────────────────────

@router.get("/schedules", dependencies=[_can_read])
async def list_schedules(period_group_id: str, academic_year: str | None = None,
                         db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    org_id = current_user.org_id
    q = (select(PeriodSchedule, Subject.name, User.full_name)
         .join(Period, Period.id == PeriodSchedule.period_id)
         .outerjoin(Subject, Subject.id == PeriodSchedule.subject_id)
         .outerjoin(User, User.id == PeriodSchedule.teacher_id)
         .where(Period.period_group_id == period_group_id, PeriodSchedule.org_id == org_id))
    if academic_year:
        q = q.where(Period.academic_year == academic_year)
    rows = (await db.execute(q)).all()
    items = [PeriodScheduleResponse(
        id=s.id, period_id=s.period_id, class_id=s.class_id, subject_id=s.subject_id,
        subject_name=subj, teacher_id=s.teacher_id, teacher_name=tname, academic_year=s.academic_year,
    ).model_dump() for s, subj, tname in rows]
    return {"items": items}


@router.post("/schedules", status_code=201, dependencies=[_can_write])
async def upsert_schedule(payload: PeriodScheduleCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Place (or replace) a subject+teacher in a period for a class."""
    org_id = current_user.org_id
    p = (await db.execute(select(Period).where(Period.id == payload.period_id, Period.org_id == org_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Period not found.")
    subj = (await db.execute(select(Subject).where(Subject.id == payload.subject_id, Subject.org_id == org_id))).scalar_one_or_none()
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found.")
    existing = (await db.execute(select(PeriodSchedule).where(
        PeriodSchedule.period_id == payload.period_id, PeriodSchedule.class_id == payload.class_id,
        PeriodSchedule.org_id == org_id))).scalar_one_or_none()
    if existing:
        existing.subject_id = payload.subject_id
        existing.teacher_id = payload.teacher_id
        s = existing
    else:
        s = PeriodSchedule(period_id=payload.period_id, class_id=payload.class_id, subject_id=payload.subject_id,
                           teacher_id=payload.teacher_id, academic_year=payload.academic_year or p.academic_year, org_id=org_id)
        db.add(s)
    await db.flush()
    tname = None
    if s.teacher_id:
        tname = (await db.execute(select(User.full_name).where(User.id == s.teacher_id))).scalar_one_or_none()
    return PeriodScheduleResponse(id=s.id, period_id=s.period_id, class_id=s.class_id, subject_id=s.subject_id,
                                  subject_name=subj.name, teacher_id=s.teacher_id, teacher_name=tname,
                                  academic_year=s.academic_year).model_dump()


@router.delete("/schedules/{schedule_id}", status_code=204, dependencies=[_can_write])
async def delete_schedule(schedule_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = (await db.execute(select(PeriodSchedule).where(PeriodSchedule.id == schedule_id, PeriodSchedule.org_id == current_user.org_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found.")
    await db.delete(s)
