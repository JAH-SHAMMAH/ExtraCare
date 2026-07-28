"""Teachers module: section assignment (Select-School filter + Assign-To-School),
real Subject.teacher_id management (one teacher per subject), and CSV export.
Teachers are Users (job_title ~ teacher) — no separate model."""
from __future__ import annotations

import uuid

import pytest

from app.models.user import User, UserStatus
from app.models.modules.school import Subject
from app.models.modules.platform import SchoolSection
from app.routers.modules.school import (
    create_teacher, list_teachers, assign_teacher_section,
    get_teacher_subjects, set_teacher_subjects, export_teachers,
)
from app.schemas.teacher import TeacherCreate, TeacherSubjectsUpdate, AssignSectionRequest


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Admin",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def _section(db, org, name) -> SchoolSection:
    s = SchoolSection(id=str(uuid.uuid4()), name=name, org_id=org.id)
    db.add(s)
    await db.commit()
    return s


async def _subject(db, org, name) -> Subject:
    s = Subject(id=str(uuid.uuid4()), name=name, org_id=org.id)
    db.add(s)
    await db.commit()
    return s


async def _mk_teacher(db, admin, **kw):
    payload = dict(first_name="Ada", last_name="Obi", email=f"t-{uuid.uuid4().hex[:6]}@x.com")
    payload.update(kw)
    return await create_teacher(TeacherCreate(**payload), request=None, db=db, current_user=admin)


async def test_create_with_fields_and_section_filter(db, org):
    admin = await _admin(db, org)
    sec = await _section(db, org, "Secondary")
    other = await _section(db, org, "Nursery")

    t = await _mk_teacher(db, admin, first_name="Ada", last_name="Obi", other_names="Grace",
                          employee_id="FSE/001", section_id=sec.id)
    assert t["other_names"] == "Grace" and t["employee_id"] == "FSE/001"
    assert t["section_id"] == sec.id and t["section_name"] == "Secondary" and t["photo_url"] is None

    # Select-School filter: appears under its section, not another.
    in_sec = await list_teachers(page=1, page_size=25, search=None, section=sec.id, db=db, current_user=admin)
    assert any(x["id"] == t["id"] for x in in_sec["items"])
    in_other = await list_teachers(page=1, page_size=25, search=None, section=other.id, db=db, current_user=admin)
    assert all(x["id"] != t["id"] for x in in_other["items"])


async def test_assign_transfer_and_unassign_section(db, org):
    admin = await _admin(db, org)
    a = await _section(db, org, "Junior")
    b = await _section(db, org, "Secondary")
    t = await _mk_teacher(db, admin)
    assert t["section_id"] is None

    r1 = await assign_teacher_section(t["id"], AssignSectionRequest(section_id=a.id), None, db, admin)
    assert r1["section_id"] == a.id and r1["section_name"] == "Junior"
    r2 = await assign_teacher_section(t["id"], AssignSectionRequest(section_id=b.id), None, db, admin)  # transfer
    assert r2["section_id"] == b.id and r2["section_name"] == "Secondary"
    r3 = await assign_teacher_section(t["id"], AssignSectionRequest(section_id=None), None, db, admin)  # unassign
    assert r3["section_id"] is None


async def test_subject_assignment_one_teacher_per_subject(db, org):
    admin = await _admin(db, org)
    t1 = await _mk_teacher(db, admin)
    t2 = await _mk_teacher(db, admin)
    math = await _subject(db, org, "Mathematics")
    phys = await _subject(db, org, "Physics")

    await set_teacher_subjects(t1["id"], TeacherSubjectsUpdate(subject_ids=[math.id, phys.id]), None, db, admin)
    got = await get_teacher_subjects(t1["id"], db=db, current_user=admin)
    assert {x["id"] for x in got["items"]} == {math.id, phys.id}

    # Reassign Physics to t2 → moves off t1 (one teacher per subject).
    await set_teacher_subjects(t2["id"], TeacherSubjectsUpdate(subject_ids=[phys.id]), None, db, admin)
    assert {x["id"] for x in (await get_teacher_subjects(t1["id"], db=db, current_user=admin))["items"]} == {math.id}
    assert {x["id"] for x in (await get_teacher_subjects(t2["id"], db=db, current_user=admin))["items"]} == {phys.id}

    # Empty list unassigns everything for t1.
    await set_teacher_subjects(t1["id"], TeacherSubjectsUpdate(subject_ids=[]), None, db, admin)
    assert (await get_teacher_subjects(t1["id"], db=db, current_user=admin))["items"] == []


async def test_export_csv(db, org):
    admin = await _admin(db, org)
    sec = await _section(db, org, "Secondary")
    await _mk_teacher(db, admin, first_name="Ada", last_name="Obi", employee_id="FSE/007", section_id=sec.id)
    resp = await export_teachers(section=None, db=db, current_user=admin)
    body = resp.body.decode()
    assert resp.media_type == "text/csv"
    assert "Employee ID" in body and "FSE/007" in body and "Secondary" in body and "Ada" in body
