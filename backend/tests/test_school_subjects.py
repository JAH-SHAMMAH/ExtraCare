"""Tests for GET/POST/PATCH/DELETE /school/subjects.

The Subject model existed but had no endpoint, so the Subject Management page
called a 404 (audit's broken-endpoint gap). Proves:
  • create persists the fields the UI captures (department, credit_hours,
    is_active, free-text teacher_name) — not just name/code
  • list maps to the frontend Subject shape (code "" when null, class_ids [])
    and search filters name/code/department
  • update persists changes (toggle is_active, change department)
  • delete works when unused but is blocked (409) once grades reference it
  • RBAC: read = school:read, writes = school:write
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import Subject, Grade
from app.routers.modules.school import (
    list_subjects, get_subject, create_subject, update_subject, delete_subject,
)
from app.schemas.subject import SubjectCreate, SubjectUpdate


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


# ── Create persists the full UI field set ───────────────────────────────────────

async def test_create_persists_ui_fields(db, org, teacher):
    resp = await create_subject(
        SubjectCreate(name="Mathematics", code="MTH101", department="Sciences",
                      credit_hours=3, teacher_name="Mr Ade"),
        request=None, db=db, current_user=teacher,
    )
    assert resp["name"] == "Mathematics" and resp["code"] == "MTH101"
    assert resp["department"] == "Sciences" and resp["credit_hours"] == 3
    assert resp["teacher_name"] == "Mr Ade" and resp["is_active"] is True
    assert resp["class_ids"] == []
    row = (await db.execute(select(Subject).where(Subject.id == resp["id"]))).scalar_one()
    assert row.department == "Sciences" and row.credit_hours == 3 and row.teacher_name == "Mr Ade"


async def test_create_defaults(db, org, teacher):
    resp = await create_subject(SubjectCreate(name="Civics"), request=None, db=db, current_user=teacher)
    assert resp["code"] == "" and resp["credit_hours"] == 1 and resp["is_active"] is True


# ── List + search ────────────────────────────────────────────────────────────────

async def test_list_and_search(db, org, teacher):
    await create_subject(SubjectCreate(name="Biology", code="BIO", department="Sciences"), request=None, db=db, current_user=teacher)
    await create_subject(SubjectCreate(name="History", code="HIS", department="Arts"), request=None, db=db, current_user=teacher)
    allres = await list_subjects(page=1, page_size=100, search=None, db=db, current_user=teacher)
    assert allres["total"] == 2
    by_dept = await list_subjects(page=1, page_size=100, search="Arts", db=db, current_user=teacher)
    assert by_dept["total"] == 1 and by_dept["items"][0]["name"] == "History"
    by_code = await list_subjects(page=1, page_size=100, search="BIO", db=db, current_user=teacher)
    assert by_code["total"] == 1 and by_code["items"][0]["name"] == "Biology"


# ── Update persists ──────────────────────────────────────────────────────────────

async def test_update_persists(db, org, teacher):
    s = await create_subject(SubjectCreate(name="Physics", department="Sciences"), request=None, db=db, current_user=teacher)
    resp = await update_subject(s["id"], SubjectUpdate(department="Applied Sciences", is_active=False, credit_hours=4),
                                request=None, db=db, current_user=teacher)
    assert resp["department"] == "Applied Sciences" and resp["is_active"] is False and resp["credit_hours"] == 4
    row = (await db.execute(select(Subject).where(Subject.id == s["id"]))).scalar_one()
    assert row.department == "Applied Sciences" and row.is_active is False


async def test_get_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await get_subject(str(uuid.uuid4()), db=db, current_user=teacher)
    assert exc.value.status_code == 404


# ── Delete + guard ───────────────────────────────────────────────────────────────

async def test_delete_unused(db, org, teacher):
    s = await create_subject(SubjectCreate(name="Temp"), request=None, db=db, current_user=teacher)
    await delete_subject(s["id"], request=None, db=db, current_user=teacher)
    gone = (await db.execute(select(Subject).where(Subject.id == s["id"]))).scalar_one_or_none()
    assert gone is None


async def test_delete_blocked_when_graded(db, org, teacher, student):
    s = await create_subject(SubjectCreate(name="Chemistry"), request=None, db=db, current_user=teacher)
    db.add(Grade(id=str(uuid.uuid4()), student_id=student.id, subject_id=s["id"],
                 score=80, max_score=100, term="Term 1", org_id=org.id))
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await delete_subject(s["id"], request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 409


# ── RBAC ────────────────────────────────────────────────────────────────────────

async def test_subjects_rbac(db, org):
    for slug in ("manager", "teacher"):
        u = await _preset_user(db, org, slug)
        assert u.has_permission("school:read") and u.has_permission("school:write")
    for slug in ("parent", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("school:read") and not u.has_permission("school:write")
