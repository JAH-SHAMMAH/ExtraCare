"""Tests for HR Admin managed lists (Phase 1 — the 'Admin › Job' cluster).

One generic table (hr_managed_items) backs seven managed lists discriminated by
`list_type`. Every endpoint is gated ``hr:write``. These prove CRUD, list-type
validation, catalog counts and org isolation, plus that the hr:write gate
excludes hr:read-only teachers/staff — exercising the exact PermissionChecker.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.core.permissions import PermissionChecker
from app.routers.hr_admin import (
    list_catalog, list_items, create_item, update_item, delete_item,
)
from app.schemas.hr_admin import HrItemCreate, HrItemUpdate
from app.models.hr_admin import HR_LIST_TYPES


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


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def test_create_and_list_item(db, org, teacher):
    it = await create_item("job_title", HrItemCreate(name="  Senior Teacher  ", code="ST"),
                           db=db, current_user=teacher)
    assert it.name == "Senior Teacher"           # trimmed
    assert it.code == "ST" and it.is_active is True and it.list_type == "job_title"
    rows = await list_items("job_title", include_inactive=True, db=db, current_user=teacher)
    assert [r.id for r in rows] == [it.id]


async def test_list_scoped_to_its_type(db, org, teacher):
    await create_item("job_title", HrItemCreate(name="Bursar"), db=db, current_user=teacher)
    await create_item("pay_grade", HrItemCreate(name="Grade 8"), db=db, current_user=teacher)
    titles = await list_items("job_title", include_inactive=True, db=db, current_user=teacher)
    grades = await list_items("pay_grade", include_inactive=True, db=db, current_user=teacher)
    assert all(r.list_type == "job_title" for r in titles)
    assert all(r.list_type == "pay_grade" for r in grades)
    assert "Grade 8" not in [r.name for r in titles]


async def test_unknown_list_type_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_item("not_a_list", HrItemCreate(name="X"), db=db, current_user=teacher)
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException) as exc2:
        await list_items("not_a_list", include_inactive=True, db=db, current_user=teacher)
    assert exc2.value.status_code == 404


async def test_all_seven_list_types_accepted(db, org, teacher):
    for lt in HR_LIST_TYPES:
        it = await create_item(lt, HrItemCreate(name=f"{lt} item"), db=db, current_user=teacher)
        assert it.list_type == lt


async def test_include_inactive_toggle(db, org, teacher):
    active = await create_item("work_shift", HrItemCreate(name="Morning"), db=db, current_user=teacher)
    hidden = await create_item("work_shift", HrItemCreate(name="Night", is_active=False), db=db, current_user=teacher)
    all_rows = await list_items("work_shift", include_inactive=True, db=db, current_user=teacher)
    only_active = await list_items("work_shift", include_inactive=False, db=db, current_user=teacher)
    assert {active.id, hidden.id} <= {r.id for r in all_rows}
    assert active.id in {r.id for r in only_active}
    assert hidden.id not in {r.id for r in only_active}


async def test_update_item(db, org, teacher):
    it = await create_item("employment_status", HrItemCreate(name="Probation"), db=db, current_user=teacher)
    upd = await update_item(it.id, HrItemUpdate(name="  Confirmed  ", is_active=False),
                            db=db, current_user=teacher)
    assert upd.name == "Confirmed" and upd.is_active is False


async def test_delete_soft(db, org, teacher):
    it = await create_item("working_tool", HrItemCreate(name="Laptop"), db=db, current_user=teacher)
    await delete_item(it.id, db=db, current_user=teacher)
    rows = await list_items("working_tool", include_inactive=True, db=db, current_user=teacher)
    assert it.id not in [r.id for r in rows]
    with pytest.raises(HTTPException) as exc:
        await update_item(it.id, HrItemUpdate(name="Z"), db=db, current_user=teacher)
    assert exc.value.status_code == 404


async def test_catalog_counts(db, org, teacher):
    await create_item("job_title", HrItemCreate(name="A"), db=db, current_user=teacher)
    await create_item("job_title", HrItemCreate(name="B"), db=db, current_user=teacher)
    await create_item("job_category", HrItemCreate(name="Teaching"), db=db, current_user=teacher)
    catalog = await list_catalog(db=db, current_user=teacher)
    by_type = {c.list_type: c for c in catalog}
    assert len(catalog) == len(HR_LIST_TYPES)          # every list represented
    assert by_type["job_title"].count == 2
    assert by_type["job_category"].count == 1
    assert by_type["pay_grade"].count == 0
    assert by_type["job_title"].label == "Job Titles"


async def test_org_isolation(db, org, teacher):
    mine = await create_item("job_title", HrItemCreate(name="Only Mine"), db=db, current_user=teacher)
    other = SimpleNamespace(org_id=str(uuid.uuid4()))    # a user in a different org
    rows = await list_items("job_title", include_inactive=True, db=db, current_user=other)
    assert mine.id not in [r.id for r in rows]
    with pytest.raises(HTTPException) as exc:            # can't edit across orgs
        await update_item(mine.id, HrItemUpdate(name="Hijack"), db=db, current_user=other)
    assert exc.value.status_code == 404


# ── RBAC (exercise the exact hr:write gate the router uses) ────────────────────

async def _run_gate(user, org, db):
    checker = PermissionChecker("hr:write")
    request = SimpleNamespace(state=SimpleNamespace(org=org, org_id=org.id))
    return await checker(request=request, current_user=user, db=db)


async def test_hr_admin_lists_rbac(db, org):
    for slug in ("teacher", "nurse"):
        u = await _preset_user(db, org, slug)
        assert u.has_permission("hr:read") and not u.has_permission("hr:write")
        with pytest.raises(HTTPException) as exc:
            await _run_gate(u, org, db)
        assert exc.value.status_code == 403
    for slug in ("org_admin", "manager"):
        u = await _preset_user(db, org, slug)
        granted = await _run_gate(u, org, db)
        assert granted.id == u.id
