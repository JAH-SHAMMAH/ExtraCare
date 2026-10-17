import uuid

import pytest
from sqlalchemy import select

from app.models.modules.platform import SchoolSection
from app.models.modules.school import TeacherSection
from app.models.user import User, UserStatus
from app.routers.modules import school as sch

pytestmark = pytest.mark.asyncio


async def _two_sections(db, org):
    out = []
    for n in ("Primary", "Secondary"):
        s = SchoolSection(id=str(uuid.uuid4()), name=n, org_id=org.id)
        db.add(s)
        out.append(s)
    await db.commit()
    return out


async def _teacher(db, org):
    u = User(id=str(uuid.uuid4()), email=f"t-{uuid.uuid4().hex[:6]}@x.com", full_name="Ada Teacher",
             status=UserStatus.ACTIVE, org_id=org.id, job_title="Teacher")
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def test_a_teacher_can_belong_to_primary_and_secondary(db, org):
    prim, sec = await _two_sections(db, org)
    t = await _teacher(db, org)
    await sch._add_teacher_section(db, org.id, t.id, prim.id)
    await sch._add_teacher_section(db, org.id, t.id, sec.id)
    await db.commit()
    m = await sch._teacher_sections_map(db, org.id, [t.id])
    assert [x["name"] for x in m[t.id][2]] == ["Primary", "Secondary"]
    d = sch._teacher_dict(t, m[t.id])
    assert d["section_name"] == "Primary, Secondary"
    assert set(d["section_ids"]) == {prim.id, sec.id}


async def test_adding_the_same_section_twice_is_harmless(db, org):
    prim, _ = await _two_sections(db, org)
    t = await _teacher(db, org)
    await sch._add_teacher_section(db, org.id, t.id, prim.id)
    await sch._add_teacher_section(db, org.id, t.id, prim.id)
    await db.commit()
    rows = (await db.execute(select(TeacherSection).where(TeacherSection.teacher_id == t.id))).scalars().all()
    assert len(rows) == 1


async def test_set_replaces_and_empty_clears(db, org):
    prim, sec = await _two_sections(db, org)
    t = await _teacher(db, org)
    await sch._set_teacher_sections(db, org.id, t.id, [prim.id, sec.id])
    await sch._set_teacher_sections(db, org.id, t.id, [sec.id])
    await db.commit()
    ids = (await db.execute(select(TeacherSection.section_id).where(TeacherSection.teacher_id == t.id))).scalars().all()
    assert ids == [sec.id]
    await sch._set_teacher_sections(db, org.id, t.id, [])
    await db.commit()
    assert (await db.execute(select(TeacherSection).where(TeacherSection.teacher_id == t.id))).scalars().all() == []


async def test_foreign_section_is_refused(db, org):
    from fastapi import HTTPException
    t = await _teacher(db, org)
    with pytest.raises(HTTPException):
        await sch._set_teacher_sections(db, org.id, t.id, [str(uuid.uuid4())])


async def test_me_lists_every_assigned_section_even_without_a_class_in_each(db, org):
    from app.routers.auth import get_me
    prim, sec = await _two_sections(db, org)
    t = await _teacher(db, org)
    await sch._set_teacher_sections(db, org.id, t.id, [prim.id, sec.id])
    await db.commit()
    me = await get_me(current_user=t, db=db)
    assert {s.name for s in me.teacher_sections} == {"Primary", "Secondary"}
