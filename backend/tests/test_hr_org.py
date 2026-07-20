"""Tests for Organization Structure (org units).

Gated hr:write. Covers CRUD, parent/head validation, the re-parent cycle guard
(a unit can't sit under itself or a descendant), the guarded delete (a unit with
sub-units can't be removed), org isolation, and the hr:write RBAC boundary.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.core.permissions import PermissionChecker
from app.routers.hr_org import list_units, create_unit, update_unit, delete_unit
from app.schemas.hr_org import OrgUnitCreate, OrgUnitUpdate

pytestmark = pytest.mark.asyncio


async def _staff(db, org, name) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{name}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=name, status=UserStatus.ACTIVE, org_id=org.id)
    db.add(u)
    await db.commit()
    return u


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


# ── CRUD + hierarchy ──────────────────────────────────────────────────────────

async def test_create_and_list(db, org, teacher):
    head = await _staff(db, org, "Head One")
    root = await create_unit(OrgUnitCreate(name="Academics", unit_type="division", head_user_id=head.id), db=db, current_user=teacher)
    assert root.parent_id is None and root.head_name == "Head One"
    child = await create_unit(OrgUnitCreate(name="Science Dept", unit_type="department", parent_id=root.id), db=db, current_user=teacher)
    assert child.parent_id == root.id
    listed = await list_units(db=db, current_user=teacher)
    assert {u.name for u in listed} == {"Academics", "Science Dept"}


async def test_unknown_parent_and_head_404(db, org, teacher):
    with pytest.raises(HTTPException) as e1:
        await create_unit(OrgUnitCreate(name="X", parent_id="nope"), db=db, current_user=teacher)
    assert e1.value.status_code == 404
    with pytest.raises(HTTPException) as e2:
        await create_unit(OrgUnitCreate(name="Y", head_user_id="nope"), db=db, current_user=teacher)
    assert e2.value.status_code == 404


async def test_reparent_cycle_guard(db, org, teacher):
    a = await create_unit(OrgUnitCreate(name="A"), db=db, current_user=teacher)
    b = await create_unit(OrgUnitCreate(name="B", parent_id=a.id), db=db, current_user=teacher)
    c = await create_unit(OrgUnitCreate(name="C", parent_id=b.id), db=db, current_user=teacher)
    # A under itself → 422
    with pytest.raises(HTTPException) as e0:
        await update_unit(a.id, OrgUnitUpdate(parent_id=a.id), db=db, current_user=teacher)
    assert e0.value.status_code == 422
    # A under C (its own grandchild) → 422
    with pytest.raises(HTTPException) as e1:
        await update_unit(a.id, OrgUnitUpdate(parent_id=c.id), db=db, current_user=teacher)
    assert e1.value.status_code == 422
    # Valid re-parent: C under A (A is not a descendant of C) → ok
    moved = await update_unit(c.id, OrgUnitUpdate(parent_id=a.id), db=db, current_user=teacher)
    assert moved.parent_id == a.id


async def test_clear_parent_to_root(db, org, teacher):
    a = await create_unit(OrgUnitCreate(name="A"), db=db, current_user=teacher)
    b = await create_unit(OrgUnitCreate(name="B", parent_id=a.id), db=db, current_user=teacher)
    moved = await update_unit(b.id, OrgUnitUpdate(parent_id=None), db=db, current_user=teacher)
    assert moved.parent_id is None


async def test_guarded_delete_blocks_parent_with_children(db, org, teacher):
    a = await create_unit(OrgUnitCreate(name="A"), db=db, current_user=teacher)
    b = await create_unit(OrgUnitCreate(name="B", parent_id=a.id), db=db, current_user=teacher)
    with pytest.raises(HTTPException) as exc:
        await delete_unit(a.id, db=db, current_user=teacher)
    assert exc.value.status_code == 409          # must clear children first
    # Remove the leaf, then the parent is deletable.
    await delete_unit(b.id, db=db, current_user=teacher)
    await delete_unit(a.id, db=db, current_user=teacher)
    assert await list_units(db=db, current_user=teacher) == []


async def test_org_isolation(db, org, teacher):
    mine = await create_unit(OrgUnitCreate(name="Mine"), db=db, current_user=teacher)
    other = SimpleNamespace(org_id=str(uuid.uuid4()))
    assert mine.id not in [u.id for u in await list_units(db=db, current_user=other)]
    with pytest.raises(HTTPException) as exc:
        await update_unit(mine.id, OrgUnitUpdate(name="Hijack"), db=db, current_user=other)
    assert exc.value.status_code == 404


# ── RBAC ──────────────────────────────────────────────────────────────────────

async def _run_gate(user, org, db):
    checker = PermissionChecker("hr:write")
    request = SimpleNamespace(state=SimpleNamespace(org=org, org_id=org.id))
    return await checker(request=request, current_user=user, db=db)


async def test_org_structure_rbac(db, org):
    tchr = await _preset_user(db, org, "teacher")
    assert not tchr.has_permission("hr:write")
    with pytest.raises(HTTPException) as exc:
        await _run_gate(tchr, org, db)
    assert exc.value.status_code == 403
    for slug in ("org_admin", "manager"):
        u = await _preset_user(db, org, slug)
        assert (await _run_gate(u, org, db)).id == u.id
