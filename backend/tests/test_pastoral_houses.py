"""Pastoral Batch B: house scoping/status + PATCH, House Masters, House Weeks,
and the Pastoral Students roster (mentor/house/leader, assign/sync/export).
Reuses SchoolHouse; students stay their own record."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.modules.platform import SchoolSection
from app.routers.modules.platform import create_house, update_house, list_houses
from app.routers.modules.pastoral import (
    add_house_master, list_house_masters, remove_house_master,
    create_house_week, update_house_week, list_house_weeks,
    list_pastoral_students, assign_pastoral_student, sync_pastoral_students, export_pastoral_students,
)
from app.schemas.platform import HouseCreate, HouseUpdate
from app.schemas.pastoral import HouseMasterCreate, HouseWeekCreate, HouseWeekUpdate, PastoralStudentAssign


pytestmark = pytest.mark.asyncio


async def _user(db, org, name="U") -> User:
    u = User(id=str(uuid.uuid4()), email=f"{uuid.uuid4().hex[:8]}@x.com", full_name=name,
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def _section(db, org, name="Secondary") -> SchoolSection:
    s = SchoolSection(id=str(uuid.uuid4()), name=name, org_id=org.id)
    db.add(s)
    await db.commit()
    return s


async def test_house_enrich_masters_weeks(db, org):
    admin = await _user(db, org, "Admin")
    sec = await _section(db, org, "Secondary")

    h = await create_house(payload=HouseCreate(name="Red House", color="#e11", section_id=sec.id), db=db, current_user=admin)
    assert h.section_id == sec.id and h.section_name == "Secondary" and h.is_active is True

    h2 = await update_house(h.id, HouseUpdate(is_active=False, color="#00f"), db=db, current_user=admin)
    assert h2.is_active is False and h2.color == "#00f"

    scoped = await list_houses(section=sec.id, db=db, current_user=admin)
    assert any(x.id == h.id for x in scoped)

    # House master (validated house + user).
    teacher = await _user(db, org, "Mr Master")
    m = await add_house_master(payload=HouseMasterCreate(house_id=h.id, user_id=teacher.id), db=db, current_user=admin)
    assert m.house_name == "Red House" and m.user_name == "Mr Master"
    assert len(await list_house_masters(house_id=h.id, db=db, current_user=admin)) == 1
    await remove_house_master(m.id, db=db, current_user=admin)
    assert len(await list_house_masters(house_id=h.id, db=db, current_user=admin)) == 0

    with pytest.raises(HTTPException) as exc:
        await add_house_master(payload=HouseMasterCreate(house_id=h.id, user_id="not-a-user"), db=db, current_user=admin)
    assert exc.value.status_code == 422

    # House week.
    w = await create_house_week(payload=HouseWeekCreate(name="Week 1"), db=db, current_user=admin)
    w2 = await update_house_week(w.id, HouseWeekUpdate(is_active=False), db=db, current_user=admin)
    assert w2.is_active is False
    assert len(await list_house_weeks(db=db, current_user=admin)) == 1


async def test_pastoral_students_roster(db, org, student):
    admin = await _user(db, org, "Admin")

    # LEFT-joined roster shows the student even with no assignment.
    roster = await list_pastoral_students(db=db, current_user=admin)
    row = next(r for r in roster if r.student_id == student.id)
    assert row.house_id is None and row.is_leader is False and row.student_name

    house = await create_house(payload=HouseCreate(name="Blue House"), db=db, current_user=admin)
    mentor = await _user(db, org, "Mentor Joy")
    await assign_pastoral_student(student.id, PastoralStudentAssign(house_id=house.id, mentor_id=mentor.id, is_leader=True), db=db, current_user=admin)

    row = next(r for r in await list_pastoral_students(db=db, current_user=admin) if r.student_id == student.id)
    assert row.house_id == house.id and row.house_name == "Blue House"
    assert row.mentor_id == mentor.id and row.mentor_name == "Mentor Joy" and row.is_leader is True

    # Filter by house.
    assert any(r.student_id == student.id for r in await list_pastoral_students(house=house.id, db=db, current_user=admin))

    # Sync is idempotent (this student already has a row → not recreated).
    before = await sync_pastoral_students(db=db, current_user=admin)
    assert before["synced"] >= 0

    # Export CSV.
    resp = await export_pastoral_students(section=None, db=db, current_user=admin)
    body = resp.body.decode()
    assert resp.media_type == "text/csv" and "Blue House" in body and "House" in body

    # Invalid house/mentor rejected.
    with pytest.raises(HTTPException) as exc:
        await assign_pastoral_student(student.id, PastoralStudentAssign(house_id="nope"), db=db, current_user=admin)
    assert exc.value.status_code == 422
