"""Tests for Finance: period Income & Expense report (read-only over the ledger).

Proves the report is period-scoped and agrees with the /statements sign
convention, and that the by-source breakdown attributes income/expense to the
feature that posted it:
  • income = Σ(credit−debit) on income accounts within the window
  • expense = Σ(debit−credit) on expense accounts within the window
  • out-of-window entries are excluded; net = income − expense
  • by_account and by_source breakdowns are correct
  • end-before-start → 422; RBAC (read-only view)
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.finance import LedgerAccount
from app.services import ledger
from app.routers.modules.finance import income_expense_report


pytestmark = pytest.mark.asyncio


async def _acct(db, org, code, name, type_) -> LedgerAccount:
    a = LedgerAccount(id=str(uuid.uuid4()), code=code, name=name, type=type_, org_id=org.id, is_active=True)
    db.add(a)
    await db.commit()
    return a


async def _post(db, org, lines, on, source, actor):
    return await ledger.post_journal_entry(
        db, org_id=org.id, entry_date=on, memo=source, source=source, source_id=None,
        lines=lines, actor=actor,
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


async def _seed(db, org, teacher):
    """Fees income + two expenses in-window, one expense out-of-window."""
    fees = await _acct(db, org, "4000", "Fees", "income")
    supplies = await _acct(db, org, "5200", "Supplies", "expense")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    # in-window
    await _post(db, org, [{"account_id": cash.id, "debit": 100000, "credit": 0},
                          {"account_id": fees.id, "debit": 0, "credit": 100000}], date(2026, 2, 1), "invoice", teacher)
    await _post(db, org, [{"account_id": supplies.id, "debit": 40000, "credit": 0},
                          {"account_id": cash.id, "debit": 0, "credit": 40000}], date(2026, 2, 15), "payroll", teacher)
    await _post(db, org, [{"account_id": supplies.id, "debit": 10000, "credit": 0},
                          {"account_id": cash.id, "debit": 0, "credit": 10000}], date(2026, 2, 20), "requisition", teacher)
    # out-of-window
    await _post(db, org, [{"account_id": supplies.id, "debit": 30000, "credit": 0},
                          {"account_id": cash.id, "debit": 0, "credit": 30000}], date(2026, 5, 1), "payroll", teacher)
    return fees, supplies, cash


async def test_period_totals_scoped(db, org, teacher):
    await _seed(db, org, teacher)
    rep = await income_expense_report(start=date(2026, 1, 1), end=date(2026, 3, 31), db=db, current_user=teacher)
    assert rep.income == 100000.0
    assert rep.expense == 50000.0          # 40000 + 10000, the out-of-window 30000 excluded
    assert rep.net == 50000.0


async def test_by_account_breakdown(db, org, teacher):
    fees, supplies, _ = await _seed(db, org, teacher)
    rep = await income_expense_report(start=date(2026, 1, 1), end=date(2026, 3, 31), db=db, current_user=teacher)
    by_id = {r.account_id: r for r in rep.by_account}
    assert by_id[fees.id].type == "income" and by_id[fees.id].amount == 100000.0
    assert by_id[supplies.id].type == "expense" and by_id[supplies.id].amount == 50000.0


async def test_by_source_breakdown(db, org, teacher):
    await _seed(db, org, teacher)
    rep = await income_expense_report(start=date(2026, 1, 1), end=date(2026, 3, 31), db=db, current_user=teacher)
    src = {r.source: r for r in rep.by_source}
    assert src["invoice"].income == 100000.0 and src["invoice"].expense == 0.0
    assert src["payroll"].expense == 40000.0    # only the in-window payroll entry
    assert src["requisition"].expense == 10000.0


async def test_full_range_includes_everything(db, org, teacher):
    await _seed(db, org, teacher)
    rep = await income_expense_report(start=None, end=None, db=db, current_user=teacher)
    assert rep.income == 100000.0
    assert rep.expense == 80000.0          # all three expenses, incl. the May one


async def test_end_before_start_rejected(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await income_expense_report(start=date(2026, 3, 31), end=date(2026, 1, 1), db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_empty_report_is_zeroed(db, org, teacher):
    rep = await income_expense_report(start=date(2026, 1, 1), end=date(2026, 3, 31), db=db, current_user=teacher)
    assert rep.income == 0.0 and rep.expense == 0.0 and rep.net == 0.0
    assert rep.by_account == [] and rep.by_source == []


async def test_reports_rbac(db, org):
    # Org-wide financials are gated payments:WRITE (same bar as /statements), NOT
    # payments:read — because parents hold payments:read for their own invoices and
    # must not see the school's whole P&L.
    for slug in ("manager", "accountant"):
        u = await _preset_user(db, org, slug)
        assert u.has_permission("payments:write")
    parent = await _preset_user(db, org, "parent")
    assert parent.has_permission("payments:read")          # parents can read their own invoices…
    assert not parent.has_permission("payments:write")     # …but NOT the school-wide report
    for slug in ("teacher", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("payments:write")
