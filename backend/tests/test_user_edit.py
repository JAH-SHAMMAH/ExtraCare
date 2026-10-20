import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.modules.platform import SchoolSection
from app.models.modules.school import TeacherSection
from app.models.role import Role
from app.models.user import User, UserStatus
from app.routers.users import assign_roles, set_user_sections, update_user
from app.schemas.user import UserUpdate

pytestmark = pytest.mark.asyncio


class _Client:
    host = "127.0.0.1"


class _Req:
    headers = {}
    client = _Client()


async def _world(db, org):
    sec = SchoolSection(id=str(uuid.uuid4()), name="Primary", org_id=org.id)
    teacher = Role(id=str(uuid.uuid4()), name="Teacher", slug="teacher", permissions=["school:read"], org_id=org.id, is_system=False)
    acct = Role(id=str(uuid.uuid4()), name="Accountant", slug="accountant", permissions=["payments:read"], org_id=org.id, is_system=False)
    arole = Role(id=str(uuid.uuid4()), name="Admin", slug="admin", permissions=["*"], org_id=org.id, is_system=False)
    admin = User(id=str(uuid.uuid4()), email="d@x.com", full_name="Dir", status=UserStatus.ACTIVE, org_id=org.id)
    admin.roles = [arole]
    staff = User(id=str(uuid.uuid4()), email="s@x.com", full_name="Staff", status=UserStatus.ACTIVE, org_id=org.id)
    staff.roles = [acct]
    db.add_all([sec, teacher, acct, arole, admin, staff])
    await db.commit()
    return sec, teacher, acct, admin, staff


async def test_edit_profile_fields(db, org):
    sec, teacher, acct, admin, staff = await _world(db, org)
    r = await update_user(staff.id, UserUpdate(full_name="Staff Renamed", phone="0801", department="Finance", job_title="Bursar"),
                          _Req(), db=db, current_user=admin)
    assert (r.full_name, r.phone, r.department, r.job_title) == ("Staff Renamed", "0801", "Finance", "Bursar")
    with pytest.raises(HTTPException) as e:
        await update_user(staff.id, UserUpdate(full_name="  "), _Req(), db=db, current_user=admin)
    assert e.value.status_code == 422


async def test_lower_tier_cannot_edit_a_higher_account(db, org):
    sec, teacher, acct, admin, staff = await _world(db, org)
    with pytest.raises(HTTPException) as e:
        await update_user(admin.id, UserUpdate(full_name="Hijack"), _Req(), db=db, current_user=staff)
    assert e.value.status_code == 403


async def test_teaching_role_needs_a_section_then_works(db, org):
    sec, teacher, acct, admin, staff = await _world(db, org)
    with pytest.raises(HTTPException) as e:
        await assign_roles(staff.id, [teacher.id], _Req(), db=db, current_user=admin)
    assert e.value.status_code == 422 and "section" in e.value.detail.lower()
    await set_user_sections(staff.id, [sec.id], _Req(), db=db, current_user=admin)
    r = await assign_roles(staff.id, [teacher.id], _Req(), db=db, current_user=admin)
    await db.commit()
    assert [x["slug"] for x in r.roles] == ["teacher"] and r.job_title == "Teacher"
    rows = (await db.execute(select(TeacherSection).where(TeacherSection.teacher_id == staff.id))).scalars().all()
    assert [x.section_id for x in rows] == [sec.id]
    # cannot strip the last section from a teacher
    with pytest.raises(HTTPException):
        await set_user_sections(staff.id, [], _Req(), db=db, current_user=admin)
