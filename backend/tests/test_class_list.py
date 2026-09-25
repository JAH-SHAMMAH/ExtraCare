"""The roster for one (class, subject) a teacher actually teaches.

Teachers had no page showing who is in their class for a given subject. The rows
were reachable — `GET /school/students?class_id=` serves them and teachers hold
school:students:read — but that endpoint is ORG-WIDE, so a page built on it would
have been scoped more weakly than Make Report and Grade Analysis, which both
enforce the Timetable pair server-side. This endpoint enforces it too.

Deliberately NOT modelled: Educare's version splits a class+subject across
several teachers ("assigned to this teacher" / "assigned elsewhere", locked
pupils). Timetable is class-level with no student_id, and Subject.teacher_id is
one teacher org-wide, so nothing here can express that. Faking the counts would
be worse than omitting them.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.modules.school import SchoolClass, Student, Subject, Timetable
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.academics import class_list


async def _user(db, org, preset="teacher") -> User:
    role = Role(id=str(uuid.uuid4()), name=preset, slug=f"{preset}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[preset]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"{uuid.uuid4().hex[:6]}@example.com",
             full_name=preset.title(), status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _school(db, org, n_students=3):
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="JSS1", org_id=org.id)
    other = SchoolClass(id=str(uuid.uuid4()), name="JSS1 B", level="JSS1", org_id=org.id)
    subj = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    db.add_all([cls, other, subj])
    await db.commit()
    for i in range(n_students):
        db.add(Student(id=str(uuid.uuid4()), student_id=f"S-{i}", first_name=f"Pupil{i}",
                       last_name="Test", class_id=cls.id, org_id=org.id))
    # A pupil in the OTHER class, to prove the roster is not the whole school.
    db.add(Student(id=str(uuid.uuid4()), student_id="S-X", first_name="Elsewhere",
                   last_name="Test", class_id=other.id, org_id=org.id))
    await db.commit()
    return cls, other, subj


async def _teaches(db, org, teacher, cls, subj):
    db.add(Timetable(id=str(uuid.uuid4()), class_id=cls.id, subject_id=subj.id,
                     teacher_id=teacher.id, day_of_week=0, start_time="08:00",
                     end_time="09:00", org_id=org.id))
    await db.commit()


@pytest.mark.asyncio
async def test_a_teacher_sees_the_roster_for_a_pair_they_teach(db, org):
    teacher = await _user(db, org)
    cls, _, subj = await _school(db, org)
    await _teaches(db, org, teacher, cls, subj)

    out = await class_list(class_id=cls.id, subject_id=subj.id, db=db, current_user=teacher)

    assert out["total"] == 3
    assert out["class_name"] == "JSS1 A" and out["subject_name"] == "Mathematics"
    assert {s["name"] for s in out["students"]} == {"Pupil0 Test", "Pupil1 Test", "Pupil2 Test"}


@pytest.mark.asyncio
async def test_the_roster_is_the_class_not_the_school(db, org):
    """A pupil in another class must not appear, or "class list" means nothing."""
    teacher = await _user(db, org)
    cls, _, subj = await _school(db, org)
    await _teaches(db, org, teacher, cls, subj)

    out = await class_list(class_id=cls.id, subject_id=subj.id, db=db, current_user=teacher)

    assert "Elsewhere Test" not in {s["name"] for s in out["students"]}


@pytest.mark.asyncio
async def test_a_pair_the_teacher_does_not_teach_is_refused(db, org):
    """The point of enforcing server-side: /school/students would have served
    these rows to any teacher for any class."""
    teacher = await _user(db, org)
    cls, other, subj = await _school(db, org)
    await _teaches(db, org, teacher, cls, subj)   # teaches JSS1 A, not JSS1 B

    with pytest.raises(HTTPException) as e:
        await class_list(class_id=other.id, subject_id=subj.id, db=db, current_user=teacher)
    assert e.value.status_code == 403
    assert "do not teach" in e.value.detail


@pytest.mark.asyncio
async def test_a_teacher_with_no_timetable_rows_is_refused(db, org):
    teacher = await _user(db, org)
    cls, _, subj = await _school(db, org)

    with pytest.raises(HTTPException) as e:
        await class_list(class_id=cls.id, subject_id=subj.id, db=db, current_user=teacher)
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_an_admin_is_not_required_to_be_on_the_timetable(db, org):
    """Admins hold school_admin and appear on nobody's timetable. Requiring a pair
    would make this permanently empty for them — the failure mode Grade Analysis
    already has."""
    admin = await _user(db, org, "org_admin")
    cls, _, subj = await _school(db, org)

    out = await class_list(class_id=cls.id, subject_id=subj.id, db=db, current_user=admin)
    assert out["total"] == 3


@pytest.mark.asyncio
async def test_a_deleted_pupil_is_not_listed(db, org):
    teacher = await _user(db, org)
    cls, _, subj = await _school(db, org)
    await _teaches(db, org, teacher, cls, subj)
    db.add(Student(id=str(uuid.uuid4()), student_id="S-D", first_name="Gone", last_name="Test",
                   class_id=cls.id, is_deleted=True, org_id=org.id))
    await db.commit()

    out = await class_list(class_id=cls.id, subject_id=subj.id, db=db, current_user=teacher)
    assert out["total"] == 3 and "Gone Test" not in {s["name"] for s in out["students"]}


@pytest.mark.asyncio
async def test_a_class_from_another_organisation_is_not_found(db, org):
    teacher = await _user(db, org)
    cls, _, subj = await _school(db, org)
    await _teaches(db, org, teacher, cls, subj)
    cls.org_id = str(uuid.uuid4())
    await db.commit()

    with pytest.raises(HTTPException) as e:
        await class_list(class_id=cls.id, subject_id=subj.id, db=db, current_user=teacher)
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_an_unknown_subject_is_not_found(db, org):
    teacher = await _user(db, org)
    cls, _, subj = await _school(db, org)
    await _teaches(db, org, teacher, cls, subj)

    with pytest.raises(HTTPException) as e:
        await class_list(class_id=cls.id, subject_id=str(uuid.uuid4()), db=db, current_user=teacher)
    assert e.value.status_code == 404
