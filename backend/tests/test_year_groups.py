"""Manage YearGroups — the class-level taxonomy CRUD + reorder.

Proves create auto-appends to the order, updates round-trip (rename / category /
mock), a duplicate name 409s, delete removes it, and reorder persists positions
from the supplied id order.
"""
import uuid

import pytest
from fastapi import HTTPException

from app.routers.modules.school import (
    list_year_groups, create_year_group, update_year_group, delete_year_group, reorder_year_groups,
)
from app.schemas.year_group import YearGroupCreate, YearGroupUpdate, ReorderRequest

pytestmark = pytest.mark.asyncio


async def _mk(db, user, name, **kw):
    return await create_year_group(YearGroupCreate(name=name, **kw), db=db, current_user=user)


async def test_year_group_crud_and_order(db, org, teacher):
    a = await _mk(db, teacher, "YEAR 7", short_code="Y7")
    b = await _mk(db, teacher, "YEAR 8")
    assert a["position"] == 0 and b["position"] == 1   # auto-append
    assert a["category"] == "active" and a["is_mock"] is False

    upd = await update_year_group(a["id"], YearGroupUpdate(name="Year 7", category="active", is_mock=True), db=db, current_user=teacher)
    assert upd["name"] == "Year 7" and upd["is_mock"] is True

    listed = await list_year_groups(db=db, current_user=teacher)
    assert [y["id"] for y in listed] == [a["id"], b["id"]]   # ordered by position

    await delete_year_group(b["id"], db=db, current_user=teacher)
    assert [y["id"] for y in await list_year_groups(db=db, current_user=teacher)] == [a["id"]]


async def test_year_group_reorder(db, org, teacher):
    a = await _mk(db, teacher, "YEAR 9")
    b = await _mk(db, teacher, "YEAR 10")
    c = await _mk(db, teacher, "YEAR 11")
    reordered = await reorder_year_groups(ReorderRequest(ids=[c["id"], a["id"], b["id"]]), db=db, current_user=teacher)
    assert [y["id"] for y in reordered] == [c["id"], a["id"], b["id"]]
    assert [y["position"] for y in reordered] == [0, 1, 2]


async def test_year_group_duplicate_conflicts(db, org, teacher):
    # Duplicate name 409s — kept last (the IntegrityError leaves the async session
    # unusable without the rollback the request lifecycle would do).
    await _mk(db, teacher, "Entrance Examination", category="prospective")
    with pytest.raises(HTTPException) as ei:
        await _mk(db, teacher, "Entrance Examination")
    assert ei.value.status_code == 409
