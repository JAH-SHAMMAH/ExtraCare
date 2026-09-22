"""Assigning, changing and clearing a class's teacher.

`SchoolClass.teacher_id` decides who can open the class in Reports View and who
can submit its report for approval, but the classes admin form never exposed it
— it edited name, grade level, section, capacity and academic year only. Fairview's
assignments came from seeding, so there was no way for an admin to set or change
one. The API always accepted `class_teacher_id`; only the form was missing.

The clearing case is the one with teeth. `teacher_id` is a foreign key to
users.id, and unlike `section_id` the router did not normalise "" to None — so
"unassign" would have sent an empty string into a FK column and failed, the
first time an admin used the new dropdown for exactly what it is for.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.modules.school import SchoolClass
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.school import update_class
from app.schemas.school_class import ClassUpdate


async def _user(db, org, preset="org_admin", name="Admin") -> User:
    role = Role(id=str(uuid.uuid4()), name=preset, slug=f"{preset}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[preset]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"{uuid.uuid4().hex[:6]}@example.com",
             full_name=name, status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _class(db, org, teacher=None) -> SchoolClass:
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="JSS1",
                      teacher_id=teacher.id if teacher else None, org_id=org.id)
    db.add(cls)
    await db.commit()
    return cls


async def _patch(db, admin, cls, **fields):
    return await update_class(cls.id, ClassUpdate(**fields), request=None,
                              db=db, current_user=admin)


async def _reload(db, cls) -> SchoolClass:
    db.expunge_all()   # read the row back, not the identity map's copy
    return (await db.execute(select(SchoolClass).where(SchoolClass.id == cls.id))).scalars().one()


@pytest.mark.asyncio
async def test_a_class_teacher_can_be_assigned(db, org):
    admin = await _user(db, org)
    teacher = await _user(db, org, "teacher", "Ngozi Chukwu")
    cls = await _class(db, org)

    await _patch(db, admin, cls, class_teacher_id=teacher.id)

    assert (await _reload(db, cls)).teacher_id == teacher.id


@pytest.mark.asyncio
async def test_a_class_teacher_can_be_changed(db, org):
    admin = await _user(db, org)
    first = await _user(db, org, "teacher", "First")
    second = await _user(db, org, "teacher", "Second")
    cls = await _class(db, org, first)

    await _patch(db, admin, cls, class_teacher_id=second.id)

    assert (await _reload(db, cls)).teacher_id == second.id


@pytest.mark.asyncio
async def test_clearing_the_class_teacher_unassigns_rather_than_failing(db, org):
    """The defect the dropdown would have hit immediately. "" must become NULL —
    teacher_id is a FK, so an empty string is not a value it can hold."""
    admin = await _user(db, org)
    teacher = await _user(db, org, "teacher", "Ngozi Chukwu")
    cls = await _class(db, org, teacher)

    await _patch(db, admin, cls, class_teacher_id="")

    assert (await _reload(db, cls)).teacher_id is None


@pytest.mark.asyncio
async def test_an_explicit_null_also_clears(db, org):
    """What the form actually sends for "None"."""
    admin = await _user(db, org)
    teacher = await _user(db, org, "teacher", "Ngozi Chukwu")
    cls = await _class(db, org, teacher)

    await _patch(db, admin, cls, class_teacher_id=None)

    assert (await _reload(db, cls)).teacher_id is None


@pytest.mark.asyncio
async def test_an_unrelated_edit_leaves_the_teacher_alone(db, org):
    """exclude_unset matters: editing capacity must not silently unassign the
    teacher just because the field was absent from the payload."""
    admin = await _user(db, org)
    teacher = await _user(db, org, "teacher", "Ngozi Chukwu")
    cls = await _class(db, org, teacher)

    await _patch(db, admin, cls, capacity=35)

    after = await _reload(db, cls)
    assert after.teacher_id == teacher.id and after.max_capacity == 35


@pytest.mark.asyncio
async def test_an_unknown_teacher_is_refused(db, org):
    admin = await _user(db, org)
    cls = await _class(db, org)

    with pytest.raises(HTTPException) as e:
        await _patch(db, admin, cls, class_teacher_id=str(uuid.uuid4()))
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_a_teacher_from_another_organisation_is_refused(db, org):
    """Tenant isolation: the id exists, just not here. Without the org check a
    class could be handed to a stranger's account."""
    admin = await _user(db, org)
    outsider = await _user(db, org, "teacher", "Outsider")
    outsider.org_id = str(uuid.uuid4())
    await db.commit()
    cls = await _class(db, org)

    with pytest.raises(HTTPException) as e:
        await _patch(db, admin, cls, class_teacher_id=outsider.id)
    assert e.value.status_code == 404
    assert (await _reload(db, cls)).teacher_id is None


@pytest.mark.asyncio
async def test_the_assigned_teacher_comes_back_on_the_class(db, org):
    """The form repopulates from what the API returns, so the round trip has to
    carry both the id and a readable name."""
    admin = await _user(db, org)
    teacher = await _user(db, org, "teacher", "Ngozi Chukwu")
    cls = await _class(db, org)

    out = await _patch(db, admin, cls, class_teacher_id=teacher.id)

    assert out["class_teacher_id"] == teacher.id
    assert "Ngozi" in (out.get("class_teacher_name") or "")
