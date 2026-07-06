"""Tests for the Parents Directory (Batch 1, People & HR).

Covers CRUD over guardian↔student links, tenant isolation, search, and the
RBAC contract (staff-side read via the broad-grant hierarchy; students/parents
never reach it). Handlers are called directly per the conftest convention.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.organization import Organization, IndustryType
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import Student
from app.routers.modules.parents import (
    list_parent_links, create_parent_link, update_parent_link, delete_parent_link,
)
from app.schemas.people import ParentLinkCreate, ParentLinkUpdate


pytestmark = pytest.mark.asyncio


# ── helpers ───────────────────────────────────────────────────────────────────

async def _preset_user(db, org, slug: str) -> User:
    u = User(
        id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
        full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id,
    )
    role = Role(
        id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
        permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False,
    )
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _link(db, current_user, *, user_id, student_id, rel="parent", primary=False):
    return await create_parent_link(
        ParentLinkCreate(user_id=user_id, student_id=student_id, relationship_type=rel, is_primary=primary),
        request=None, db=db, current_user=current_user,
    )


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def test_create_and_list(db, org, teacher, unlinked_user, student):
    link = await _link(db, teacher, user_id=unlinked_user.id, student_id=student.id, rel="parent", primary=True)
    assert link.parent.id == unlinked_user.id
    assert link.student.id == student.id
    assert link.is_primary is True
    assert link.student.full_name == "Ada Okafor"

    listing = await list_parent_links(search=None, page=1, page_size=25, db=db, current_user=teacher)
    assert listing.total == 1
    assert listing.items[0].id == link.id


async def test_duplicate_link_returns_409(db, org, teacher, unlinked_user, student):
    await _link(db, teacher, user_id=unlinked_user.id, student_id=student.id)
    with pytest.raises(HTTPException) as exc:
        await _link(db, teacher, user_id=unlinked_user.id, student_id=student.id)
    assert exc.value.status_code == 409


async def test_create_rejects_user_outside_org(db, org, teacher, student):
    other = Organization(id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:6]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    outsider = User(id=str(uuid.uuid4()), email="out@example.com", full_name="Out",
                    status=UserStatus.ACTIVE, org_id=other.id)
    db.add(outsider)
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await _link(db, teacher, user_id=outsider.id, student_id=student.id)
    assert exc.value.status_code == 404


async def test_create_rejects_unknown_student(db, org, teacher, unlinked_user):
    with pytest.raises(HTTPException) as exc:
        await _link(db, teacher, user_id=unlinked_user.id, student_id="nope")
    assert exc.value.status_code == 404


async def test_update_relationship_and_primary(db, org, teacher, unlinked_user, student):
    link = await _link(db, teacher, user_id=unlinked_user.id, student_id=student.id, rel="parent", primary=False)
    updated = await update_parent_link(
        link.id, ParentLinkUpdate(relationship_type="guardian", is_primary=True),
        request=None, db=db, current_user=teacher,
    )
    assert updated.relationship_type == "guardian"
    assert updated.is_primary is True


async def test_update_rejects_bad_relationship(db, org, teacher, unlinked_user, student):
    link = await _link(db, teacher, user_id=unlinked_user.id, student_id=student.id)
    with pytest.raises(HTTPException) as exc:
        await update_parent_link(link.id, ParentLinkUpdate(relationship_type="spouse"),
                                 request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_delete_unlinks(db, org, teacher, unlinked_user, student):
    link = await _link(db, teacher, user_id=unlinked_user.id, student_id=student.id)
    await delete_parent_link(link.id, request=None, db=db, current_user=teacher)
    listing = await list_parent_links(search=None, page=1, page_size=25, db=db, current_user=teacher)
    assert listing.total == 0


async def test_delete_missing_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await delete_parent_link("missing", request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 404


# ── search ────────────────────────────────────────────────────────────────────

async def test_search_by_parent_and_student(db, org, teacher, unlinked_user, student):
    await _link(db, teacher, user_id=unlinked_user.id, student_id=student.id)
    by_parent = await list_parent_links(search="unlinked", page=1, page_size=25, db=db, current_user=teacher)
    assert by_parent.total == 1
    by_student = await list_parent_links(search="ada", page=1, page_size=25, db=db, current_user=teacher)
    assert by_student.total == 1
    none = await list_parent_links(search="zzzz", page=1, page_size=25, db=db, current_user=teacher)
    assert none.total == 0


# ── tenant isolation ──────────────────────────────────────────────────────────

async def test_list_is_tenant_scoped(db, org, teacher, unlinked_user, student):
    await _link(db, teacher, user_id=unlinked_user.id, student_id=student.id)

    other = Organization(id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:6]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    teacher2 = User(id=str(uuid.uuid4()), email="t2@example.com", full_name="T2",
                    status=UserStatus.ACTIVE, org_id=other.id)
    db.add(teacher2)
    await db.commit()

    mine = await list_parent_links(search=None, page=1, page_size=25, db=db, current_user=teacher)
    theirs = await list_parent_links(search=None, page=1, page_size=25, db=db, current_user=teacher2)
    assert mine.total == 1
    assert theirs.total == 0


# ── RBAC contract ─────────────────────────────────────────────────────────────

async def test_rbac_parents_scope_visibility(db, org):
    # Staff-side roles reach the directory (via the school:read/write hierarchy).
    for slug in ("org_admin", "manager", "teacher"):
        u = await _preset_user(db, org, slug)
        assert u.has_permission("school:parents:read"), f"{slug} should read"
        assert u.has_permission("school:parents:write"), f"{slug} should write"
    # Read-only staff: read yes, write no.
    for slug in ("staff", "viewer"):
        u = await _preset_user(db, org, slug)
        assert u.has_permission("school:parents:read"), f"{slug} should read"
        assert not u.has_permission("school:parents:write"), f"{slug} must not write"
    # Low-trust roles never see the guardian directory.
    for slug in ("student", "parent"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("school:parents:read"), f"{slug} must not read"
        assert not u.has_permission("school:parents:write"), f"{slug} must not write"
