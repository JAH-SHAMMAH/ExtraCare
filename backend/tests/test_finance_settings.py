"""Tests for Finance: Accounts Setup (per-org default posting accounts)."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.finance import LedgerAccount, OrgFinanceSettings
from app.routers.modules.finance import get_finance_settings, update_finance_settings
from app.schemas.finance import FinanceSettingsUpdate


pytestmark = pytest.mark.asyncio


async def _acct(db, org, code, name, type_) -> LedgerAccount:
    a = LedgerAccount(id=str(uuid.uuid4()), code=code, name=name, type=type_, org_id=org.id, is_active=True)
    db.add(a)
    await db.commit()
    return a


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


async def test_get_blank_when_unset(db, org, teacher):
    r = await get_finance_settings(db=db, current_user=teacher)
    assert r.default_cash_account_id is None and r.default_income_account_id is None
    assert r.org_id == org.id


async def test_put_sets_defaults_with_names(db, org, teacher):
    cash = await _acct(db, org, "1000", "Cash", "asset")
    fees = await _acct(db, org, "4000", "Fees", "income")
    exp = await _acct(db, org, "5000", "Expenses", "expense")
    r = await update_finance_settings(
        FinanceSettingsUpdate(default_cash_account_id=cash.id, default_income_account_id=fees.id, default_expense_account_id=exp.id),
        request=None, db=db, current_user=teacher,
    )
    assert r.default_cash_account_id == cash.id and r.default_cash_account_name == "Cash"
    assert r.default_income_account_id == fees.id and r.default_income_account_name == "Fees"
    assert r.default_expense_account_id == exp.id
    # persisted + readable via GET
    g = await get_finance_settings(db=db, current_user=teacher)
    assert g.default_cash_account_id == cash.id


async def test_wrong_type_rejected(db, org, teacher):
    fees = await _acct(db, org, "4000", "Fees", "income")
    with pytest.raises(HTTPException) as exc:
        # cash default must be an asset; passing an income account is invalid
        await update_finance_settings(FinanceSettingsUpdate(default_cash_account_id=fees.id),
                                      request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_unknown_account_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await update_finance_settings(FinanceSettingsUpdate(default_cash_account_id="nope"),
                                      request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 404


async def test_partial_update_and_clear(db, org, teacher):
    cash = await _acct(db, org, "1000", "Cash", "asset")
    fees = await _acct(db, org, "4000", "Fees", "income")
    await update_finance_settings(FinanceSettingsUpdate(default_cash_account_id=cash.id, default_income_account_id=fees.id),
                                  request=None, db=db, current_user=teacher)
    # partial: touch only income (leave cash); explicit null clears income
    r = await update_finance_settings(FinanceSettingsUpdate(default_income_account_id=None),
                                      request=None, db=db, current_user=teacher)
    assert r.default_cash_account_id == cash.id       # untouched
    assert r.default_income_account_id is None         # cleared


async def test_upsert_single_row(db, org, teacher):
    cash = await _acct(db, org, "1000", "Cash", "asset")
    await update_finance_settings(FinanceSettingsUpdate(default_cash_account_id=cash.id), request=None, db=db, current_user=teacher)
    await update_finance_settings(FinanceSettingsUpdate(default_cash_account_id=cash.id), request=None, db=db, current_user=teacher)
    rows = (await db.execute(select(OrgFinanceSettings).where(OrgFinanceSettings.org_id == org.id))).scalars().all()
    assert len(rows) == 1                              # one settings row per org


async def test_settings_rbac(db, org):
    manager = await _preset_user(db, org, "manager")
    assert manager.has_permission("payments:write")
    for slug in ("teacher", "parent", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("payments:write")
