"""Tests for Store: Warehouse module (multi-location stock).

Own module — physical stock movements (receive / transfer / issue) with per-location
balances, no ledger impact. Proves:
  • receive increments a location's on-hand; the store's sellable quantity is untouched
  • transfer moves stock between locations (source ↓, dest ↑); insufficient → 422
  • issue decrements; over-issue → 422
  • can't delete a warehouse that still holds stock; low-stock flag; RBAC
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.finance import StoreItem, WarehouseStock
from app.routers.modules.finance_ops import (
    create_warehouse, update_warehouse, delete_warehouse, list_warehouses,
    warehouse_stock, warehouse_receive, warehouse_issue, warehouse_transfer,
)
from app.schemas.finance_ops import (
    WarehouseCreate, WarehouseUpdate, StockReceive, StockTransfer, StockIssue,
)


pytestmark = pytest.mark.asyncio


async def _item(db, org, name, qty=0, reorder=0) -> StoreItem:
    it = StoreItem(id=str(uuid.uuid4()), name=name, unit_price=Decimal(100), cost_price=Decimal(0),
                   quantity=Decimal(qty), reorder_level=Decimal(reorder), is_active=True, org_id=org.id)
    db.add(it)
    await db.commit()
    return it


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


async def _qty(db, wid, iid) -> float:
    s = (await db.execute(select(WarehouseStock).where(WarehouseStock.warehouse_id == wid, WarehouseStock.item_id == iid))).scalar_one_or_none()
    return float(s.quantity) if s else 0.0


# ── Receive / balances ────────────────────────────────────────────────────────

async def test_receive_increments_location_not_sellable(db, org, teacher):
    it = await _item(db, org, "Exercise Book", qty=5)   # store sellable = 5
    wh = await create_warehouse(WarehouseCreate(name="Main Store"), db=db, current_user=teacher)
    rows = await warehouse_receive(StockReceive(warehouse_id=wh.id, item_id=it.id, quantity=100), db=db, current_user=teacher)
    assert rows[0].quantity == 100.0
    assert await _qty(db, wh.id, it.id) == 100.0
    # store's own sellable quantity is untouched (separate module)
    reloaded = (await db.execute(select(StoreItem).where(StoreItem.id == it.id))).scalar_one()
    assert float(reloaded.quantity) == 5.0
    # warehouse response reflects holdings
    listed = await list_warehouses(db=db, current_user=teacher)
    ours = next(w for w in listed if w.id == wh.id)
    assert ours.item_count == 1 and ours.total_units == 100.0


async def test_transfer_moves_between_locations(db, org, teacher):
    it = await _item(db, org, "Marker")
    main = await create_warehouse(WarehouseCreate(name="Main"), db=db, current_user=teacher)
    annex = await create_warehouse(WarehouseCreate(name="Annex"), db=db, current_user=teacher)
    await warehouse_receive(StockReceive(warehouse_id=main.id, item_id=it.id, quantity=50), db=db, current_user=teacher)
    rows = await warehouse_transfer(StockTransfer(from_warehouse_id=main.id, to_warehouse_id=annex.id, item_id=it.id, quantity=20), db=db, current_user=teacher)
    assert await _qty(db, main.id, it.id) == 30.0
    assert await _qty(db, annex.id, it.id) == 20.0
    # returns both affected rows
    assert {r.quantity for r in rows} == {30.0, 20.0}


async def test_transfer_insufficient_and_same_warehouse(db, org, teacher):
    it = await _item(db, org, "Pen")
    a = await create_warehouse(WarehouseCreate(name="A"), db=db, current_user=teacher)
    b = await create_warehouse(WarehouseCreate(name="B"), db=db, current_user=teacher)
    await warehouse_receive(StockReceive(warehouse_id=a.id, item_id=it.id, quantity=10), db=db, current_user=teacher)
    with pytest.raises(HTTPException) as exc:
        await warehouse_transfer(StockTransfer(from_warehouse_id=a.id, to_warehouse_id=b.id, item_id=it.id, quantity=999), db=db, current_user=teacher)
    assert exc.value.status_code == 422
    with pytest.raises(HTTPException) as exc:
        await warehouse_transfer(StockTransfer(from_warehouse_id=a.id, to_warehouse_id=a.id, item_id=it.id, quantity=1), db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_issue_decrements_and_guards(db, org, teacher):
    it = await _item(db, org, "Chalk")
    wh = await create_warehouse(WarehouseCreate(name="Store"), db=db, current_user=teacher)
    await warehouse_receive(StockReceive(warehouse_id=wh.id, item_id=it.id, quantity=8), db=db, current_user=teacher)
    await warehouse_issue(StockIssue(warehouse_id=wh.id, item_id=it.id, quantity=3), db=db, current_user=teacher)
    assert await _qty(db, wh.id, it.id) == 5.0
    with pytest.raises(HTTPException) as exc:
        await warehouse_issue(StockIssue(warehouse_id=wh.id, item_id=it.id, quantity=99), db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_low_stock_flag(db, org, teacher):
    it = await _item(db, org, "Ruler", reorder=20)
    wh = await create_warehouse(WarehouseCreate(name="Store"), db=db, current_user=teacher)
    await warehouse_receive(StockReceive(warehouse_id=wh.id, item_id=it.id, quantity=15), db=db, current_user=teacher)  # 15 <= 20
    rows = await warehouse_stock(wh.id, db=db, current_user=teacher)
    assert rows[0].low_stock is True and rows[0].reorder_level == 20.0


async def test_cannot_delete_warehouse_with_stock(db, org, teacher):
    it = await _item(db, org, "Book")
    wh = await create_warehouse(WarehouseCreate(name="Store"), db=db, current_user=teacher)
    await warehouse_receive(StockReceive(warehouse_id=wh.id, item_id=it.id, quantity=5), db=db, current_user=teacher)
    with pytest.raises(HTTPException) as exc:
        await delete_warehouse(wh.id, db=db, current_user=teacher)
    assert exc.value.status_code == 409
    # issue it all out → now deletable
    await warehouse_issue(StockIssue(warehouse_id=wh.id, item_id=it.id, quantity=5), db=db, current_user=teacher)
    await delete_warehouse(wh.id, db=db, current_user=teacher)
    assert all(w.id != wh.id for w in await list_warehouses(db=db, current_user=teacher))


async def test_update_warehouse(db, org, teacher):
    wh = await create_warehouse(WarehouseCreate(name="Old"), db=db, current_user=teacher)
    updated = await update_warehouse(wh.id, WarehouseUpdate(name="New", location="Block C", is_active=False), db=db, current_user=teacher)
    assert updated.name == "New" and updated.location == "Block C" and updated.is_active is False


# ── RBAC ──────────────────────────────────────────────────────────────────────

async def test_warehouse_rbac(db, org):
    # Warehouse stock ops are physical movements (no ledger) → payments:write.
    manager = await _preset_user(db, org, "manager")
    assert manager.has_permission("payments:write")
    for slug in ("teacher", "parent", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("payments:write")
