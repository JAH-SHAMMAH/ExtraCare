"""Tests for Student Wallet / PocketMoney + Cooperative (Batch 6 money features).

The asserts the user asked for:
  • a `wallet:spend` holder CAN record a spend but CANNOT top-up / withdraw /
    post an invoice or payroll (the capability is self-limiting);
  • the no-overdraw HARD block holds (incl. for the spend path);
  • GL ↔ subledger reconciliation ties out after a mix of top-ups and spends;
  • the spend path inherits the period-lock guard.
Plus the daily PocketMoney limit and cooperative liability postings.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.finance import LedgerAccount, AccountingPeriod
from app.routers.modules.wallet import (
    create_wallet, update_wallet, topup_wallet, withdraw_wallet, spend_wallet,
    wallet_reconciliation,
    create_member, contribute, payout, coop_reconciliation,
)
from app.schemas.wallet import (
    WalletCreate, WalletUpdate, TopUpRequest, WithdrawRequest, SpendRequest,
    CoopMemberCreate, CoopMoveRequest,
)


pytestmark = pytest.mark.asyncio


async def _acct(db, org, code, name, type_) -> LedgerAccount:
    a = LedgerAccount(id=str(uuid.uuid4()), code=code, name=name, type=type_, org_id=org.id, is_active=True)
    db.add(a)
    await db.commit()
    return a


async def _user(db, org, perms: list[str]) -> User:
    u = User(id=str(uuid.uuid4()), email=f"u-{uuid.uuid4().hex[:6]}@example.com", full_name="U",
             status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="r", slug=f"r-{uuid.uuid4().hex[:6]}", permissions=list(perms), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


# ── The dedicated wallet:spend capability is self-limiting ───────────────────────

async def test_wallet_spend_scope_is_constrained(db, org):
    """A till user with ONLY wallet:spend can spend — but holds none of the
    cash-moving / ledger-posting powers."""
    till = await _user(db, org, ["wallet:spend"])
    assert till.has_permission("wallet:spend")
    assert not till.has_permission("payments:post")    # cannot top-up / withdraw / coop / cash
    assert not till.has_permission("payments:write")   # cannot create invoices / payroll drafts
    assert not till.has_permission("school:write")
    # And the preset till role (staff) carries it for real:
    staff_perms = SCHOOL_PERMISSION_PRESETS["staff"]
    assert "wallet:spend" in staff_perms
    assert "payments:post" not in staff_perms


async def test_till_can_spend_but_balance_guards_hold(db, org, student):
    admin = await _user(db, org, ["payments:read", "payments:write", "payments:post", "wallet:spend"])
    till = await _user(db, org, ["wallet:spend"])
    cash = await _acct(db, org, "1000", "Cash", "asset")
    income = await _acct(db, org, "4000", "Tuckshop Sales", "income")
    w = await create_wallet(WalletCreate(student_id=student.id), db=db, current_user=admin)
    # Fund it (admin / payments:post path).
    await topup_wallet(w.id, TopUpRequest(amount=100, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    # Till spends within balance.
    after = await spend_wallet(w.id, SpendRequest(amount=30, income_account_id=income.id), request=None, db=db, current_user=till)
    assert after.balance == 70.0
    # No-overdraw HARD block — even though the till "could", it can't overspend.
    with pytest.raises(HTTPException) as exc:
        await spend_wallet(w.id, SpendRequest(amount=999, income_account_id=income.id), request=None, db=db, current_user=till)
    assert exc.value.status_code == 422


async def test_spend_requires_income_account(db, org, student):
    admin = await _user(db, org, ["payments:post", "wallet:spend"])
    cash = await _acct(db, org, "1000", "Cash", "asset")
    w = await create_wallet(WalletCreate(student_id=student.id), db=db, current_user=admin)
    await topup_wallet(w.id, TopUpRequest(amount=50, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    # Spending to a non-income account is refused — the path can only recognise income.
    with pytest.raises(HTTPException) as exc:
        await spend_wallet(w.id, SpendRequest(amount=10, income_account_id=cash.id), request=None, db=db, current_user=admin)
    assert exc.value.status_code == 422


# ── PocketMoney daily spend limit ────────────────────────────────────────────────

async def test_daily_spend_limit_blocks(db, org, student):
    admin = await _user(db, org, ["payments:post", "wallet:spend"])
    cash = await _acct(db, org, "1000", "Cash", "asset")
    income = await _acct(db, org, "4000", "Tuckshop", "income")
    w = await create_wallet(WalletCreate(student_id=student.id, spend_limit_daily=20), db=db, current_user=admin)
    await topup_wallet(w.id, TopUpRequest(amount=100, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    d = date(2026, 5, 1)
    await spend_wallet(w.id, SpendRequest(amount=15, income_account_id=income.id, txn_date=d), request=None, db=db, current_user=admin)
    with pytest.raises(HTTPException) as exc:   # 15 + 10 > 20
        await spend_wallet(w.id, SpendRequest(amount=10, income_account_id=income.id, txn_date=d), request=None, db=db, current_user=admin)
    assert exc.value.status_code == 422


# ── Reconciliation: GL liability ↔ derived subledger ─────────────────────────────

async def test_wallet_reconciliation_ties_out(db, org, student):
    admin = await _user(db, org, ["payments:read", "payments:post", "wallet:spend"])
    cash = await _acct(db, org, "1000", "Cash", "asset")
    income = await _acct(db, org, "4000", "Tuckshop", "income")
    # Two students, a mix of top-ups + spends.
    from app.models.modules.school import Student
    s2 = Student(id=str(uuid.uuid4()), student_id="S-900", first_name="Bee", last_name="Two", org_id=org.id)
    db.add(s2)
    await db.commit()
    w1 = await create_wallet(WalletCreate(student_id=student.id), db=db, current_user=admin)
    w2 = await create_wallet(WalletCreate(student_id=s2.id), db=db, current_user=admin)
    await topup_wallet(w1.id, TopUpRequest(amount=100, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    await topup_wallet(w2.id, TopUpRequest(amount=50, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    await spend_wallet(w1.id, SpendRequest(amount=30, income_account_id=income.id), request=None, db=db, current_user=admin)
    # Float liability should now hold 120 (100+50-30), == Σ wallet balances (70 + 50).
    rec = await wallet_reconciliation(db=db, current_user=admin)
    assert rec.gl_balance == 120.0
    assert rec.subledger_total == 120.0
    assert rec.balanced is True


async def test_withdraw_overdraw_blocked(db, org, student):
    admin = await _user(db, org, ["payments:post"])
    cash = await _acct(db, org, "1000", "Cash", "asset")
    w = await create_wallet(WalletCreate(student_id=student.id), db=db, current_user=admin)
    await topup_wallet(w.id, TopUpRequest(amount=40, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    with pytest.raises(HTTPException) as exc:
        await withdraw_wallet(w.id, WithdrawRequest(amount=100, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    assert exc.value.status_code == 422


# ── Period-lock inheritance on the spend path ────────────────────────────────────

async def test_spend_into_locked_period_rejected(db, org, student):
    admin = await _user(db, org, ["payments:post", "wallet:spend"])
    cash = await _acct(db, org, "1000", "Cash", "asset")
    income = await _acct(db, org, "4000", "Tuckshop", "income")
    w = await create_wallet(WalletCreate(student_id=student.id), db=db, current_user=admin)
    await topup_wallet(w.id, TopUpRequest(amount=100, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    db.add(AccountingPeriod(id=str(uuid.uuid4()), name="Locked", start_date=date(2026, 1, 1), end_date=date(2026, 3, 31), status="locked", org_id=org.id))
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await spend_wallet(w.id, SpendRequest(amount=10, income_account_id=income.id, txn_date=date(2026, 2, 10)), request=None, db=db, current_user=admin)
    assert exc.value.status_code == 409


# ── Cooperative (liability, not income) ──────────────────────────────────────────

async def test_cooperative_contribute_payout_and_reconcile(db, org):
    admin = await _user(db, org, ["payments:read", "payments:post"])
    cash = await _acct(db, org, "1000", "Cash", "asset")
    m = await create_member(CoopMemberCreate(member_name="Mrs Coop"), db=db, current_user=admin)
    after_c = await contribute(m.id, CoopMoveRequest(amount=200, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    assert after_c.balance == 200.0
    after_p = await payout(m.id, CoopMoveRequest(amount=80, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    assert after_p.balance == 120.0
    # Overdraw blocked.
    with pytest.raises(HTTPException) as exc:
        await payout(m.id, CoopMoveRequest(amount=999, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    assert exc.value.status_code == 422
    rec = await coop_reconciliation(db=db, current_user=admin)
    assert rec.gl_balance == 120.0 and rec.subledger_total == 120.0 and rec.balanced is True
