"""Sidebar inputs on /auth/me: is_class_teacher (Reports View is class-teacher-only)
and the department fallback for a teacher with no class and no assigned section."""
import uuid

import pytest

from app.models.modules.platform import SchoolSection
from app.models.modules.school import SchoolClass
from app.models.user import User, UserStatus
from app.routers.auth import get_me

pytestmark = pytest.mark.asyncio


async def _sections(db, org):
    out = {}
    for n in ("Early Years", "Primary", "Secondary"):
        s = SchoolSection(id=str(uuid.uuid4()), name=n, org_id=org.id,
                          curriculum="EYFS" if n == "Early Years" else None)
        db.add(s)
        out[n] = s
    await db.commit()
    return out


async def _teacher(db, org, department=None):
    u = User(id=str(uuid.uuid4()), email=f"t-{uuid.uuid4().hex[:6]}@x.com", full_name="Ada Teacher",
             status=UserStatus.ACTIVE, org_id=org.id, job_title="Teacher", department=department)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def test_class_teacher_is_flagged_and_subject_teacher_is_not(db, org):
    secs = await _sections(db, org)
    ct = await _teacher(db, org)
    other = await _teacher(db, org)
    db.add(SchoolClass(id=str(uuid.uuid4()), name="Year 5", level="YEAR 5", teacher_id=ct.id,
                       section_id=secs["Primary"].id, org_id=org.id))
    await db.commit()
    assert (await get_me(current_user=ct, db=db)).is_class_teacher is True
    assert (await get_me(current_user=other, db=db)).is_class_teacher is False


async def test_department_alone_scopes_the_menu_to_that_level(db, org):
    await _sections(db, org)
    prim = await _teacher(db, org, department="Primary")
    sec = await _teacher(db, org, department="Secondary Department")
    eyfs = await _teacher(db, org, department="Early Years")
    assert [s.name for s in (await get_me(current_user=prim, db=db)).teacher_sections] == ["Primary"]
    assert [s.name for s in (await get_me(current_user=sec, db=db)).teacher_sections] == ["Secondary"]
    assert [s.name for s in (await get_me(current_user=eyfs, db=db)).teacher_sections] == ["Early Years"]


async def test_class_wins_over_department(db, org):
    secs = await _sections(db, org)
    t = await _teacher(db, org, department="Primary")
    db.add(SchoolClass(id=str(uuid.uuid4()), name="SS 1", level="SS 1", teacher_id=t.id,
                       section_id=secs["Secondary"].id, org_id=org.id))
    await db.commit()
    me = await get_me(current_user=t, db=db)
    assert [s.name for s in me.teacher_sections] == ["Secondary"]


async def test_no_department_no_section_stays_unfiltered(db, org):
    await _sections(db, org)
    t = await _teacher(db, org)
    me = await get_me(current_user=t, db=db)
    assert me.teacher_sections == []
