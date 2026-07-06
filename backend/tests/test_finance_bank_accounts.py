"""Tests for Finance: Account Numbers (the school's own bank accounts).

Reference data (where fees are received) shown on invoices/receipts. Managed by
finance (payments:write). These prove:
  • the first account created is auto-primary; only ONE account is primary at a time
  • creating/updating/set-primary re-points the single primary correctly
  • soft delete; RBAC (payments:write; parents excluded)
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.finance import BankAccount
from app.routers.modules.finance import (
    create_bank_account, update_bank_account, set_primary_bank_account,
    delete_bank_account, list_bank_accounts, primary_bank_account,
)
from app.schemas.finance import BankAccountCreate, BankAccountUpdate


pytestmark = pytest.mark.asyncio


def _payload(bank="GTBank", num="0123456789", primary=False):
    return BankAccountCreate(bank_name=bank, account_name="Fairview School", account_number=num, is_primary=primary)


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


async def _primary_count(db, org) -> int:
    rows = (await db.execute(
        select(BankAccount).where(
            BankAccount.org_id == org.id, BankAccount.is_primary == True,  # noqa: E712
            BankAccount.is_deleted == False)  # noqa: E712
    )).scalars().all()
    return len(rows)


# ── Primary management ────────────────────────────────────────────────────────

async def test_first_account_is_auto_primary(db, org, teacher):
    b = await create_bank_account(_payload(), request=None, db=db, current_user=teacher)
    assert b.is_primary is True


async def test_only_one_primary_at_a_time(db, org, teacher):
    a = await create_bank_account(_payload("GTBank", "111"), request=None, db=db, current_user=teacher)
    assert a.is_primary is True
    # second, explicitly primary → steals primary from the first
    b = await create_bank_account(_payload("Access", "222", primary=True), request=None, db=db, current_user=teacher)
    assert b.is_primary is True
    assert await _primary_count(db, org) == 1
    reloaded_a = (await db.execute(select(BankAccount).where(BankAccount.id == a.id))).scalar_one()
    assert reloaded_a.is_primary is False


async def test_second_non_primary_stays_non_primary(db, org, teacher):
    await create_bank_account(_payload("GTBank", "111"), request=None, db=db, current_user=teacher)
    b = await create_bank_account(_payload("Access", "222", primary=False), request=None, db=db, current_user=teacher)
    assert b.is_primary is False
    assert await _primary_count(db, org) == 1


async def test_set_primary_repoints(db, org, teacher):
    a = await create_bank_account(_payload("GTBank", "111"), request=None, db=db, current_user=teacher)
    b = await create_bank_account(_payload("Access", "222"), request=None, db=db, current_user=teacher)
    assert a.is_primary and not b.is_primary
    switched = await set_primary_bank_account(b.id, request=None, db=db, current_user=teacher)
    assert switched.is_primary is True
    assert await _primary_count(db, org) == 1
    ra = (await db.execute(select(BankAccount).where(BankAccount.id == a.id))).scalar_one()
    assert ra.is_primary is False


async def test_update_to_primary_repoints(db, org, teacher):
    a = await create_bank_account(_payload("GTBank", "111"), request=None, db=db, current_user=teacher)
    b = await create_bank_account(_payload("Access", "222"), request=None, db=db, current_user=teacher)
    await update_bank_account(b.id, BankAccountUpdate(is_primary=True, purpose="Fees"),
                              request=None, db=db, current_user=teacher)
    assert await _primary_count(db, org) == 1
    ra = (await db.execute(select(BankAccount).where(BankAccount.id == a.id))).scalar_one()
    assert ra.is_primary is False


async def test_list_ordered_primary_first(db, org, teacher):
    await create_bank_account(_payload("GTBank", "111"), request=None, db=db, current_user=teacher)
    b = await create_bank_account(_payload("Access", "222"), request=None, db=db, current_user=teacher)
    await set_primary_bank_account(b.id, request=None, db=db, current_user=teacher)
    listed = await list_bank_accounts(db=db, current_user=teacher)
    assert listed[0].id == b.id and listed[0].is_primary is True


async def test_delete_soft(db, org, teacher):
    b = await create_bank_account(_payload(), request=None, db=db, current_user=teacher)
    await delete_bank_account(b.id, db=db, current_user=teacher)
    assert all(x.id != b.id for x in await list_bank_accounts(db=db, current_user=teacher))
    with pytest.raises(HTTPException) as exc:
        await update_bank_account(b.id, BankAccountUpdate(purpose="X"), request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 404


# ── Parent 'pay to' (public primary) ──────────────────────────────────────────

async def test_primary_public_endpoint(db, org, teacher):
    # none yet
    assert await primary_bank_account(db=db, current_user=teacher) is None
    a = await create_bank_account(_payload("GTBank", "111"), request=None, db=db, current_user=teacher)
    pub = await primary_bank_account(db=db, current_user=teacher)
    assert pub is not None and pub.bank_name == "GTBank" and pub.account_number == "111"
    # it exposes only the public subset — no internal fields on the model
    assert not hasattr(pub, "notes") and not hasattr(pub, "is_active") and not hasattr(pub, "org_id")
    # re-point primary → the public endpoint follows
    b = await create_bank_account(_payload("Access", "222"), request=None, db=db, current_user=teacher)
    await set_primary_bank_account(b.id, request=None, db=db, current_user=teacher)
    pub2 = await primary_bank_account(db=db, current_user=teacher)
    assert pub2.account_number == "222"


async def test_inactive_primary_not_returned(db, org, teacher):
    a = await create_bank_account(_payload("GTBank", "111"), request=None, db=db, current_user=teacher)
    await update_bank_account(a.id, BankAccountUpdate(is_active=False), request=None, db=db, current_user=teacher)
    assert await primary_bank_account(db=db, current_user=teacher) is None   # inactive → not shown to payers


# ── RBAC ──────────────────────────────────────────────────────────────────────

async def test_bank_account_rbac(db, org):
    # Managing bank accounts = payments:write. Parents hold payments:read — enough to
    # SEE the 'pay to' primary (GET /bank-accounts/primary) but NOT to manage accounts.
    manager = await _preset_user(db, org, "manager")
    assert manager.has_permission("payments:write")
    parent = await _preset_user(db, org, "parent")
    assert parent.has_permission("payments:read")          # can read the primary 'pay to'…
    assert not parent.has_permission("payments:write")     # …but NOT manage the account list
    for slug in ("teacher", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("payments:write")
