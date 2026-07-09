"""Tests for Sales Monitor (read-only store-sales analytics)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.finance import StoreItem, StoreSale
from app.routers.modules.finance_ops import create_store_sale, void_store_sale, store_sales_summary
from app.schemas.finance_ops import StoreSaleCreate, StoreSaleLineInput


pytestmark = pytest.mark.asyncio


async def _item(db, org, name, qty, price) -> StoreItem:
    it = StoreItem(id=str(uuid.uuid4()), name=name, unit_price=Decimal(price), cost_price=Decimal(0),
                   quantity=Decimal(qty), reorder_level=Decimal(0), is_active=True, org_id=org.id)
    db.add(it)
    await db.commit()
    return it


async def _user(db, org, name) -> User:
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


async def _seed(db, org):
    it = await _item(db, org, "Exercise Book", qty=100, price=100)
    ada = await _user(db, org, "Ada Cashier")
    bola = await _user(db, org, "Bola Cashier")
    # Ada: 2 cash sales (200 + 100); Bola: 1 transfer sale (300)
    await create_store_sale(StoreSaleCreate(payment_method="cash", lines=[StoreSaleLineInput(item_id=it.id, quantity=2)]), request=None, db=db, current_user=ada)
    await create_store_sale(StoreSaleCreate(payment_method="cash", lines=[StoreSaleLineInput(item_id=it.id, quantity=1)]), request=None, db=db, current_user=ada)
    await create_store_sale(StoreSaleCreate(payment_method="transfer", lines=[StoreSaleLineInput(item_id=it.id, quantity=3)]), request=None, db=db, current_user=bola)
    return it, ada, bola


async def test_summary_totals_and_breakdowns(db, org, teacher):
    it, ada, bola = await _seed(db, org)
    rep = await store_sales_summary(start=None, end=None, db=db, current_user=teacher)
    assert rep.total_sales == 3
    assert rep.total_revenue == 600.0
    assert rep.average_sale == 200.0
    # by payment
    pay = {g.key: g for g in rep.by_payment}
    assert pay["cash"].count == 2 and pay["cash"].revenue == 300.0
    assert pay["transfer"].count == 1 and pay["transfer"].revenue == 300.0
    # by cashier (names resolved)
    cash = {g.label: g for g in rep.by_cashier}
    assert cash["Ada Cashier"].count == 2 and cash["Ada Cashier"].revenue == 300.0
    assert cash["Bola Cashier"].count == 1
    # top items (aggregated across sales)
    assert rep.top_items[0].item_name == "Exercise Book"
    assert rep.top_items[0].quantity == 6.0 and rep.top_items[0].revenue == 600.0


async def test_void_excluded(db, org, teacher):
    it = await _item(db, org, "Pen", qty=50, price=100)
    ada = await _user(db, org, "Ada")
    sale = await create_store_sale(StoreSaleCreate(lines=[StoreSaleLineInput(item_id=it.id, quantity=5)]), request=None, db=db, current_user=ada)
    await void_store_sale(sale.id, request=None, db=db, current_user=ada)
    rep = await store_sales_summary(start=None, end=None, db=db, current_user=teacher)
    assert rep.total_sales == 0 and rep.total_revenue == 0.0    # voided sale not counted


async def test_period_scoping(db, org, teacher):
    await _seed(db, org)
    # "Today" is the org's LOCAL calendar day (what the Sales Monitor sends) — not
    # the test machine's date, which would make this timezone-dependent/flaky.
    today = datetime.now(ZoneInfo(org.timezone or "Africa/Lagos")).date()
    inc = await store_sales_summary(start=today, end=today, db=db, current_user=teacher)
    assert inc.total_sales == 3                                # sales are 'now'
    past = await store_sales_summary(start=date(2020, 1, 1), end=date(2020, 12, 31), db=db, current_user=teacher)
    assert past.total_sales == 0 and past.top_items == []      # window excludes them


async def test_local_day_window_uses_org_timezone(db, org, teacher):
    # org tz = Africa/Lagos (UTC+1): local day 2026-07-09 spans, in UTC,
    # [2026-07-08 23:00:00, 2026-07-09 22:59:59]. Deterministic (fixed created_at).
    it = await _item(db, org, "Book", qty=100, price=100)
    ada = await _user(db, org, "Ada")
    in_sale = await create_store_sale(StoreSaleCreate(payment_method="cash", lines=[StoreSaleLineInput(item_id=it.id, quantity=1)]), request=None, db=db, current_user=ada)   # revenue 100
    out_sale = await create_store_sale(StoreSaleCreate(payment_method="cash", lines=[StoreSaleLineInput(item_id=it.id, quantity=2)]), request=None, db=db, current_user=ada)  # revenue 200
    # in-window: 07-08 23:30 UTC = 07-09 00:30 Lagos (local 07-09)
    # out-of-window: 07-09 23:30 UTC = 07-10 00:30 Lagos (local 07-10)
    for sid, dt in ((in_sale.id, datetime(2026, 7, 8, 23, 30)), (out_sale.id, datetime(2026, 7, 9, 23, 30))):
        row = (await db.execute(select(StoreSale).where(StoreSale.id == sid))).scalar_one()
        row.created_at = dt
    await db.commit()

    rep = await store_sales_summary(start=date(2026, 7, 9), end=date(2026, 7, 9), db=db, current_user=teacher)
    # Only the sale whose LOCAL day is 07-09 counts. The pre-fix UTC window would
    # have excluded in_sale (07-08 UTC) and wrongly included out_sale (07-09 UTC).
    assert rep.total_sales == 1 and rep.total_revenue == 100.0


async def test_end_before_start_rejected(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await store_sales_summary(start=date(2026, 3, 31), end=date(2026, 1, 1), db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_empty_summary(db, org, teacher):
    rep = await store_sales_summary(start=None, end=None, db=db, current_user=teacher)
    assert rep.total_sales == 0 and rep.total_revenue == 0.0 and rep.average_sale == 0.0
    assert rep.top_items == [] and rep.by_payment == [] and rep.by_cashier == []


async def test_sales_monitor_rbac(db, org):
    # Read-only analytics gated payments:WRITE (store revenue) — parents excluded.
    manager = await _preset_user(db, org, "manager")
    assert manager.has_permission("payments:write")
    parent = await _preset_user(db, org, "parent")
    assert parent.has_permission("payments:read") and not parent.has_permission("payments:write")
    for slug in ("teacher", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("payments:write")
