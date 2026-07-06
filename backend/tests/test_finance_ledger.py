"""Tests for the double-entry ledger engine (Batch 5).

The money-safety properties live in `app.services.ledger`, so these tests drive
it directly: balance integrity, one-sided lines, min-2-lines, account validation,
period-lock (incl. back-dating), immutable reversal, and atomicity (a rejected
post writes nothing).
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import select, func

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.finance import LedgerAccount, AccountingPeriod, JournalEntry, JournalLine
from app.services import ledger


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


async def _count_entries(db, org) -> int:
    return (await db.execute(
        select(func.count()).select_from(JournalEntry).where(JournalEntry.org_id == org.id)
    )).scalar() or 0


# ── Double-entry integrity ─────────────────────────────────────────────────────

async def test_balanced_entry_posts(db, org, teacher):
    cash = await _acct(db, org, "1000", "Cash", "asset")
    income = await _acct(db, org, "4000", "Fees", "income")
    entry = await ledger.post_journal_entry(
        db, org_id=org.id, entry_date=date(2026, 2, 1), memo="fees", source="manual", source_id=None,
        lines=[{"account_id": cash.id, "debit": 100, "credit": 0},
               {"account_id": income.id, "debit": 0, "credit": 100}],
        actor=teacher,
    )
    assert entry.status == "posted"
    lines = (await db.execute(select(JournalLine).where(JournalLine.entry_id == entry.id))).scalars().all()
    assert len(lines) == 2
    assert sum(float(l.debit) for l in lines) == sum(float(l.credit) for l in lines) == 100.0


async def test_unbalanced_entry_rejected_and_nothing_persists(db, org, teacher):
    cash = await _acct(db, org, "1000", "Cash", "asset")
    income = await _acct(db, org, "4000", "Fees", "income")
    with pytest.raises(HTTPException) as exc:
        await ledger.post_journal_entry(
            db, org_id=org.id, entry_date=date(2026, 2, 1), memo="bad", source="manual", source_id=None,
            lines=[{"account_id": cash.id, "debit": 100, "credit": 0},
                   {"account_id": income.id, "debit": 0, "credit": 90}],
            actor=teacher,
        )
    assert exc.value.status_code == 422
    assert await _count_entries(db, org) == 0   # atomicity: nothing half-written


async def test_line_must_be_one_sided(db, org, teacher):
    cash = await _acct(db, org, "1000", "Cash", "asset")
    income = await _acct(db, org, "4000", "Fees", "income")
    with pytest.raises(HTTPException) as exc:
        await ledger.post_journal_entry(
            db, org_id=org.id, entry_date=date(2026, 2, 1), memo="x", source="manual", source_id=None,
            lines=[{"account_id": cash.id, "debit": 50, "credit": 50},
                   {"account_id": income.id, "debit": 0, "credit": 0}],
            actor=teacher,
        )
    assert exc.value.status_code == 422


async def test_minimum_two_lines(db, org, teacher):
    cash = await _acct(db, org, "1000", "Cash", "asset")
    with pytest.raises(HTTPException) as exc:
        await ledger.post_journal_entry(
            db, org_id=org.id, entry_date=date(2026, 2, 1), memo="x", source="manual", source_id=None,
            lines=[{"account_id": cash.id, "debit": 50, "credit": 0}], actor=teacher,
        )
    assert exc.value.status_code == 422


async def test_unknown_account_rejected(db, org, teacher):
    cash = await _acct(db, org, "1000", "Cash", "asset")
    with pytest.raises(HTTPException) as exc:
        await ledger.post_journal_entry(
            db, org_id=org.id, entry_date=date(2026, 2, 1), memo="x", source="manual", source_id=None,
            lines=[{"account_id": cash.id, "debit": 50, "credit": 0},
                   {"account_id": "ghost", "debit": 0, "credit": 50}], actor=teacher,
        )
    assert exc.value.status_code == 422


# ── Period lock (protects against back-dating into closed books) ────────────────

async def test_locked_period_blocks_posting(db, org, teacher):
    cash = await _acct(db, org, "1000", "Cash", "asset")
    income = await _acct(db, org, "4000", "Fees", "income")
    period = AccountingPeriod(id=str(uuid.uuid4()), name="2025/2026 T1", start_date=date(2026, 1, 1),
                              end_date=date(2026, 3, 31), status="locked", org_id=org.id)
    db.add(period)
    await db.commit()
    # A back-dated entry into the locked term must be refused.
    with pytest.raises(HTTPException) as exc:
        await ledger.post_journal_entry(
            db, org_id=org.id, entry_date=date(2026, 2, 15), memo="late", source="manual", source_id=None,
            lines=[{"account_id": cash.id, "debit": 10, "credit": 0},
                   {"account_id": income.id, "debit": 0, "credit": 10}], actor=teacher,
        )
    assert exc.value.status_code == 409
    assert await _count_entries(db, org) == 0


async def test_open_period_is_attached(db, org, teacher):
    cash = await _acct(db, org, "1000", "Cash", "asset")
    income = await _acct(db, org, "4000", "Fees", "income")
    period = AccountingPeriod(id=str(uuid.uuid4()), name="Open term", start_date=date(2026, 1, 1),
                              end_date=date(2026, 3, 31), status="open", org_id=org.id)
    db.add(period)
    await db.commit()
    entry = await ledger.post_journal_entry(
        db, org_id=org.id, entry_date=date(2026, 2, 15), memo="ok", source="manual", source_id=None,
        lines=[{"account_id": cash.id, "debit": 10, "credit": 0},
               {"account_id": income.id, "debit": 0, "credit": 10}], actor=teacher,
    )
    assert entry.period_id == period.id


# ── Immutable reversal ─────────────────────────────────────────────────────────

async def test_reverse_creates_mirror_and_locks_original(db, org, teacher):
    cash = await _acct(db, org, "1000", "Cash", "asset")
    income = await _acct(db, org, "4000", "Fees", "income")
    entry = await ledger.post_journal_entry(
        db, org_id=org.id, entry_date=date(2026, 2, 1), memo="orig", source="manual", source_id=None,
        lines=[{"account_id": cash.id, "debit": 100, "credit": 0},
               {"account_id": income.id, "debit": 0, "credit": 100}], actor=teacher,
    )
    rev = await ledger.reverse_entry(db, entry_id=entry.id, org_id=org.id, actor=teacher)
    assert rev.reversal_of_id == entry.id
    # mirror: original debit→credit
    rev_lines = (await db.execute(select(JournalLine).where(JournalLine.entry_id == rev.id))).scalars().all()
    cash_line = next(l for l in rev_lines if l.account_id == cash.id)
    assert float(cash_line.credit) == 100.0 and float(cash_line.debit) == 0.0
    # original is flagged + cannot be reversed twice
    refreshed = (await db.execute(select(JournalEntry).where(JournalEntry.id == entry.id))).scalar_one()
    assert refreshed.reversed_by_id == rev.id
    with pytest.raises(HTTPException) as exc:
        await ledger.reverse_entry(db, entry_id=entry.id, org_id=org.id, actor=teacher)
    assert exc.value.status_code == 409


# ── RBAC scopes (segregation of duties) ────────────────────────────────────────

async def test_finance_rbac_scopes(db, org):
    admin = await _preset_user(db, org, "org_admin")
    assert admin.has_permission("payments:write") and admin.has_permission("payments:post")
    accountant = await _preset_user(db, org, "accountant")
    assert accountant.has_permission("payments:write") and accountant.has_permission("payments:post")
    assert not accountant.has_permission("school:read")   # finance-only, like the nurse
    manager = await _preset_user(db, org, "manager")
    assert manager.has_permission("payments:write")
    assert not manager.has_permission("payments:post")    # manager drafts but cannot post
    for slug in ("teacher", "staff", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("payments:write")
        assert not u.has_permission("payments:post")


# ── Financial Statements (NEW endpoint) — prove the derived maths ────────────────

async def test_financial_statements_derive_correctly(db, org):
    from app.routers.modules.finance import financial_statements
    accountant = await _preset_user(db, org, "accountant")
    cash = await _acct(db, org, "1000", "Cash", "asset")
    fees = await _acct(db, org, "4000", "Fees", "income")
    salary = await _acct(db, org, "5000", "Salaries", "expense")
    # Recognise 100 income (Dr Cash / Cr Fees), then spend 30 (Dr Salary / Cr Cash).
    await ledger.post_journal_entry(
        db, org_id=org.id, entry_date=date(2026, 2, 1), memo="fees", source="manual", source_id=None,
        lines=[{"account_id": cash.id, "debit": 100, "credit": 0}, {"account_id": fees.id, "debit": 0, "credit": 100}],
        actor=accountant,
    )
    await ledger.post_journal_entry(
        db, org_id=org.id, entry_date=date(2026, 2, 2), memo="salary", source="manual", source_id=None,
        lines=[{"account_id": salary.id, "debit": 30, "credit": 0}, {"account_id": cash.id, "debit": 0, "credit": 30}],
        actor=accountant,
    )
    await db.commit()

    s = await financial_statements(as_of=None, db=db, current_user=accountant)
    # Trial balance balances (Σdebit == Σcredit): cash dr 100 + salary dr 30 = 130; fees cr 100 + cash cr 30 = 130.
    assert s.total_debit == s.total_credit == 130.0 and s.balanced is True
    # Income statement
    assert s.income == 100.0 and s.expense == 30.0 and s.net_income == 70.0
    # Balance sheet: cash 100−30 = 70 assets; no liabilities/equity; assets == L + E + net income.
    assert s.assets == 70.0 and s.liabilities == 0.0 and s.equity == 0.0
    assert s.balance_sheet_balanced is True
    # An account with no activity is excluded from the trial balance rows.
    assert all(r.code in {"1000", "4000", "5000"} for r in s.trial_balance)


async def test_financial_statements_empty_when_no_postings(db, org):
    from app.routers.modules.finance import financial_statements
    accountant = await _preset_user(db, org, "accountant")
    await _acct(db, org, "1000", "Cash", "asset")   # account exists but no entries
    s = await financial_statements(as_of=None, db=db, current_user=accountant)
    assert s.trial_balance == [] and s.total_debit == 0.0 and s.net_income == 0.0 and s.balanced is True
