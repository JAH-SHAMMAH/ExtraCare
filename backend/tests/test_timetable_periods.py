"""Tests for Manage Periods (single CRUD + generate) and the Manage Schedules
grid (place/replace/delete a subject in a period for a class)."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.modules.school import Subject
from app.routers.modules.timetable import (
    create_period_group, create_period, list_periods, update_period, delete_period, generate_periods,
    upsert_schedule, list_schedules, delete_schedule,
)
from app.schemas.timetable import (
    PeriodGroupCreate, PeriodCreate, PeriodUpdate, PeriodGenerateRequest, NonLessonPeriod,
    PeriodScheduleCreate,
)


pytestmark = pytest.mark.asyncio
YEAR = "2025/2026"


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@example.com", full_name="Admin",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def _subject(db, org, name="Maths") -> Subject:
    s = Subject(id=str(uuid.uuid4()), name=name, org_id=org.id)
    db.add(s)
    await db.commit()
    return s


# ── Periods ───────────────────────────────────────────────────────────────────

async def test_period_single_crud(db, org):
    admin = await _admin(db, org)
    pg = await create_period_group(PeriodGroupCreate(name="SECONDARY"), db=db, current_user=admin)
    p = await create_period(PeriodCreate(period_group_id=pg["id"], academic_year=YEAR, day_of_week=0, start_time="08:00", end_time="08:40", period_type="LESSON"), db=db, current_user=admin)
    assert p["period_type"] == "LESSON"
    assert len((await list_periods(period_group_id=pg["id"], academic_year=YEAR, db=db, current_user=admin))["items"]) == 1
    upd = await update_period(p["id"], PeriodUpdate(period_type="ASSEMBLY"), db=db, current_user=admin)
    assert upd["period_type"] == "ASSEMBLY"
    await delete_period(p["id"], db=db, current_user=admin)
    assert len((await list_periods(period_group_id=pg["id"], academic_year=YEAR, db=db, current_user=admin))["items"]) == 0


async def test_generate_periods_with_break(db, org):
    admin = await _admin(db, org)
    pg = await create_period_group(PeriodGroupCreate(name="PRIMARY"), db=db, current_user=admin)
    res = await generate_periods(PeriodGenerateRequest(
        period_group_id=pg["id"], academic_year=YEAR, days=[0, 1], periods_per_day=3, start_time="08:00",
        minutes_per_period=40, non_lesson=[NonLessonPeriod(name="SHORT BREAK", after_period=2, minutes=15)],
    ), db=db, current_user=admin)
    # (3 lessons + 1 break) x 2 days = 8
    assert res.created == 8
    periods = (await list_periods(period_group_id=pg["id"], academic_year=YEAR, db=db, current_user=admin))["items"]
    monday = [p for p in periods if p["day_of_week"] == 0]
    # lesson 08:00-08:40, lesson 08:40-09:20, BREAK 09:20-09:35, lesson 09:35-10:15
    assert [p["start_time"] for p in monday] == ["08:00", "08:40", "09:20", "09:35"]
    assert monday[2]["period_type"] == "SHORT BREAK" and monday[2]["end_time"] == "09:35"
    assert monday[3]["start_time"] == "09:35" and monday[3]["period_type"] == "LESSON"


async def test_generate_replaces_existing(db, org):
    admin = await _admin(db, org)
    pg = await create_period_group(PeriodGroupCreate(name="G"), db=db, current_user=admin)
    await generate_periods(PeriodGenerateRequest(period_group_id=pg["id"], academic_year=YEAR, days=[0], periods_per_day=2, start_time="08:00", minutes_per_period=30), db=db, current_user=admin)
    await generate_periods(PeriodGenerateRequest(period_group_id=pg["id"], academic_year=YEAR, days=[0], periods_per_day=4, start_time="08:00", minutes_per_period=30), db=db, current_user=admin)
    assert len((await list_periods(period_group_id=pg["id"], academic_year=YEAR, db=db, current_user=admin))["items"]) == 4


# ── Schedules ─────────────────────────────────────────────────────────────────

async def test_schedule_upsert_and_delete(db, org, student, school_class):
    admin = await _admin(db, org)
    subj = await _subject(db, org, "English")
    subj2 = await _subject(db, org, "Maths")
    pg = await create_period_group(PeriodGroupCreate(name="SEC"), db=db, current_user=admin)
    period = await create_period(PeriodCreate(period_group_id=pg["id"], academic_year=YEAR, day_of_week=0, start_time="08:00", end_time="08:40"), db=db, current_user=admin)

    s = await upsert_schedule(PeriodScheduleCreate(period_id=period["id"], class_id=school_class.id, subject_id=subj.id, academic_year=YEAR), db=db, current_user=admin)
    assert s["subject_name"] == "English"
    # Upsert same period+class replaces the subject (no duplicate).
    s2 = await upsert_schedule(PeriodScheduleCreate(period_id=period["id"], class_id=school_class.id, subject_id=subj2.id), db=db, current_user=admin)
    assert s2["id"] == s["id"] and s2["subject_name"] == "Maths"

    listing = await list_schedules(period_group_id=pg["id"], academic_year=YEAR, db=db, current_user=admin)
    assert len(listing["items"]) == 1
    await delete_schedule(s["id"], db=db, current_user=admin)
    assert len((await list_schedules(period_group_id=pg["id"], academic_year=YEAR, db=db, current_user=admin))["items"]) == 0


async def test_schedule_unknown_subject_404(db, org, school_class):
    admin = await _admin(db, org)
    pg = await create_period_group(PeriodGroupCreate(name="X"), db=db, current_user=admin)
    period = await create_period(PeriodCreate(period_group_id=pg["id"], day_of_week=0, start_time="08:00", end_time="08:40"), db=db, current_user=admin)
    with pytest.raises(HTTPException) as exc:
        await upsert_schedule(PeriodScheduleCreate(period_id=period["id"], class_id=school_class.id, subject_id="nope"), db=db, current_user=admin)
    assert exc.value.status_code == 404
