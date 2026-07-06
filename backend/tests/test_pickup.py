"""Tests for Store: Pickup Unit.

Configure the points where students collect store purchases, and track each
collection ticket from `pending` → `collected` (or `cancelled`). No ledger impact.
Proves:
  • create a pickup ticket (pending), student name auto-filled from student_id
  • collect → status/collected_at/collected_by set; only pending can collect (409)
  • cancel → status cancelled; only pending can cancel (409)
  • pickup point pending_count; can't delete a point with pending tickets (409)
  • list filters by status and point; RBAC on payments:write
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from starlette.requests import Request

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.finance import Pickup
from app.core.permissions import AnyPermissionChecker
from app.routers.modules.finance_ops import (
    create_pickup_point, update_pickup_point, delete_pickup_point, list_pickup_points,
    create_pickup, list_pickups, collect_pickup, cancel_pickup, delete_pickup,
)
from app.schemas.finance_ops import (
    PickupPointCreate, PickupPointUpdate, PickupCreate,
)


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


# ── Points ──────────────────────────────────────────────────────────────────────

async def test_create_and_update_point(db, org, teacher):
    pt = await create_pickup_point(PickupPointCreate(name="Front Desk", location="Reception"), db=db, current_user=teacher)
    assert pt.name == "Front Desk" and pt.location == "Reception" and pt.is_active is True
    assert pt.pending_count == 0
    upd = await update_pickup_point(pt.id, PickupPointUpdate(name="Main Gate", is_active=False), db=db, current_user=teacher)
    assert upd.name == "Main Gate" and upd.is_active is False
    listed = await list_pickup_points(db=db, current_user=teacher)
    assert any(p.id == pt.id for p in listed)


# ── Ticket lifecycle ──────────────────────────────────────────────────────────────

async def test_create_pickup_pending_with_student_name(db, org, teacher, student):
    pt = await create_pickup_point(PickupPointCreate(name="Store"), db=db, current_user=teacher)
    pk = await create_pickup(
        PickupCreate(pickup_point_id=pt.id, student_id=student.id, description="1x School bag", reference="SALE-1"),
        db=db, current_user=teacher,
    )
    assert pk.status == "pending"
    assert pk.pickup_point_name == "Store"
    # customer_name auto-filled from the student when not supplied
    assert pk.customer_name == f"{student.first_name} {student.last_name}".strip()
    # point now shows one pending ticket
    pts = await list_pickup_points(db=db, current_user=teacher)
    assert next(p for p in pts if p.id == pt.id).pending_count == 1


async def test_collect_sets_fields_and_is_idempotent_guarded(db, org, teacher):
    pt = await create_pickup_point(PickupPointCreate(name="Store"), db=db, current_user=teacher)
    pk = await create_pickup(PickupCreate(pickup_point_id=pt.id, customer_name="Walk-in", description="2x Pen"), db=db, current_user=teacher)
    done = await collect_pickup(pk.id, db=db, current_user=teacher)
    assert done.status == "collected"
    assert done.collected_at is not None
    assert done.collected_by == teacher.id
    # collecting again → 409
    with pytest.raises(HTTPException) as exc:
        await collect_pickup(pk.id, db=db, current_user=teacher)
    assert exc.value.status_code == 409
    # point pending_count back to 0
    pts = await list_pickup_points(db=db, current_user=teacher)
    assert next(p for p in pts if p.id == pt.id).pending_count == 0


async def test_cancel_only_from_pending(db, org, teacher):
    pk = await create_pickup(PickupCreate(customer_name="Ada", description="1x Ruler"), db=db, current_user=teacher)
    cancelled = await cancel_pickup(pk.id, db=db, current_user=teacher)
    assert cancelled.status == "cancelled"
    with pytest.raises(HTTPException) as exc:
        await collect_pickup(pk.id, db=db, current_user=teacher)
    assert exc.value.status_code == 409


async def test_list_filters_by_status_and_point(db, org, teacher):
    a = await create_pickup_point(PickupPointCreate(name="A"), db=db, current_user=teacher)
    b = await create_pickup_point(PickupPointCreate(name="B"), db=db, current_user=teacher)
    p1 = await create_pickup(PickupCreate(pickup_point_id=a.id, customer_name="one", description="x"), db=db, current_user=teacher)
    await create_pickup(PickupCreate(pickup_point_id=b.id, customer_name="two", description="y"), db=db, current_user=teacher)
    await collect_pickup(p1.id, db=db, current_user=teacher)
    pending = await list_pickups(status="pending", pickup_point_id=None, db=db, current_user=teacher)
    assert all(p.status == "pending" for p in pending)
    assert p1.id not in {p.id for p in pending}
    at_a = await list_pickups(status=None, pickup_point_id=a.id, db=db, current_user=teacher)
    assert {p.pickup_point_id for p in at_a} == {a.id}


# ── Guards ────────────────────────────────────────────────────────────────────────

async def test_cannot_delete_point_with_pending(db, org, teacher):
    pt = await create_pickup_point(PickupPointCreate(name="Store"), db=db, current_user=teacher)
    pk = await create_pickup(PickupCreate(pickup_point_id=pt.id, customer_name="x", description="item"), db=db, current_user=teacher)
    with pytest.raises(HTTPException) as exc:
        await delete_pickup_point(pt.id, db=db, current_user=teacher)
    assert exc.value.status_code == 409
    # collect it → now deletable
    await collect_pickup(pk.id, db=db, current_user=teacher)
    await delete_pickup_point(pt.id, db=db, current_user=teacher)
    assert all(p.id != pt.id for p in await list_pickup_points(db=db, current_user=teacher))


async def test_create_pickup_rejects_foreign_student(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_pickup(PickupCreate(student_id=str(uuid.uuid4()), description="item"), db=db, current_user=teacher)
    assert exc.value.status_code == 404


async def test_delete_pickup_soft(db, org, teacher):
    pk = await create_pickup(PickupCreate(customer_name="x", description="item"), db=db, current_user=teacher)
    await delete_pickup(pk.id, db=db, current_user=teacher)
    row = (await db.execute(select(Pickup).where(Pickup.id == pk.id))).scalar_one()
    assert row.is_deleted is True
    assert all(p.id != pk.id for p in await list_pickups(status=None, pickup_point_id=None, db=db, current_user=teacher))


# ── RBAC ──────────────────────────────────────────────────────────────────────────

async def test_pickup_rbac(db, org):
    # Pickup config + tickets are finance-clerk actions → payments:write.
    manager = await _preset_user(db, org, "manager")
    assert manager.has_permission("payments:write")
    for slug in ("teacher", "parent", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("payments:write")


def _request() -> Request:
    return Request({"type": "http", "headers": [], "state": {}})


async def test_collect_gate_allows_cashier_or_finance(db, org):
    """`collect` uses AnyPermissionChecker(store:sell, payments:write): a cashier
    (store:sell only) may collect; a manager (payments:write only) keeps access;
    someone with neither is 403. Additive — nobody who could collect before loses it."""
    gate = AnyPermissionChecker("store:sell", "payments:write")

    cashier = await _preset_user(db, org, "cashier")     # store:sell, NOT payments:write
    assert cashier.has_permission("store:sell") and not cashier.has_permission("payments:write")
    assert (await gate(_request(), current_user=cashier, db=db)) is cashier

    manager = await _preset_user(db, org, "manager")     # payments:write, NOT store:sell
    assert manager.has_permission("payments:write") and not manager.has_permission("store:sell")
    assert (await gate(_request(), current_user=manager, db=db)) is manager

    for slug in ("parent", "student"):                   # neither → blocked
        u = await _preset_user(db, org, slug)
        with pytest.raises(HTTPException) as exc:
            await gate(_request(), current_user=u, db=db)
        assert exc.value.status_code == 403
