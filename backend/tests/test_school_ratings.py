"""Tests for the Teacher Ratings surface — /school/ratings.

The ratings page (list/submit/average) had no backend at all. Proves:
  • submit validates rating 1–5 and the teacher/student belong to the org
  • student id accepts either the uuid or the human student_id code
  • one rating per (student, teacher) — resubmitting updates in place, no dupes
  • list returns the frontend TeacherRating shape with student_name resolved
  • the teacher-average endpoint returns average + count + 1–5 distribution
  • RBAC: read = school:read, submit = school:write
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import TeacherRating, Student
from app.routers.modules.school import (
    list_ratings, submit_rating, teacher_rating_average,
)
from app.schemas.rating import RatingCreate


pytestmark = pytest.mark.asyncio


async def _preset_user(db, org, slug) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


# ── Submit: validation + upsert ──────────────────────────────────────────────────

async def test_submit_creates_and_resolves_student(db, org, teacher, student):
    resp = await submit_rating(
        RatingCreate(teacher_id=teacher.id, student_id=student.id, rating=4, comment="Great teacher"),
        request=None, db=db, current_user=teacher,
    )
    assert resp["rating"] == 4 and resp["comment"] == "Great teacher"
    assert resp["teacher_id"] == teacher.id and resp["student_id"] == student.id
    assert resp["student_name"]  # resolved, not None
    row = (await db.execute(select(TeacherRating).where(TeacherRating.id == resp["id"]))).scalar_one()
    assert row.rating == 4


async def test_submit_accepts_human_student_code(db, org, teacher, student):
    # student fixture has a human student_id code distinct from the uuid
    resp = await submit_rating(
        RatingCreate(teacher_id=teacher.id, student_id=student.student_id, rating=5),
        request=None, db=db, current_user=teacher,
    )
    assert resp["student_id"] == student.id and resp["rating"] == 5


async def test_rating_out_of_range_rejected():
    with pytest.raises(ValidationError):
        RatingCreate(teacher_id="t", student_id="s", rating=6)
    with pytest.raises(ValidationError):
        RatingCreate(teacher_id="t", student_id="s", rating=0)


async def test_upsert_one_per_student_teacher(db, org, teacher, student):
    await submit_rating(RatingCreate(teacher_id=teacher.id, student_id=student.id, rating=3),
                        request=None, db=db, current_user=teacher)
    await submit_rating(RatingCreate(teacher_id=teacher.id, student_id=student.id, rating=5, comment="Improved"),
                        request=None, db=db, current_user=teacher)
    rows = (await db.execute(select(TeacherRating).where(
        TeacherRating.teacher_id == teacher.id, TeacherRating.student_id == student.id))).scalars().all()
    assert len(rows) == 1 and rows[0].rating == 5 and rows[0].comment == "Improved"


async def test_submit_unknown_teacher_or_student(db, org, teacher, student):
    with pytest.raises(HTTPException) as e1:
        await submit_rating(RatingCreate(teacher_id=str(uuid.uuid4()), student_id=student.id, rating=4),
                            request=None, db=db, current_user=teacher)
    assert e1.value.status_code == 404
    with pytest.raises(HTTPException) as e2:
        await submit_rating(RatingCreate(teacher_id=teacher.id, student_id="nope", rating=4),
                            request=None, db=db, current_user=teacher)
    assert e2.value.status_code == 404


# ── List + average ────────────────────────────────────────────────────────────────

async def test_list_and_average(db, org, teacher, student):
    # second student to get a distribution
    other = Student(id=str(uuid.uuid4()), student_id=f"S{uuid.uuid4().hex[:5]}", first_name="Ada",
                    last_name="Obi", class_id=student.class_id, org_id=org.id, is_active=True)
    db.add(other)
    await db.commit()

    await submit_rating(RatingCreate(teacher_id=teacher.id, student_id=student.id, rating=5),
                        request=None, db=db, current_user=teacher)
    await submit_rating(RatingCreate(teacher_id=teacher.id, student_id=other.id, rating=3),
                        request=None, db=db, current_user=teacher)

    listed = await list_ratings(page=1, page_size=50, teacher_id=teacher.id, db=db, current_user=teacher)
    assert listed["total"] == 2
    assert all("student_name" in r and "rating" in r for r in listed["items"])

    avg = await teacher_rating_average(teacher.id, db=db, current_user=teacher)
    assert avg["count"] == 2 and avg["average"] == 4.0
    assert avg["distribution"][5] == 1 and avg["distribution"][3] == 1 and avg["distribution"][1] == 0


async def test_average_no_ratings(db, org, teacher):
    avg = await teacher_rating_average(teacher.id, db=db, current_user=teacher)
    assert avg["count"] == 0 and avg["average"] == 0


# ── RBAC ────────────────────────────────────────────────────────────────────────

async def test_ratings_rbac(db, org):
    for slug in ("manager", "teacher"):
        u = await _preset_user(db, org, slug)
        assert u.has_permission("school:read") and u.has_permission("school:write")
    for slug in ("parent", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("school:read") and not u.has_permission("school:write")
