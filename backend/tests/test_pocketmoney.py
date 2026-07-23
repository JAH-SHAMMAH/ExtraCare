"""Tests for PocketMoney Manager — the item catalogue + itemised New Transaction.

New Transaction records a SPEND against the student's existing StudentWallet
(reusing the ledger-backed spend path), so the money guarantees (no-overdraw,
daily limit) are inherited. Here we assert the catalogue CRUD, that a purchase
debits the wallet by the item total, and the transactions list.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role
from app.models.modules.finance import LedgerAccount
from app.routers.modules.wallet import (
    create_wallet, topup_wallet,
    list_pocketmoney_items, create_pocketmoney_item, update_pocketmoney_item, delete_pocketmoney_item,
    list_pocketmoney_transactions, create_pocketmoney_transaction, list_pocketmoney_students,
)
from app.schemas.wallet import (
    WalletCreate, TopUpRequest,
    PocketMoneyItemCreate, PocketMoneyItemUpdate,
    PocketMoneyTxnCreate, PocketMoneyTxnLine,
)


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
                permissions=["payments:read", "payments:write", "payments:post", "wallet:spend"], org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


# ── Item catalogue CRUD ──────────────────────────────────────────────────────────

async def test_item_crud(db, org):
    admin = await _admin(db, org)
    created = await create_pocketmoney_item(PocketMoneyItemCreate(name="Meat Pie", unit_price=250), db=db, current_user=admin)
    assert created.name == "Meat Pie" and created.unit_price == 250.0 and created.is_active is True

    listing = await list_pocketmoney_items(active_only=False, db=db, current_user=admin)
    assert len(listing) == 1

    upd = await update_pocketmoney_item(created.id, PocketMoneyItemUpdate(unit_price=300, is_active=False), db=db, current_user=admin)
    assert upd.unit_price == 300.0 and upd.is_active is False
    # active_only filter hides the deactivated item.
    assert len(await list_pocketmoney_items(active_only=True, db=db, current_user=admin)) == 0

    await delete_pocketmoney_item(created.id, db=db, current_user=admin)
    assert len(await list_pocketmoney_items(active_only=False, db=db, current_user=admin)) == 0


# ── New Transaction records a spend ──────────────────────────────────────────────

async def test_itemised_transaction_debits_wallet(db, org, student):
    admin = await _admin(db, org)
    cash = await _acct(db, org, "1000", "Cash", "asset")
    income = await _acct(db, org, "4000", "Canteen", "income")
    w = await create_wallet(WalletCreate(student_id=student.id), db=db, current_user=admin)
    await topup_wallet(w.id, TopUpRequest(amount=1000, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    pie = await create_pocketmoney_item(PocketMoneyItemCreate(name="Meat Pie", unit_price=250), db=db, current_user=admin)
    juice = await create_pocketmoney_item(PocketMoneyItemCreate(name="Juice", unit_price=150), db=db, current_user=admin)

    txn = await create_pocketmoney_transaction(
        PocketMoneyTxnCreate(wallet_id=w.id, income_account_id=income.id,
                             lines=[PocketMoneyTxnLine(item_id=pie.id, qty=2), PocketMoneyTxnLine(item_id=juice.id, qty=1)]),
        request=None, db=db, current_user=admin,
    )
    assert txn.amount == 650.0   # 250*2 + 150
    assert "Meat Pie x2" in txn.memo and "Juice x1" in txn.memo

    listing = await list_pocketmoney_transactions(page=1, page_size=50, db=db, current_user=admin)
    assert listing.total == 1
    assert listing.items[0].amount == 650.0 and listing.items[0].student_name == "Ada Okafor"


async def test_direct_amount_transaction(db, org, student):
    admin = await _admin(db, org)
    cash = await _acct(db, org, "1000", "Cash", "asset")
    income = await _acct(db, org, "4000", "Canteen", "income")
    w = await create_wallet(WalletCreate(student_id=student.id), db=db, current_user=admin)
    await topup_wallet(w.id, TopUpRequest(amount=500, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    txn = await create_pocketmoney_transaction(
        PocketMoneyTxnCreate(wallet_id=w.id, income_account_id=income.id, amount=120, memo="Snacks"),
        request=None, db=db, current_user=admin,
    )
    assert txn.amount == 120.0 and txn.memo == "Snacks"


async def test_transaction_no_overdraw(db, org, student):
    admin = await _admin(db, org)
    cash = await _acct(db, org, "1000", "Cash", "asset")
    income = await _acct(db, org, "4000", "Canteen", "income")
    w = await create_wallet(WalletCreate(student_id=student.id), db=db, current_user=admin)
    await topup_wallet(w.id, TopUpRequest(amount=100, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    with pytest.raises(HTTPException) as exc:
        await create_pocketmoney_transaction(
            PocketMoneyTxnCreate(wallet_id=w.id, income_account_id=income.id, amount=999),
            request=None, db=db, current_user=admin,
        )
    assert exc.value.status_code == 422


async def test_empty_transaction_rejected(db, org, student):
    admin = await _admin(db, org)
    income = await _acct(db, org, "4000", "Canteen", "income")
    w = await create_wallet(WalletCreate(student_id=student.id), db=db, current_user=admin)
    with pytest.raises(HTTPException) as exc:   # no lines, no amount
        await create_pocketmoney_transaction(
            PocketMoneyTxnCreate(wallet_id=w.id, income_account_id=income.id),
            request=None, db=db, current_user=admin,
        )
    assert exc.value.status_code == 422


async def test_transaction_requires_a_target(db, org):
    admin = await _admin(db, org)
    income = await _acct(db, org, "4000", "Canteen", "income")
    with pytest.raises(HTTPException) as exc:   # neither student_id nor wallet_id
        await create_pocketmoney_transaction(
            PocketMoneyTxnCreate(income_account_id=income.id, amount=10),
            request=None, db=db, current_user=admin,
        )
    assert exc.value.status_code == 422


async def test_transaction_by_student_id(db, org, student):
    admin = await _admin(db, org)
    cash = await _acct(db, org, "1000", "Cash", "asset")
    income = await _acct(db, org, "4000", "Canteen", "income")
    w = await create_wallet(WalletCreate(student_id=student.id), db=db, current_user=admin)
    await topup_wallet(w.id, TopUpRequest(amount=200, cash_account_id=cash.id), request=None, db=db, current_user=admin)
    # Target the STUDENT (not the wallet id) — resolves to the existing wallet.
    txn = await create_pocketmoney_transaction(
        PocketMoneyTxnCreate(student_id=student.id, income_account_id=income.id, amount=50),
        request=None, db=db, current_user=admin,
    )
    assert txn.amount == 50.0 and txn.student_name == "Ada Okafor"


# ── POCKET MONEY STUDENT LIST ────────────────────────────────────────────────────

async def test_student_list_shows_parent_class_balance(db, org, student):
    admin = await _admin(db, org)
    cash = await _acct(db, org, "1000", "Cash", "asset")
    student.guardian_name = "MR & MRS OKAFOR"
    db.add(student)
    await db.commit()
    w = await create_wallet(WalletCreate(student_id=student.id), db=db, current_user=admin)
    await topup_wallet(w.id, TopUpRequest(amount=300, cash_account_id=cash.id), request=None, db=db, current_user=admin)

    res = await list_pocketmoney_students(page=1, page_size=50, search=None, db=db, current_user=admin)
    assert res.total == 1
    row = res.items[0]
    assert row.student_name == "Ada Okafor"
    assert row.parent_name == "MR & MRS OKAFOR"
    assert row.class_name == "Year 10A"     # from the student fixture's class
    assert row.balance == 300.0
    assert row.wallet_id == w.id


async def test_student_list_search_and_no_wallet_zero_balance(db, org, student):
    admin = await _admin(db, org)
    # student has no wallet → balance 0, wallet_id None, still listed.
    res = await list_pocketmoney_students(page=1, page_size=50, search="Ada", db=db, current_user=admin)
    assert res.total == 1 and res.items[0].balance == 0.0 and res.items[0].wallet_id is None
    # A non-matching search returns nothing.
    empty = await list_pocketmoney_students(page=1, page_size=50, search="Zzz", db=db, current_user=admin)
    assert empty.total == 0
