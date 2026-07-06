"""Tests for Store Front Desk (POS sales).

A sale reduces stock AND posts revenue to the ledger, so — like stock purchases —
it's a posting action (payments:post). These prove:
  • sale prices lines from the catalog, reduces stock, posts a BALANCED
    Dr Cash / Cr Store Sales income entry (accounts auto-provisioned)
  • discount applies; over-discount / zero-total / oversell are rejected (422)
  • void reverses the ledger AND restores stock
  • RBAC: recording a sale needs payments:post (write-only roles can't)
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.finance import LedgerAccount, JournalEntry, JournalLine, StoreItem, StoreSale
from app.routers.modules.finance_ops import create_store_sale, void_store_sale, list_store_sales
from app.schemas.finance_ops import StoreSaleCreate, StoreSaleLineInput


pytestmark = pytest.mark.asyncio


async def _item(db, org, name, qty, price) -> StoreItem:
    it = StoreItem(id=str(uuid.uuid4()), name=name, unit_price=Decimal(price), cost_price=Decimal(0),
                   quantity=Decimal(qty), reorder_level=Decimal(0), is_active=True, org_id=org.id)
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


async def _reload_item(db, iid) -> StoreItem:
    return (await db.execute(select(StoreItem).where(StoreItem.id == iid))).scalar_one()


async def _balanced(db, entry_id) -> bool:
    lines = (await db.execute(select(JournalLine).where(JournalLine.entry_id == entry_id))).scalars().all()
    return len(lines) >= 2 and sum(float(l.debit) for l in lines) == sum(float(l.credit) for l in lines)


# ── Sale ──────────────────────────────────────────────────────────────────────

async def test_sale_reduces_stock_and_posts_balanced(db, org, teacher):
    it = await _item(db, org, "Exercise Book", qty=10, price=500)
    sale = await create_store_sale(
        StoreSaleCreate(customer_name="Walk-in", lines=[StoreSaleLineInput(item_id=it.id, quantity=3)]),
        request=None, db=db, current_user=teacher,
    )
    assert sale.subtotal == 1500.0 and sale.total == 1500.0 and sale.status == "completed"
    assert sale.lines[0].unit_price == 500.0 and sale.lines[0].amount == 1500.0
    assert (await _reload_item(db, it.id)).quantity == 7            # 10 − 3
    assert await _balanced(db, sale.journal_entry_id)
    # Dr Cash (1000 asset) / Cr Store Sales (4100 income), auto-provisioned.
    cash = (await db.execute(select(LedgerAccount).where(LedgerAccount.org_id == org.id, LedgerAccount.code == "1000"))).scalar_one()
    income = (await db.execute(select(LedgerAccount).where(LedgerAccount.org_id == org.id, LedgerAccount.code == "4100"))).scalar_one()
    assert cash.type == "asset" and income.type == "income"
    lines = (await db.execute(select(JournalLine).where(JournalLine.entry_id == sale.journal_entry_id))).scalars().all()
    assert float(next(l for l in lines if l.account_id == cash.id).debit) == 1500.0
    assert float(next(l for l in lines if l.account_id == income.id).credit) == 1500.0


async def test_sale_with_discount(db, org, teacher):
    it = await _item(db, org, "Pen", qty=100, price=100)
    sale = await create_store_sale(
        StoreSaleCreate(discount=200, lines=[StoreSaleLineInput(item_id=it.id, quantity=10)]),
        request=None, db=db, current_user=teacher,
    )
    assert sale.subtotal == 1000.0 and sale.discount == 200.0 and sale.total == 800.0


async def test_oversell_rejected(db, org, teacher):
    it = await _item(db, org, "Ruler", qty=5, price=100)
    with pytest.raises(HTTPException) as exc:
        await create_store_sale(StoreSaleCreate(lines=[StoreSaleLineInput(item_id=it.id, quantity=6)]),
                                request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422
    assert (await _reload_item(db, it.id)).quantity == 5           # unchanged


async def test_over_discount_and_zero_total_rejected(db, org, teacher):
    it = await _item(db, org, "Eraser", qty=10, price=100)
    with pytest.raises(HTTPException) as exc:
        await create_store_sale(StoreSaleCreate(discount=9999, lines=[StoreSaleLineInput(item_id=it.id, quantity=2)]),
                                request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422
    with pytest.raises(HTTPException) as exc:
        # discount == subtotal → total 0 → rejected
        await create_store_sale(StoreSaleCreate(discount=200, lines=[StoreSaleLineInput(item_id=it.id, quantity=2)]),
                                request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422


# ── Void ──────────────────────────────────────────────────────────────────────

async def test_void_reverses_ledger_and_restores_stock(db, org, teacher):
    it = await _item(db, org, "Book", qty=10, price=500)
    sale = await create_store_sale(StoreSaleCreate(lines=[StoreSaleLineInput(item_id=it.id, quantity=4)]),
                                   request=None, db=db, current_user=teacher)
    assert (await _reload_item(db, it.id)).quantity == 6
    voided = await void_store_sale(sale.id, request=None, db=db, current_user=teacher)
    assert voided.status == "void"
    assert (await _reload_item(db, it.id)).quantity == 10          # restored
    orig = (await db.execute(select(JournalEntry).where(JournalEntry.id == sale.journal_entry_id))).scalar_one()
    assert orig.reversed_by_id is not None


async def test_void_twice_rejected(db, org, teacher):
    it = await _item(db, org, "Book", qty=10, price=500)
    sale = await create_store_sale(StoreSaleCreate(lines=[StoreSaleLineInput(item_id=it.id, quantity=1)]),
                                   request=None, db=db, current_user=teacher)
    await void_store_sale(sale.id, request=None, db=db, current_user=teacher)
    with pytest.raises(HTTPException) as exc:
        await void_store_sale(sale.id, request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 409


# ── RBAC ──────────────────────────────────────────────────────────────────────

async def test_store_sale_rbac(db, org):
    # Recording a sale = the NARROW `store:sell` (Cashier), NOT the broad
    # `payments:post` that also approves payroll/discounts. A cashier can sell but
    # can't post payroll; the broader finance roles can also sell.
    cashier = await _preset_user(db, org, "cashier")
    assert cashier.has_permission("store:sell")
    assert not cashier.has_permission("payments:post")     # can sell, can't post payroll/discounts
    for slug in ("org_admin", "accountant"):                # broader roles keep the till
        u = await _preset_user(db, org, slug)
        assert u.has_permission("store:sell")
    for slug in ("manager", "teacher", "parent", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("store:sell")           # manager unchanged (no till by default)
