"""Tests for TimeTable Setup — settings singleton + period/subject group and
activity CRUD."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.routers.modules.timetable import (
    get_settings, update_settings,
    list_period_groups, create_period_group, update_period_group, delete_period_group,
    list_subject_groups, create_subject_group, update_subject_group, delete_subject_group,
    list_activities, create_activity, update_activity, delete_activity,
)
from app.schemas.timetable import (
    TimetableSettingsUpdate, PeriodGroupCreate, PeriodGroupUpdate,
    SubjectGroupCreate, SubjectGroupUpdate, SchoolActivityCreate, SchoolActivityUpdate,
)


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@example.com", full_name="Admin",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def test_settings_singleton_and_default_group_validation(db, org):
    admin = await _admin(db, org)
    s = await get_settings(db=db, current_user=admin)
    assert s.enable_even_odd_week is False and s.week_start_day == "Monday"

    pg = await create_period_group(PeriodGroupCreate(name="SECONDARY", year_group="All Year Group"), db=db, current_user=admin)
    upd = await update_settings(TimetableSettingsUpdate(enable_subject_grouping=True, default_period_group_id=pg["id"], week_start_day="Sunday"), db=db, current_user=admin)
    assert upd.enable_subject_grouping is True and upd.default_period_group_id == pg["id"] and upd.week_start_day == "Sunday"

    # Unknown default group is rejected.
    with pytest.raises(HTTPException) as exc:
        await update_settings(TimetableSettingsUpdate(default_period_group_id="nope"), db=db, current_user=admin)
    assert exc.value.status_code == 404


async def test_period_group_crud(db, org):
    admin = await _admin(db, org)
    pg = await create_period_group(PeriodGroupCreate(name="PRIMARY"), db=db, current_user=admin)
    assert pg["name"] == "PRIMARY"
    assert len((await list_period_groups(db=db, current_user=admin))["items"]) == 1
    upd = await update_period_group(pg["id"], PeriodGroupUpdate(year_group="YEAR 3"), db=db, current_user=admin)
    assert upd["year_group"] == "YEAR 3"
    await delete_period_group(pg["id"], db=db, current_user=admin)
    assert len((await list_period_groups(db=db, current_user=admin))["items"]) == 0


async def test_subject_group_crud_with_ids(db, org):
    admin = await _admin(db, org)
    sg = await create_subject_group(SubjectGroupCreate(name="Sciences", year_group="YEAR 11", subject_ids=["s1", "s2"]), db=db, current_user=admin)
    assert sg["subject_ids"] == ["s1", "s2"]
    upd = await update_subject_group(sg["id"], SubjectGroupUpdate(subject_ids=["s3"]), db=db, current_user=admin)
    assert upd["subject_ids"] == ["s3"]
    await delete_subject_group(sg["id"], db=db, current_user=admin)
    assert len((await list_subject_groups(db=db, current_user=admin))["items"]) == 0


async def test_activity_crud(db, org):
    admin = await _admin(db, org)
    a = await create_activity(SchoolActivityCreate(name="Story Time", color="#22c55e"), db=db, current_user=admin)
    assert a["name"] == "Story Time" and a["color"] == "#22c55e"
    upd = await update_activity(a["id"], SchoolActivityUpdate(color="#ef4444"), db=db, current_user=admin)
    assert upd["color"] == "#ef4444"
    await delete_activity(a["id"], db=db, current_user=admin)
    assert len((await list_activities(db=db, current_user=admin))["items"]) == 0
