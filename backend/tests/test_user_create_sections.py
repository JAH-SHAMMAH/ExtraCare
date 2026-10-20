import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.modules.platform import SchoolSection
from app.models.modules.school import TeacherSection
from app.models.role import Role
from app.models.user import User, UserStatus
from app.routers.users import create_new_user
from app.schemas.user import UserCreate

pytestmark = pytest.mark.asyncio


class _Client:
    host = "127.0.0.1"


class _Req:
    headers = {}
    client = _Client()


async def _setup(db, org):
    sec = SchoolSection(id=str(uuid.uuid4()), name="Primary", org_id=org.id)
    teacher = Role(id=str(uuid.uuid4()), name="Teacher", slug="teacher", permissions=["school:read"], org_id=org.id, is_system=False)
    acct = Role(id=str(uuid.uuid4()), name="Accountant", slug="accountant", permissions=["payments:read"], org_id=org.id, is_system=False)
    admin_role = Role(id=str(uuid.uuid4()), name="Admin", slug="admin", permissions=["*"], org_id=org.id, is_system=False)
    admin = User(id=str(uuid.uuid4()), email="dir@x.com", full_name="Director", status=UserStatus.ACTIVE, org_id=org.id)
    admin.roles = [admin_role]
    db.add_all([sec, teacher, acct, admin_role, admin])
    await db.commit()
    return admin, sec, teacher, acct


def _data(email, role, sections=()):
    return UserCreate(email=email, full_name="New Person", password="Temp12345", role_ids=[role.id],
                      section_ids=list(sections))


async def test_teacher_without_a_section_is_refused(db, org):
    admin, sec, teacher, _ = await _setup(db, org)
    with pytest.raises(HTTPException) as e:
        await create_new_user(_data("a@x.com", teacher), _Req(), db=db, current_user=admin)
    assert e.value.status_code == 422 and "section" in e.value.detail.lower()
    assert (await db.execute(select(User).where(User.email == "a@x.com"))).first() is None


async def test_teacher_with_a_section_is_created_with_it_and_a_teacher_title(db, org):
    admin, sec, teacher, _ = await _setup(db, org)
    await create_new_user(_data("b@x.com", teacher, [sec.id]), _Req(), db=db, current_user=admin)
    await db.commit()
    u = (await db.execute(select(User).where(User.email == "b@x.com"))).scalar_one()
    assert u.job_title == "Teacher"
    rows = (await db.execute(select(TeacherSection).where(TeacherSection.teacher_id == u.id))).scalars().all()
    assert [r.section_id for r in rows] == [sec.id]


async def test_non_teaching_role_needs_no_section(db, org):
    admin, _, _, acct = await _setup(db, org)
    await create_new_user(_data("c@x.com", acct), _Req(), db=db, current_user=admin)
    await db.commit()
    assert (await db.execute(select(User).where(User.email == "c@x.com"))).scalar_one().job_title is None
