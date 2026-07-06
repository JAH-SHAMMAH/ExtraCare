"""Tests for Finance: period-scoped Budget Management.

Budgets carry an optional [start_date, end_date] window. 'spent' is measured from
the ledger — non-reversed debits to the account — scoped to that window when set,
else all-time (backward-compatible with date-less budgets). These prove:
  • in-window spend counts; out-of-window spend does NOT (true per-period variance)
  • remaining = amount − spent (negative = over budget)
  • a date-less budget falls back to all-time spend
  • reversed entries are excluded
  • update (PATCH) changes amount/window and re-scopes spent
  • end-before-start is rejected (422); RBAC
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.finance import LedgerAccount
from app.services import ledger
from app.routers.modules.finance_ops import (
    create_budget, update_budget, list_budgets, delete_budget,
)
from app.schemas.finance_ops import BudgetCreate, BudgetUpdate


pytestmark = pytest.mark.asyncio


async def _acct(db, org, code, name, type_) -> LedgerAccount:
    a = LedgerAccount(id=str(uuid.uuid4()), code=code, name=name, type=type_, org_id=org.id, is_active=True)
    db.add(a)
    await db.commit()
    return a


async def _spend(db, org, exp, cash, amount, on: date, actor):
    """Post a balanced Dr expense / Cr cash entry dated `on`."""
    return await ledger.post_journal_entry(
        db, org_id=org.id, entry_date=on, memo="spend", source="manual", source_id=None,
        lines=[{"account_id": exp.id, "debit": amount, "credit": 0},
               {"account_id": cash.id, "debit": 0, "credit": amount}],
        actor=actor,
    )


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


def _only(budgets, account_id):
    return next(b for b in budgets if b.account_id == account_id)


# ── Period scoping ────────────────────────────────────────────────────────────

async def test_spent_scoped_to_window(db, org, teacher):
    exp = await _acct(db, org, "5200", "Supplies", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    await create_budget(
        BudgetCreate(account_id=exp.id, period_label="2026 Q1", amount=100000,
                     start_date=date(2026, 1, 1), end_date=date(2026, 3, 31)),
        db=db, current_user=teacher,
    )
    await _spend(db, org, exp, cash, 40000, date(2026, 2, 15), teacher)   # inside window
    await _spend(db, org, exp, cash, 30000, date(2026, 5, 1), teacher)    # outside window
    b = _only(await list_budgets(db=db, current_user=teacher), exp.id)
    assert b.spent == 40000.0            # only the in-window spend
    assert b.remaining == 60000.0        # 100000 − 40000


async def test_boundary_dates_inclusive(db, org, teacher):
    exp = await _acct(db, org, "5200", "Supplies", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    await create_budget(
        BudgetCreate(account_id=exp.id, amount=100000, start_date=date(2026, 1, 1), end_date=date(2026, 3, 31)),
        db=db, current_user=teacher,
    )
    await _spend(db, org, exp, cash, 1000, date(2026, 1, 1), teacher)     # start boundary
    await _spend(db, org, exp, cash, 2000, date(2026, 3, 31), teacher)    # end boundary
    await _spend(db, org, exp, cash, 5000, date(2025, 12, 31), teacher)   # day before window
    b = _only(await list_budgets(db=db, current_user=teacher), exp.id)
    assert b.spent == 3000.0             # both boundaries in, the day-before out


async def test_dateless_budget_is_all_time(db, org, teacher):
    exp = await _acct(db, org, "5200", "Supplies", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    await create_budget(BudgetCreate(account_id=exp.id, amount=50000), db=db, current_user=teacher)  # no dates
    await _spend(db, org, exp, cash, 20000, date(2026, 2, 15), teacher)
    await _spend(db, org, exp, cash, 15000, date(2026, 9, 1), teacher)
    b = _only(await list_budgets(db=db, current_user=teacher), exp.id)
    assert b.spent == 35000.0            # all-time, no window filter


async def test_over_budget_negative_remaining(db, org, teacher):
    exp = await _acct(db, org, "5200", "Supplies", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    await create_budget(
        BudgetCreate(account_id=exp.id, amount=10000, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31)),
        db=db, current_user=teacher,
    )
    await _spend(db, org, exp, cash, 13500, date(2026, 6, 1), teacher)
    b = _only(await list_budgets(db=db, current_user=teacher), exp.id)
    assert b.spent == 13500.0
    assert b.remaining == -3500.0        # over budget


async def test_reversed_spend_excluded(db, org, teacher):
    exp = await _acct(db, org, "5200", "Supplies", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    await create_budget(
        BudgetCreate(account_id=exp.id, amount=100000, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31)),
        db=db, current_user=teacher,
    )
    entry = await _spend(db, org, exp, cash, 25000, date(2026, 3, 1), teacher)
    await ledger.reverse_entry(db, entry_id=entry.id, org_id=org.id, actor=teacher)
    b = _only(await list_budgets(db=db, current_user=teacher), exp.id)
    assert b.spent == 0.0                # the reversed spend no longer counts


# ── Update / validation ───────────────────────────────────────────────────────

async def test_update_amount_and_window_rescopes(db, org, teacher):
    exp = await _acct(db, org, "5200", "Supplies", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    created = await create_budget(
        BudgetCreate(account_id=exp.id, amount=100000, start_date=date(2026, 1, 1), end_date=date(2026, 3, 31)),
        db=db, current_user=teacher,
    )
    await _spend(db, org, exp, cash, 40000, date(2026, 2, 15), teacher)   # Q1
    await _spend(db, org, exp, cash, 30000, date(2026, 5, 15), teacher)   # Q2
    # Move the window to Q2 and bump the amount.
    updated = await update_budget(
        created.id, BudgetUpdate(amount=50000, start_date=date(2026, 4, 1), end_date=date(2026, 6, 30)),
        db=db, current_user=teacher,
    )
    assert updated.amount == 50000.0
    assert updated.spent == 30000.0      # now counts Q2 spend only
    assert updated.remaining == 20000.0


async def test_end_before_start_rejected(db, org, teacher):
    exp = await _acct(db, org, "5200", "Supplies", "expense")
    with pytest.raises(HTTPException) as exc:
        await create_budget(
            BudgetCreate(account_id=exp.id, amount=1000, start_date=date(2026, 3, 31), end_date=date(2026, 1, 1)),
            db=db, current_user=teacher,
        )
    assert exc.value.status_code == 422


async def test_update_end_before_start_rejected(db, org, teacher):
    exp = await _acct(db, org, "5200", "Supplies", "expense")
    created = await create_budget(
        BudgetCreate(account_id=exp.id, amount=1000, start_date=date(2026, 1, 1), end_date=date(2026, 6, 30)),
        db=db, current_user=teacher,
    )
    with pytest.raises(HTTPException) as exc:
        await update_budget(created.id, BudgetUpdate(end_date=date(2025, 12, 31)), db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_create_unknown_account_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_budget(BudgetCreate(account_id="nope", amount=1000), db=db, current_user=teacher)
    assert exc.value.status_code == 404


async def test_delete_budget(db, org, teacher):
    exp = await _acct(db, org, "5200", "Supplies", "expense")
    created = await create_budget(BudgetCreate(account_id=exp.id, amount=1000), db=db, current_user=teacher)
    await delete_budget(created.id, db=db, current_user=teacher)
    assert all(b.id != created.id for b in await list_budgets(db=db, current_user=teacher))
    with pytest.raises(HTTPException) as exc:
        await update_budget(created.id, BudgetUpdate(amount=2000), db=db, current_user=teacher)
    assert exc.value.status_code == 404


# ── RBAC ──────────────────────────────────────────────────────────────────────

async def test_budget_rbac(db, org):
    # Set/edit budgets = payments:write; view = payments:read (post NOT required).
    manager = await _preset_user(db, org, "manager")
    assert manager.has_permission("payments:write") and manager.has_permission("payments:read")
    for slug in ("teacher", "parent", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("payments:write")
