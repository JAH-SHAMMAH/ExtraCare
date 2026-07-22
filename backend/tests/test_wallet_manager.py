"""Tests for the Wallet Manager surface (own-section resurfacing of the ledger
wallet): the dashboard summary roll-up, the WalletSettings singleton + its
default-limit / allow-topup effects, and the parent-centric fields (guardian +
class) now carried on every wallet response.

The money core (postings, no-overdraw, reconciliation) is covered by test_wallet.py;
here we only assert the Wallet Manager additions.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role
from app.models.modules.finance import LedgerAccount
from app.models.modules.school import Student
from app.routers.modules.wallet import (
    create_wallet, topup_wallet, spend_wallet,
    wallet_summary, get_wallet_settings, update_wallet_settings,
)
from app.schemas.wallet import WalletCreate, TopUpRequest, SpendRequest, WalletSettingsUpdate


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


async def _extra_student(db, org, sid="S-950") -> Student:
    s = Student(id=str(uuid.uuid4()), student_id=sid, first_name="Bee", last_name="Two", org_id=org.id)
    db.add(s)
    await db.commit()
    return s


# ── Dashboard summary roll-up ────────────────────────────────────────────────────

async def test_wallet_summary_rollup(db, org, student):
    admin = await _user(db, org, ["payments:read", "payments:write", "payments:post", "wallet:spend"])
    cash = await _acct(db, org, "1000", "Cash", "asset")
    income = await _acct(db, org, "4000", "Tuckshop", "income")
    s2 = await _extra_student(db, org)
    w1 = await create_wallet(WalletCreate(student_id=student.id), db=db, current_user=admin)
    w2 = await create_wallet(WalletCreate(student_id=s2.id), db=db, current_user=admin)
    await topup_wallet(w1.id, TopUpRequest(amount=100, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    await topup_wallet(w2.id, TopUpRequest(amount=50, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    await spend_wallet(w1.id, SpendRequest(amount=30, income_account_id=income.id), request=None, db=db, current_user=admin)

    summ = await wallet_summary(db=db, current_user=admin)
    assert summ.total_wallets == 2
    assert summ.active_wallets == 2
    assert summ.inactive_wallets == 0
    assert summ.total_topped_up == 150.0   # 100 + 50
    assert summ.total_spent == 30.0        # reported positive
    assert summ.total_balance == 120.0     # 150 topped − 30 spent


async def test_summary_empty_org_is_zeroed(db, org):
    admin = await _user(db, org, ["payments:read"])
    summ = await wallet_summary(db=db, current_user=admin)
    assert summ.total_wallets == 0
    assert summ.total_balance == 0.0 and summ.total_topped_up == 0.0 and summ.total_spent == 0.0


# ── Settings singleton + effects ─────────────────────────────────────────────────

async def test_wallet_settings_singleton_and_update(db, org):
    admin = await _user(db, org, ["payments:read", "payments:write"])
    s = await get_wallet_settings(db=db, current_user=admin)
    assert s.default_daily_limit is None and s.notify_low_balance is False and s.allow_topup is True

    upd = await update_wallet_settings(
        WalletSettingsUpdate(default_daily_limit=25, low_balance_threshold=5, notify_low_balance=True, allow_topup=False),
        db=db, current_user=admin,
    )
    assert upd.default_daily_limit == 25.0 and upd.low_balance_threshold == 5.0
    assert upd.notify_low_balance is True and upd.allow_topup is False
    # Re-fetch reflects the update and remains a single row (no duplicate created).
    again = await get_wallet_settings(db=db, current_user=admin)
    assert again.default_daily_limit == 25.0 and again.allow_topup is False


async def test_create_wallet_applies_default_daily_limit(db, org, student):
    admin = await _user(db, org, ["payments:write"])
    await update_wallet_settings(WalletSettingsUpdate(default_daily_limit=25), db=db, current_user=admin)
    # No explicit limit → inherits the org default.
    w = await create_wallet(WalletCreate(student_id=student.id), db=db, current_user=admin)
    assert w.spend_limit_daily == 25.0
    # Explicit limit wins over the default.
    s2 = await _extra_student(db, org)
    w2 = await create_wallet(WalletCreate(student_id=s2.id, spend_limit_daily=10), db=db, current_user=admin)
    assert w2.spend_limit_daily == 10.0


async def test_allow_topup_false_blocks_topup(db, org, student):
    admin = await _user(db, org, ["payments:write", "payments:post"])
    cash = await _acct(db, org, "1000", "Cash", "asset")
    w = await create_wallet(WalletCreate(student_id=student.id), db=db, current_user=admin)
    await update_wallet_settings(WalletSettingsUpdate(allow_topup=False), db=db, current_user=admin)
    with pytest.raises(HTTPException) as exc:
        await topup_wallet(w.id, TopUpRequest(amount=50, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    assert exc.value.status_code == 409


# ── Parent-centric fields on the wallet response ─────────────────────────────────

async def test_wallet_response_carries_guardian_and_class(db, org, student):
    admin = await _user(db, org, ["payments:write"])
    student.guardian_name = "Mrs Okafor"
    student.guardian_phone = "+234800000000"
    db.add(student)
    await db.commit()
    w = await create_wallet(WalletCreate(student_id=student.id), db=db, current_user=admin)
    assert w.student_name == "Ada Okafor"
    assert w.guardian_name == "Mrs Okafor"
    assert w.guardian_phone == "+234800000000"
    assert w.class_name == "Year 10A"   # from the student fixture's class
