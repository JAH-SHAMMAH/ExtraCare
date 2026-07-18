"""CRUD tests for Students and Teachers.

These cover the regressions reported from the dashboard:
  • "failed to create student" — caused by `data: dict` accepting `date_of_birth=""`
    and blowing up at SQLAlchemy flush.
  • "not found" when adding a teacher — there was no /school/teachers endpoint.

Each test calls the router handler as a coroutine (per conftest convention),
bypassing the FastAPI DI / permission layer so the logic under test is
exercised directly.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.modules.school import Student
from app.models.organization import Organization, IndustryType
from app.routers.modules.school import (
    create_student, update_student, delete_student,
    create_teacher, update_teacher, list_teachers, delete_teacher,
    TEACHER_JOB_TITLE,
)
from app.schemas.student import StudentCreate, StudentUpdate
from app.schemas.teacher import TeacherCreate, TeacherUpdate


pytestmark = pytest.mark.asyncio


# ── Students ──────────────────────────────────────────────────────────────────

async def test_create_student_happy_path(db, org, teacher, school_class):
    data = StudentCreate(
        student_id="S-100",
        first_name="Ada",
        last_name="Okafor",
        email="ada@example.com",
        class_id=school_class.id,
        date_of_birth=date(2010, 3, 4),
    )
    result = await create_student(data=data, db=db, current_user=teacher)
    assert result["student_id"] == "S-100"
    assert result["first_name"] == "Ada"
    assert result["class_id"] == school_class.id


async def test_create_student_coerces_empty_strings(db, org, teacher):
    """Regression: browser forms submit '' for unfilled optional fields.

    Before the fix, `date_of_birth=''` made it to `Column(Date)` and raised
    StatementError at flush — surfaced as a 500/"failed to create student".
    """
    data = StudentCreate.model_validate({
        "student_id": "S-101",
        "first_name": "Bola",
        "last_name": "Adebayo",
        "email": "",
        "phone": "",
        "date_of_birth": "",
        "class_id": "",
        "guardian_name": "",
    })
    assert data.email is None
    assert data.date_of_birth is None
    assert data.class_id is None

    result = await create_student(data=data, db=db, current_user=teacher)
    assert result["id"]
    assert result["email"] is None


async def test_create_student_rejects_blank_required(db):
    with pytest.raises(Exception):  # pydantic ValidationError
        StudentCreate.model_validate({
            "student_id": "",
            "first_name": "X",
            "last_name": "Y",
        })


async def test_create_student_invalid_class_id(db, org, teacher):
    data = StudentCreate(
        student_id="S-102",
        first_name="Chidi",
        last_name="Eze",
        class_id="not-a-real-class",
    )
    with pytest.raises(HTTPException) as exc:
        await create_student(data=data, db=db, current_user=teacher)
    assert exc.value.status_code == 404
    assert "not-a-real-class" in exc.value.detail


async def test_create_student_cross_tenant_class_id_rejected(db, org, teacher, school_class):
    """Another tenant's class_id must not resolve, even if it physically exists."""
    other = Organization(
        id=str(uuid.uuid4()),
        name="Other School",
        slug=f"other-{uuid.uuid4().hex[:8]}",
        industry=IndustryType.SCHOOL,
        modules_enabled=["school"],
    )
    db.add(other)
    other_teacher = User(
        id=str(uuid.uuid4()),
        email="tx@example.com",
        full_name="Tx",
        status=UserStatus.ACTIVE,
        org_id=other.id,
    )
    db.add(other_teacher)
    await db.commit()

    data = StudentCreate(
        student_id="S-103",
        first_name="Tari",
        last_name="Onu",
        class_id=school_class.id,  # belongs to `org`, not `other`
    )
    with pytest.raises(HTTPException) as exc:
        await create_student(data=data, db=db, current_user=other_teacher)
    assert exc.value.status_code == 404


async def test_update_student_not_found_returns_404(db, teacher):
    with pytest.raises(HTTPException) as exc:
        await update_student(
            id="nope", data=StudentUpdate(first_name="X"),
            db=db, current_user=teacher,
        )
    assert exc.value.status_code == 404


async def test_delete_student_soft_deletes(db, teacher, student):
    await delete_student(id=student.id, db=db, current_user=teacher)
    await db.refresh(student)
    assert student.is_deleted is True


# ── Teachers ──────────────────────────────────────────────────────────────────

async def test_create_teacher_happy_path(db, org, teacher):
    data = TeacherCreate(
        first_name="Grace",
        last_name="Okoro",
        email="grace@example.com",
        phone="+2348000000",
        department="Science",
        qualification="MSc Physics",
        subjects=["Physics", "Chemistry"],
    )
    result = await create_teacher(data=data, db=db, current_user=teacher)
    assert result["first_name"] == "Grace"
    assert result["last_name"] == "Okoro"
    assert result["email"] == "grace@example.com"
    assert result["subjects"] == ["Physics", "Chemistry"]
    assert result["qualification"] == "MSc Physics"
    assert result["is_active"] is True

    # Backed by a real User row tagged as Teacher.
    row = (await db.execute(
        select(User).where(User.email == "grace@example.com", User.org_id == org.id)
    )).scalar_one()
    assert row.job_title == TEACHER_JOB_TITLE


async def test_create_teacher_duplicate_email_per_org(db, org, teacher):
    data = TeacherCreate(
        first_name="Joy",
        last_name="Mba",
        email="joy@example.com",
    )
    await create_teacher(data=data, db=db, current_user=teacher)

    with pytest.raises(HTTPException) as exc:
        await create_teacher(data=data, db=db, current_user=teacher)
    assert exc.value.status_code == 409
    assert "joy@example.com" in exc.value.detail


async def test_create_teacher_blank_name_rejected(db):
    with pytest.raises(Exception):
        TeacherCreate.model_validate({
            "first_name": "",
            "last_name": "",
            "email": "x@example.com",
        })


async def test_create_teacher_blank_email_rejected(db):
    with pytest.raises(Exception):
        TeacherCreate.model_validate({
            "first_name": "A",
            "last_name": "B",
            "email": "",
        })


async def test_list_teachers_excludes_other_users_and_other_orgs(db, org, teacher):
    # Create one teacher in this org
    await create_teacher(
        data=TeacherCreate(first_name="T1", last_name="X", email="t1@example.com"),
        db=db, current_user=teacher,
    )
    # And a non-teacher user in the same org (should not appear)
    nonstaff = User(
        id=str(uuid.uuid4()),
        email="staff@example.com",
        full_name="Staff",
        status=UserStatus.ACTIVE,
        org_id=org.id,
        job_title="Accountant",
    )
    db.add(nonstaff)
    await db.commit()

    page = await list_teachers(
        page=1, page_size=25, search=None,
        db=db, current_user=teacher,
    )
    emails = [t["email"] for t in page["items"]]
    assert "t1@example.com" in emails
    assert "staff@example.com" not in emails


async def test_list_teachers_counts_subject_titled_teachers(db, org, teacher):
    """Regression: real teachers carry subject-specific titles ("Physics Teacher"),
    not the bare "Teacher". They must count as teachers (job_title contains
    'teacher'); non-teaching staff must not. Keeps the Teachers list + dashboard
    counters in agreement."""
    db.add_all([
        User(id=str(uuid.uuid4()), email="phys@example.com", full_name="Phys T",
             status=UserStatus.ACTIVE, org_id=org.id, job_title="Physics Teacher"),
        User(id=str(uuid.uuid4()), email="acct@example.com", full_name="Acct",
             status=UserStatus.ACTIVE, org_id=org.id, job_title="Accountant"),
    ])
    await db.commit()
    emails = [t["email"] for t in (await list_teachers(page=1, page_size=50, search=None, db=db, current_user=teacher))["items"]]
    assert "phys@example.com" in emails
    assert "acct@example.com" not in emails


async def test_update_teacher_changes_name_and_subjects(db, org, teacher):
    created = await create_teacher(
        data=TeacherCreate(first_name="Kay", last_name="L", email="kl@example.com"),
        db=db, current_user=teacher,
    )
    updated = await update_teacher(
        id=created["id"],
        data=TeacherUpdate(first_name="Kayode", subjects=["Maths"], qualification="BEd"),
        db=db, current_user=teacher,
    )
    assert updated["first_name"] == "Kayode"
    assert updated["subjects"] == ["Maths"]
    assert updated["qualification"] == "BEd"


async def test_delete_teacher_soft_deletes(db, org, teacher):
    created = await create_teacher(
        data=TeacherCreate(first_name="Del", last_name="Me", email="del@example.com"),
        db=db, current_user=teacher,
    )
    await delete_teacher(id=created["id"], db=db, current_user=teacher)

    page = await list_teachers(
        page=1, page_size=25, search=None,
        db=db, current_user=teacher,
    )
    assert "del@example.com" not in [t["email"] for t in page["items"]]
