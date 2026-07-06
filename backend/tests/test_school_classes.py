"""Tests for GET/POST/PATCH/DELETE /school/classes.

The list endpoint was missing entirely, so class dropdowns rendered empty
app-wide (enrollment, class pickers). Proves:
  • list returns existing classes mapped to the frontend SchoolClass shape
    (grade_level, section, capacity, class_teacher_name, student_count, is_active)
  • create/update map frontend names -> ORM columns (grade_level->level,
    capacity->max_capacity, class_teacher_id->teacher_id) and persist `section`
  • student_count is computed; delete is blocked while students are enrolled
  • RBAC: read = school:read, writes = school:write
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import SchoolClass
from app.routers.modules.school import (
    list_classes, get_class, create_class, update_class, delete_class,
)
from app.schemas.school_class import ClassCreate, ClassUpdate


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


# ── The bug: list must return existing classes (not empty) ──────────────────────

async def test_list_returns_existing_classes(db, org, teacher, school_class):
    res = await list_classes(page=1, page_size=100, search=None, db=db, current_user=teacher)
    assert res["total"] == 1
    row = res["items"][0]
    assert row["id"] == school_class.id
    assert row["name"] == "Grade 10A"
    assert row["grade_level"] == "Secondary"          # level -> grade_level
    assert row["class_teacher_id"] == teacher.id
    assert row["class_teacher_name"] == teacher.full_name   # resolved
    assert row["is_active"] is True
    assert row["student_count"] == 0


async def test_student_count_computed(db, org, teacher, school_class, student):
    res = await list_classes(page=1, page_size=100, search=None, db=db, current_user=teacher)
    row = next(r for r in res["items"] if r["id"] == school_class.id)
    assert row["student_count"] == 1


async def test_search_filters(db, org, teacher, school_class):
    hit = await list_classes(page=1, page_size=100, search="Grade 10", db=db, current_user=teacher)
    assert hit["total"] == 1
    miss = await list_classes(page=1, page_size=100, search="Nursery", db=db, current_user=teacher)
    assert miss["total"] == 0


# ── Create / update field mapping ───────────────────────────────────────────────

async def test_create_maps_frontend_names(db, org, teacher):
    resp = await create_class(
        ClassCreate(name="JSS 1A", grade_level="JSS 1", section="A", capacity=35, academic_year="2025/2026"),
        request=None, db=db, current_user=teacher,
    )
    assert resp["grade_level"] == "JSS 1" and resp["section"] == "A" and resp["capacity"] == 35
    # ORM columns actually persisted under the mapped names.
    row = (await db.execute(select(SchoolClass).where(SchoolClass.id == resp["id"]))).scalar_one()
    assert row.level == "JSS 1" and row.section == "A" and row.max_capacity == 35


async def test_update_maps_and_persists(db, org, teacher, school_class):
    resp = await update_class(
        school_class.id, ClassUpdate(grade_level="Primary", capacity=50, section="B"),
        request=None, db=db, current_user=teacher,
    )
    assert resp["grade_level"] == "Primary" and resp["capacity"] == 50 and resp["section"] == "B"
    row = (await db.execute(select(SchoolClass).where(SchoolClass.id == school_class.id))).scalar_one()
    assert row.level == "Primary" and row.max_capacity == 50


async def test_create_rejects_foreign_teacher(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_class(ClassCreate(name="X", class_teacher_id=str(uuid.uuid4())), request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 404


# ── Delete guard ────────────────────────────────────────────────────────────────

async def test_delete_blocked_while_students_enrolled(db, org, teacher, school_class, student):
    with pytest.raises(HTTPException) as exc:
        await delete_class(school_class.id, request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 409


async def test_delete_empty_class(db, org, teacher):
    c = await create_class(ClassCreate(name="Temp"), request=None, db=db, current_user=teacher)
    await delete_class(c["id"], request=None, db=db, current_user=teacher)
    gone = (await db.execute(select(SchoolClass).where(SchoolClass.id == c["id"]))).scalar_one_or_none()
    assert gone is None


async def test_get_class_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await get_class(str(uuid.uuid4()), db=db, current_user=teacher)
    assert exc.value.status_code == 404


# ── RBAC ────────────────────────────────────────────────────────────────────────

async def test_classes_rbac(db, org):
    # Managers/admins read+write; teachers hold school:read+write (self-serve teaching);
    # parents/students hold neither.
    for slug in ("manager", "teacher"):
        u = await _preset_user(db, org, slug)
        assert u.has_permission("school:read") and u.has_permission("school:write")
    for slug in ("parent", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("school:read") and not u.has_permission("school:write")
