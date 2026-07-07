"""Tests for GET /school/students/{id} — the single-student read.

list/create/update/delete existed; GET-by-id was the only missing piece of the
students CRUD (the useStudent hook called a 404). Proves it returns the same
shape as the list rows, and 404s for an unknown id.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.routers.modules.school import get_student

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
