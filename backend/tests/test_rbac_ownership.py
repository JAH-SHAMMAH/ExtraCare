"""RBAC ownership scoping (Finding #1).

The student roster, report-card and per-student attendance endpoints take an
arbitrary `student_id`. Staff-side roles (admin/manager/teacher/staff/viewer —
anyone whose grant covers `school:students:read`) may view any student in their
org, but a STUDENT or PARENT must only reach their own record / linked children.

Handlers are called directly per the conftest convention, so the in-handler
`_ensure_student_visible` guard is exercised even though the FastAPI permission
dependency layer is bypassed. Users are built with their `roles` collection
populated *before* flush so `has_permission` never triggers an async lazyload.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role
from app.models.modules.school import Student, ParentGuardian
from app.routers.modules.school import get_report_card, student_attendance_history


pytestmark = pytest.mark.asyncio


async def _make_user(db, org, email: str, perms: list[str] | None = None) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email=email,
        full_name=email.split("@")[0].title(),
        status=UserStatus.ACTIVE,
        org_id=org.id,
    )
    roles: list[Role] = []
    if perms:
        role = Role(
            id=str(uuid.uuid4()),
            name="Scoped",
            slug=f"scoped-{uuid.uuid4().hex[:6]}",
            permissions=perms,
            org_id=org.id,
            is_system=False,
        )
        db.add(role)
        roles = [role]
    # Assign while the User is still transient so the collection is treated as
    # loaded — avoids a sync lazyload of `roles` in the async handler path.
    u.roles = roles
    db.add(u)
    await db.commit()
    return u


async def _make_student(db, org, email: str, sid: str = "S-100") -> Student:
    s = Student(
        id=str(uuid.uuid4()),
        student_id=sid,
        first_name="Test",
        last_name="Child",
        email=email,
        org_id=org.id,
    )
    db.add(s)
    await db.commit()
    return s


# ── report-card ──────────────────────────────────────────────────────────────

async def test_report_card_blocks_unrelated_student(db, org):
    """A student calling another student's report card is rejected."""
    kid = await _make_user(db, org, "kid@example.com")
    victim = await _make_student(db, org, "victim@example.com", "S-999")
    with pytest.raises(HTTPException) as exc:
        await get_report_card(student_id=victim.id, db=db, current_user=kid)
    assert exc.value.status_code == 403


async def test_report_card_allows_own_record(db, org):
    """The linked student (matched by email) may read their own report card."""
    kid = await _make_user(db, org, "kid@example.com")
    own = await _make_student(db, org, "kid@example.com", "S-100")
    out = await get_report_card(student_id=own.id, db=db, current_user=kid)
    assert out["student_id"] == own.id


async def test_report_card_allows_linked_parent(db, org):
    """A guardian linked via ParentGuardian may read their child's report card."""
    parent = await _make_user(db, org, "parent@example.com")
    child = await _make_student(db, org, "child@example.com")
    db.add(ParentGuardian(
        id=str(uuid.uuid4()),
        user_id=parent.id,
        student_id=child.id,
        relationship_type="parent",
        is_primary=True,
        org_id=org.id,
    ))
    await db.commit()
    out = await get_report_card(student_id=child.id, db=db, current_user=parent)
    assert out["student_id"] == child.id


async def test_report_card_allows_staff_role(db, org):
    """A user whose grant covers school:students:read sees any student."""
    staff = await _make_user(db, org, "staff@example.com", perms=["school:read"])
    child = await _make_student(db, org, "child@example.com")
    out = await get_report_card(student_id=child.id, db=db, current_user=staff)
    assert out["student_id"] == child.id


# ── per-student attendance ────────────────────────────────────────────────────

async def test_attendance_history_blocks_unrelated_student(db, org):
    kid = await _make_user(db, org, "kid@example.com")
    victim = await _make_student(db, org, "victim@example.com", "S-999")
    with pytest.raises(HTTPException) as exc:
        await student_attendance_history(student_id=victim.id, db=db, current_user=kid)
    assert exc.value.status_code == 403


async def test_attendance_history_allows_own_record(db, org):
    kid = await _make_user(db, org, "kid@example.com")
    own = await _make_student(db, org, "kid@example.com", "S-100")
    out = await student_attendance_history(student_id=own.id, db=db, current_user=kid)
    assert out["student_id"] == own.id
