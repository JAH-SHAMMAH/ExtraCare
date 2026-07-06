"""Tests for Finance ops (Batch 5, second half): Petty Cash & Budget, Cash
Transactions, Store & Inventory.

Per the requirement, each feature EXPLICITLY proves it inherits the shared-engine
guards — it is NOT assumed:
  • petty-cash disbursement into a LOCKED period → 409
  • cash receipt into a LOCKED period → 409
  • the store posting path rejects an UNBALANCED entry → 422
  • every feature posts a BALANCED journal entry
Plus the soft over-budget warning, stock maths, and finance RBAC.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.finance import LedgerAccount, AccountingPeriod, JournalLine, StoreItem
from app.services import ledger
from app.routers.modules.finance_ops import (
    record_petty_cash, void_petty_cash, list_petty_cash, create_budget,
    record_cash, void_cash,
    create_store_item, purchase_stock, adjust_stock,
)
from app.schemas.finance_ops import (
    PettyCashCreate, BudgetCreate, CashTxnCreate, StoreItemCreate, PurchaseCreate, StockAdjustCreate,
)


pytestmark = pytest.mark.asyncio


async def _acct(db, org, code, name, type_) -> LedgerAccount:
    a = LedgerAccount(id=str(uuid.uuid4()), code=code, name=name, type=type_, org_id=org.id, is_active=True)
    db.add(a)
    await db.commit()
    return a


async def _lock_period(db, org, start, end):
    p = AccountingPeriod(id=str(uuid.uuid4()), name="Locked", start_date=start, end_date=end, status="locked", org_id=org.id)
    db.add(p)
    await db.commit()
    return p


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


async def _balanced(db, entry_id) -> bool:
    lines = (await db.execute(select(JournalLine).where(JournalLine.entry_id == entry_id))).scalars().all()
    return len(lines) >= 2 and sum(float(l.debit) for l in lines) == sum(float(l.credit) for l in lines)


# ── Petty Cash ──────────────────────────────────────────────────────────────────

async def test_petty_cash_posts_balanced(db, org, teacher):
    exp = await _acct(db, org, "5100", "Sundry Expense", "expense")
    cash = await _acct(db, org, "1010", "Petty Cash", "asset")
    t = await record_petty_cash(
        PettyCashCreate(amount=25, expense_account_id=exp.id, cash_account_id=cash.id, description="biscuits"),
        request=None, db=db, current_user=teacher,
    )
    assert t.amount == 25.0
    assert t.journal_entry_id is not None
    assert await _balanced(db, t.journal_entry_id)


async def test_petty_cash_into_locked_period_rejected(db, org, teacher):
    exp = await _acct(db, org, "5100", "Sundry", "expense")
    cash = await _acct(db, org, "1010", "Petty Cash", "asset")
    await _lock_period(db, org, date(2026, 1, 1), date(2026, 3, 31))
    with pytest.raises(HTTPException) as exc:
        await record_petty_cash(
            PettyCashCreate(amount=25, expense_account_id=exp.id, cash_account_id=cash.id, txn_date=date(2026, 2, 10)),
            request=None, db=db, current_user=teacher,
        )
    assert exc.value.status_code == 409   # inherited period-lock guard


async def test_petty_cash_soft_budget_warning(db, org, teacher):
    exp = await _acct(db, org, "5100", "Stationery", "expense")
    cash = await _acct(db, org, "1010", "Petty Cash", "asset")
    await create_budget(BudgetCreate(account_id=exp.id, amount=50), db=db, current_user=teacher)
    # Spend over the budget — soft warning, NOT a block (the txn still posts).
    t = await record_petty_cash(
        PettyCashCreate(amount=80, expense_account_id=exp.id, cash_account_id=cash.id),
        request=None, db=db, current_user=teacher,
    )
    assert t.status == "posted"
    assert t.warning is not None and "Over budget" in t.warning


async def test_petty_cash_void_reverses(db, org, teacher):
    exp = await _acct(db, org, "5100", "Sundry", "expense")
    cash = await _acct(db, org, "1010", "Petty Cash", "asset")
    t = await record_petty_cash(PettyCashCreate(amount=10, expense_account_id=exp.id, cash_account_id=cash.id),
                                request=None, db=db, current_user=teacher)
    voided = await void_petty_cash(t.id, request=None, db=db, current_user=teacher)
    assert voided.status == "void"


# ── Cash Transactions ───────────────────────────────────────────────────────────

async def test_cash_receipt_and_payment_post_balanced(db, org, teacher):
    cash = await _acct(db, org, "1000", "Cash", "asset")
    income = await _acct(db, org, "4000", "Donations", "income")
    expense = await _acct(db, org, "5000", "Utilities", "expense")
    r = await record_cash(CashTxnCreate(type="receipt", amount=200, cash_account_id=cash.id, counter_account_id=income.id),
                          request=None, db=db, current_user=teacher)
    assert await _balanced(db, r.journal_entry_id)
    p = await record_cash(CashTxnCreate(type="payment", amount=75, cash_account_id=cash.id, counter_account_id=expense.id),
                          request=None, db=db, current_user=teacher)
    assert await _balanced(db, p.journal_entry_id)


async def test_cash_into_locked_period_rejected(db, org, teacher):
    cash = await _acct(db, org, "1000", "Cash", "asset")
    income = await _acct(db, org, "4000", "Donations", "income")
    await _lock_period(db, org, date(2026, 1, 1), date(2026, 3, 31))
    with pytest.raises(HTTPException) as exc:
        await record_cash(
            CashTxnCreate(type="receipt", amount=200, cash_account_id=cash.id, counter_account_id=income.id, txn_date=date(2026, 2, 10)),
            request=None, db=db, current_user=teacher,
        )
    assert exc.value.status_code == 409   # inherited period-lock guard


async def test_cash_void_reverses(db, org, teacher):
    cash = await _acct(db, org, "1000", "Cash", "asset")
    income = await _acct(db, org, "4000", "Donations", "income")
    r = await record_cash(CashTxnCreate(type="receipt", amount=50, cash_account_id=cash.id, counter_account_id=income.id),
                          request=None, db=db, current_user=teacher)
    voided = await void_cash(r.id, request=None, db=db, current_user=teacher)
    assert voided.status == "void"


# ── Store & Inventory ───────────────────────────────────────────────────────────

async def test_purchase_posts_balanced_and_increments_stock(db, org, teacher):
    inv = await _acct(db, org, "1200", "Inventory", "asset")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    item = await create_store_item(StoreItemCreate(name="Exercise Book", unit_price=2), db=db, current_user=teacher)
    updated = await purchase_stock(
        item.id, PurchaseCreate(quantity=100, unit_cost="1.50", inventory_account_id=inv.id, funding_account_id=cash.id),
        request=None, db=db, current_user=teacher,
    )
    assert updated.quantity == 100.0
    # The purchase posted a balanced Dr Inventory / Cr Cash of 150.00.
    je = (await db.execute(select(JournalLine).where(JournalLine.account_id == inv.id))).scalars().all()
    assert float(je[0].debit) == 150.0
    # verify the entry itself balances
    entry_id = je[0].entry_id
    assert await _balanced(db, entry_id)


async def test_purchase_into_locked_period_rejected(db, org, teacher):
    inv = await _acct(db, org, "1200", "Inventory", "asset")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    item = await create_store_item(StoreItemCreate(name="Pen"), db=db, current_user=teacher)
    await _lock_period(db, org, date(2026, 1, 1), date(2026, 3, 31))
    with pytest.raises(HTTPException) as exc:
        await purchase_stock(
            item.id, PurchaseCreate(quantity=10, unit_cost=1, inventory_account_id=inv.id, funding_account_id=cash.id, purchase_date=date(2026, 2, 10)),
            request=None, db=db, current_user=teacher,
        )
    assert exc.value.status_code == 409   # inherited period-lock guard


async def test_store_posting_path_rejects_unbalanced(db, org, teacher):
    """The inventory purchase posts via post_journal_entry(source='store'); prove
    that path refuses an unbalanced entry (an unbalanced purchase can't post)."""
    inv = await _acct(db, org, "1200", "Inventory", "asset")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    with pytest.raises(HTTPException) as exc:
        await ledger.post_journal_entry(
            db, org_id=org.id, entry_date=date(2026, 5, 1), memo="bad purchase", source="store", source_id=None,
            lines=[{"account_id": inv.id, "debit": 150, "credit": 0},
                   {"account_id": cash.id, "debit": 0, "credit": 120}],  # 150 ≠ 120
            actor=teacher,
        )
    assert exc.value.status_code == 422


async def test_stock_out_and_adjust(db, org, teacher):
    inv = await _acct(db, org, "1200", "Inventory", "asset")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    item = await create_store_item(StoreItemCreate(name="Ruler"), db=db, current_user=teacher)
    await purchase_stock(item.id, PurchaseCreate(quantity=20, unit_cost=1, inventory_account_id=inv.id, funding_account_id=cash.id),
                         request=None, db=db, current_user=teacher)
    out = await adjust_stock(item.id, StockAdjustCreate(type="out", quantity=5), db=db, current_user=teacher)
    assert out.quantity == 15.0
    # can't go negative
    with pytest.raises(HTTPException) as exc:
        await adjust_stock(item.id, StockAdjustCreate(type="out", quantity=999), db=db, current_user=teacher)
    assert exc.value.status_code == 422
    # adjust sets an absolute count
    fixed = await adjust_stock(item.id, StockAdjustCreate(type="adjust", quantity=12), db=db, current_user=teacher)
    assert fixed.quantity == 12.0


# ── RBAC (SoD) ──────────────────────────────────────────────────────────────────

async def test_finance_ops_rbac(db, org):
    # Recording cash/petty-cash/purchases posts to the ledger → payments:post.
    # Budgets + store-item setup + stock adjust → payments:write.
    manager = await _preset_user(db, org, "manager")
    assert manager.has_permission("payments:write")
    assert not manager.has_permission("payments:post")   # manager can set budgets/items but not post cash
    accountant = await _preset_user(db, org, "accountant")
    assert accountant.has_permission("payments:write") and accountant.has_permission("payments:post")
    for slug in ("teacher", "parent", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("payments:write")
        assert not u.has_permission("payments:post")
