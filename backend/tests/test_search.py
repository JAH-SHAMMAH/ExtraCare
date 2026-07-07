"""Tests for GET /search — the global top-bar search.

The search box called /search, which didn't exist. Proves:
  • students matching the query come back as {module, label, sublabel}
  • RBAC: a caller without school read scope gets NO student rows (no leak)
  • the `modules` filter narrows which buckets are searched
"""
from __future__ import annotations

import uuid

import pytest

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.routers.search import global_search

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


async def test_search_finds_students_for_staff(db, org, student):
    staff = await _preset_user(db, org, "teacher")  # holds school:read
    res = await global_search(q=student.first_name[:3], modules=None, db=db, current_user=staff)
    students = [i for i in res["items"] if i["module"] == "students"]
    assert any(student.first_name in i["label"] for i in students)
    assert all(set(i.keys()) >= {"module", "label", "sublabel"} for i in res["items"])


async def test_search_hides_students_from_parent(db, org, student):
    parent = await _preset_user(db, org, "parent")  # no school:read
    res = await global_search(q=student.first_name[:3], modules=None, db=db, current_user=parent)
    assert all(i["module"] != "students" for i in res["items"])


async def test_modules_filter_excludes_students(db, org, student):
    staff = await _preset_user(db, org, "teacher")
    res = await global_search(q=student.first_name[:3], modules="users", db=db, current_user=staff)
    assert all(i["module"] != "students" for i in res["items"])
