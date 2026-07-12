"""Tests for GET /school/students/{id} — the single-student read.

list/create/update/delete existed; GET-by-id was the only missing piece of the
students CRUD (the useStudent hook called a 404). Proves it returns the same
shape as the list rows, and 404s for an unknown id.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.modules.school import Student
from app.routers.modules.school import get_student, list_students

pytestmark = pytest.mark.asyncio


async def test_get_student_by_id(db, org, teacher, student):
    res = await get_student(student.id, db=db, current_user=teacher)
    assert res["id"] == student.id
    assert res["student_id"] == student.student_id
    assert res["first_name"] == student.first_name


async def test_get_student_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await get_student(str(uuid.uuid4()), db=db, current_user=teacher)
    assert exc.value.status_code == 404


async def test_list_students_status_filter(db, org, teacher, school_class, student):
    """status=active|inactive powers the Active / Inactive roster tabs; an
    unknown/absent value returns the whole roster."""
    # The `student` fixture is active by default; add an off-roster student.
    inactive = Student(
        id=str(uuid.uuid4()), student_id="S-INACT", first_name="Bob",
        last_name="Gone", class_id=school_class.id, org_id=org.id, is_active=False,
    )
    db.add(inactive)
    await db.commit()

    active = await list_students(page=1, page_size=25, status="active", db=db, current_user=teacher)
    active_ids = {s["id"] for s in active["items"]}
    assert student.id in active_ids and inactive.id not in active_ids
    assert all(s["is_active"] for s in active["items"])

    off = await list_students(page=1, page_size=25, status="inactive", db=db, current_user=teacher)
    off_ids = {s["id"] for s in off["items"]}
    assert inactive.id in off_ids and student.id not in off_ids

    every = await list_students(page=1, page_size=25, db=db, current_user=teacher)  # no filter → whole roster
    every_ids = {s["id"] for s in every["items"]}
    assert student.id in every_ids and inactive.id in every_ids
