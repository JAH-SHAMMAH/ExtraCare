"""Tests for the parent (family) Wallet Manager.

Covers the non-gateway surface: initialize-for-all-parents, the parent-centric
list (profile + children + credit/debit/balance), Add Credit + manual debit with
no-overdraw, the dashboard summary, settings singleton, and org isolation. DVA /
gateway features are out of scope (deferred to Payment Gateways).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role
from app.models.organization import Organization, IndustryType
from app.models.modules.finance import LedgerAccount
from app.models.modules.school import Student, ParentGuardian
from app.routers.modules.parent_wallet import (
    list_parent_wallets, create_parent_wallet, initialize_parent_wallets,
    parent_wallet_summary, get_parent_wallet, credit_parent_wallet, debit_parent_wallet,
    get_parent_wallet_settings, update_parent_wallet_settings,
)
from app.schemas.wallet import ParentCreditRequest, ParentDebitRequest, ParentWalletSettingsUpdate


pytestmark = pytest.mark.asyncio


async def _acct(db, org, code, name, type_) -> LedgerAccount:
    a = LedgerAccount(id=str(uuid.uuid4()), code=code, name=name, type=type_, org_id=org.id, is_active=True)
    db.add(a)
    await db.commit()
    return a


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@example.com", full_name="Admin",
             status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="r", slug=f"r-{uuid.uuid4().hex[:6]}",
                permissions=["payments:read", "payments:write", "payments:post"], org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _parent(db, org, name="Mrs Parent", phone="0801") -> User:
    u = User(id=str(uuid.uuid4()), email=f"p-{uuid.uuid4().hex[:6]}@example.com", full_name=name,
             phone=phone, status=UserStatus.ACTIVE, org_id=org.id)
    db.add(u)
    await db.commit()
    return u


async def _child(db, org, parent: User, first="Kid", last="One", sid=None) -> Student:
    s = Student(id=str(uuid.uuid4()), student_id=sid or f"S-{uuid.uuid4().hex[:5]}",
                first_name=first, last_name=last, org_id=org.id)
    db.add(s)
    await db.flush()
    db.add(ParentGuardian(id=str(uuid.uuid4()), user_id=parent.id, student_id=s.id, is_primary=True, org_id=org.id))
    await db.commit()
    return s


# ── Initialize + list ────────────────────────────────────────────────────────────

async def test_initialize_is_idempotent_and_lists_profile_and_children(db, org):
    admin = await _admin(db, org)
    p1 = await _parent(db, org, name="Mrs Prudence Duro-Bello", phone="8061388881")
    await _child(db, org, p1, "Ethan", "D")
    await _child(db, org, p1, "Ola", "D")
    p2 = await _parent(db, org, name="Mr Faisal Sani")
    await _child(db, org, p2, "Safiya", "S")

    res = await initialize_parent_wallets(db=db, current_user=admin)
    assert res.total_parents == 2 and res.created == 2
    # Idempotent — a second run creates nothing.
    again = await initialize_parent_wallets(db=db, current_user=admin)
    assert again.created == 0

    listing = await list_parent_wallets(page=1, page_size=100, db=db, current_user=admin)
    assert listing.total == 2
    by_name = {w.parent_name: w for w in listing.items}
    prudence = by_name["Mrs Prudence Duro-Bello"]
    assert prudence.parent_phone == "8061388881"
    assert len(prudence.children) == 2
    assert {c.name for c in prudence.children} == {"Ethan D", "Ola D"}
    assert prudence.balance == 0.0 and prudence.credit_total == 0.0 and prudence.debit_total == 0.0


async def test_create_rejects_non_parent_user(db, org):
    admin = await _admin(db, org)
    stranger = await _parent(db, org)   # a user with no children linked
    with pytest.raises(HTTPException) as exc:
        await create_parent_wallet(user_id=stranger.id, db=db, current_user=admin)
    assert exc.value.status_code == 404


# ── Credit / debit + balance ─────────────────────────────────────────────────────

async def test_credit_debit_balance_and_no_overdraw(db, org):
    admin = await _admin(db, org)
    cash = await _acct(db, org, "1000", "Cash", "asset")
    p = await _parent(db, org)
    await _child(db, org, p)
    w = await create_parent_wallet(user_id=p.id, db=db, current_user=admin)

    after_c = await credit_parent_wallet(w.id, ParentCreditRequest(amount=500, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    assert after_c.credit_total == 500.0 and after_c.balance == 500.0

    after_d = await debit_parent_wallet(w.id, ParentDebitRequest(amount=200, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    assert after_d.debit_total == 200.0 and after_d.balance == 300.0

    # No-overdraw hard block.
    with pytest.raises(HTTPException) as exc:
        await debit_parent_wallet(w.id, ParentDebitRequest(amount=999, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    assert exc.value.status_code == 422


async def test_detail_returns_entries(db, org):
    admin = await _admin(db, org)
    cash = await _acct(db, org, "1000", "Cash", "asset")
    p = await _parent(db, org)
    await _child(db, org, p)
    w = await create_parent_wallet(user_id=p.id, db=db, current_user=admin)
    await credit_parent_wallet(w.id, ParentCreditRequest(amount=100, cash_account_id=cash.id, memo="opening"), request=None, db=db, current_user=admin)
    detail = await get_parent_wallet(w.id, db=db, current_user=admin)
    assert len(detail.entries) == 1
    assert detail.entries[0].kind == "credit" and detail.entries[0].signed_amount == 100.0


# ── Dashboard summary ────────────────────────────────────────────────────────────

async def test_summary_rolls_up(db, org):
    admin = await _admin(db, org)
    cash = await _acct(db, org, "1000", "Cash", "asset")
    p = await _parent(db, org)
    await _child(db, org, p)
    w = await create_parent_wallet(user_id=p.id, db=db, current_user=admin)
    await credit_parent_wallet(w.id, ParentCreditRequest(amount=300, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    await debit_parent_wallet(w.id, ParentDebitRequest(amount=120, cash_account_id=cash.id), request=None, db=db, current_user=admin)

    s = await parent_wallet_summary(db=db, current_user=admin)
    assert s.total_credits == 300.0
    assert s.total_debits == 120.0        # reported positive
    assert s.cumulative_balance == 180.0
    assert s.total_active_wallets == 1
    assert s.today_credits == 300.0 and s.today_debits == 120.0   # posted today


# ── Settings singleton ───────────────────────────────────────────────────────────

async def test_settings_singleton_and_update(db, org):
    admin = await _admin(db, org)
    s = await get_parent_wallet_settings(db=db, current_user=admin)
    assert s.auto_invoice_pay is False and s.correspondent_email is None
    upd = await update_parent_wallet_settings(
        ParentWalletSettingsUpdate(auto_invoice_pay=True, correspondent_email="bursar@school.ng"),
        db=db, current_user=admin,
    )
    assert upd.auto_invoice_pay is True and upd.correspondent_email == "bursar@school.ng"
    again = await get_parent_wallet_settings(db=db, current_user=admin)
    assert again.auto_invoice_pay is True and again.correspondent_email == "bursar@school.ng"


# ── Org isolation ────────────────────────────────────────────────────────────────

async def test_org_isolation(db, org):
    admin1 = await _admin(db, org)
    p = await _parent(db, org)
    await _child(db, org, p)
    w = await create_parent_wallet(user_id=p.id, db=db, current_user=admin1)
    # An admin in a different org cannot see it.
    org2 = Organization(id=str(uuid.uuid4()), name="Other School", slug=f"other-{uuid.uuid4().hex[:8]}",
                        industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(org2)
    await db.commit()
    admin2 = await _admin(db, org2)
    listing = await list_parent_wallets(page=1, page_size=100, db=db, current_user=admin2)
    assert listing.total == 0
    with pytest.raises(HTTPException) as exc:
        await get_parent_wallet(w.id, db=db, current_user=admin2)
    assert exc.value.status_code == 404
