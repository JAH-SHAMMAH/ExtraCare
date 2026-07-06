"""The double-entry ledger engine — the ONLY path that writes JournalEntry rows.

Every money-moving feature (invoices, payroll, petty cash, cash, store) posts
through `post_journal_entry`, so the five money-safety properties are enforced in
exactly one place:

  • Double-entry integrity — rejects unless Σdebits == Σcredits, ≥2 lines, each
    line exactly one-sided, and every account exists/active in-org.
  • Immutable postings — entries are created `posted`; never edited/deleted.
    Corrections go through `reverse_entry` (a mirror entry; original is linked + flagged).
  • Period lock — refuses to post (or back-date) into a locked AccountingPeriod.
  • Audit — every post/reverse writes an immutable AuditLog with before→after.
  • Atomicity — header + all lines are flushed together inside the caller's
    request transaction (get_db commits all-or-nothing).
"""
from __future__ import annotations

from datetime import date as date_type, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Sequence

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.modules.finance import LedgerAccount, AccountingPeriod, JournalEntry, JournalLine
from app.models.user import User
from app.services.audit_service import log_action
from app.models.audit import AuditAction

CENT = Decimal("0.01")


def money(v) -> Decimal:
    """Normalise any numeric input to 2-dp Decimal (never trust float maths)."""
    return Decimal(str(v if v is not None else 0)).quantize(CENT, rounding=ROUND_HALF_UP)


async def _period_for(db: AsyncSession, org_id: str, d: date_type) -> Optional[AccountingPeriod]:
    return (await db.execute(
        select(AccountingPeriod).where(
            AccountingPeriod.org_id == org_id,
            AccountingPeriod.start_date <= d,
            AccountingPeriod.end_date >= d,
        ).limit(1)
    )).scalar_one_or_none()


async def post_journal_entry(
    db: AsyncSession,
    *,
    org_id: str,
    entry_date: date_type,
    memo: Optional[str],
    source: str,
    source_id: Optional[str],
    lines: Sequence[dict],
    actor: Optional[User],
    request=None,
) -> JournalEntry:
    """Validate-all-then-write a balanced, posted entry. Raises 422 on any
    integrity failure and 409 if the target period is locked — so an unbalanced
    or back-dated-into-a-closed-period entry can never persist."""
    if len(lines) < 2:
        raise HTTPException(status_code=422, detail="A journal entry needs at least two lines.")

    total_debit = Decimal("0")
    total_credit = Decimal("0")
    account_ids: set[str] = set()
    norm: list[tuple[str, Decimal, Decimal, Optional[str]]] = []
    for ln in lines:
        debit = money(ln.get("debit"))
        credit = money(ln.get("credit"))
        if debit < 0 or credit < 0:
            raise HTTPException(status_code=422, detail="Ledger amounts cannot be negative.")
        if (debit > 0) == (credit > 0):  # both zero, or both positive
            raise HTTPException(status_code=422, detail="Each line must be exactly one of debit or credit.")
        if not ln.get("account_id"):
            raise HTTPException(status_code=422, detail="Each line must reference an account.")
        account_ids.add(ln["account_id"])
        total_debit += debit
        total_credit += credit
        norm.append((ln["account_id"], debit, credit, ln.get("description")))

    if total_debit != total_credit:
        raise HTTPException(
            status_code=422,
            detail=f"Entry does not balance: debits {total_debit} ≠ credits {total_credit}.",
        )

    found = set((await db.execute(
        select(LedgerAccount.id).where(
            LedgerAccount.org_id == org_id,
            LedgerAccount.id.in_(account_ids),
            LedgerAccount.is_active == True,   # noqa: E712
            LedgerAccount.is_deleted == False,  # noqa: E712
        )
    )).scalars().all())
    missing = account_ids - found
    if missing:
        raise HTTPException(status_code=422, detail=f"Unknown or inactive account(s): {sorted(missing)}")

    period = await _period_for(db, org_id, entry_date)
    if period and period.status == "locked":
        raise HTTPException(
            status_code=409,
            detail=f"Accounting period '{period.name}' is locked — cannot post on {entry_date}.",
        )

    now = datetime.now(timezone.utc)
    entry = JournalEntry(
        org_id=org_id, entry_date=entry_date, memo=memo, source=source, source_id=source_id,
        status="posted", period_id=period.id if period else None,
        posted_by=actor.id if actor else None, posted_at=now,
    )
    db.add(entry)
    await db.flush()
    for account_id, debit, credit, desc in norm:
        db.add(JournalLine(
            org_id=org_id, entry_id=entry.id, account_id=account_id,
            debit=debit, credit=credit, description=desc,
        ))
    await db.flush()

    await log_action(
        db, AuditAction.RECORD_CREATED, org_id, actor=actor,
        resource_type="JournalEntry", resource_id=entry.id,
        resource_label=f"posted {source} journal entry",
        new_values={"status": "posted", "total": str(total_debit)},
        metadata={"source": source, "source_id": source_id, "lines": len(norm)},
        severity="warning", request=request,
    )
    return entry


async def reverse_entry(
    db: AsyncSession,
    *,
    entry_id: str,
    org_id: str,
    actor: Optional[User],
    request=None,
    reversal_date: Optional[date_type] = None,
) -> JournalEntry:
    """Correct a posted entry by creating its mirror (debits↔credits). The
    original is never mutated beyond linking it to its reversal."""
    original = (await db.execute(
        select(JournalEntry).where(JournalEntry.id == entry_id, JournalEntry.org_id == org_id)
    )).scalar_one_or_none()
    if not original:
        raise HTTPException(status_code=404, detail="Journal entry not found.")
    if original.reversed_by_id:
        raise HTTPException(status_code=409, detail="This entry has already been reversed.")
    if original.source == "reversal":
        raise HTTPException(status_code=409, detail="A reversing entry cannot itself be reversed.")

    lines = (await db.execute(
        select(JournalLine).where(JournalLine.entry_id == original.id)
    )).scalars().all()

    rdate = reversal_date or datetime.now(timezone.utc).date()
    period = await _period_for(db, org_id, rdate)
    if period and period.status == "locked":
        raise HTTPException(
            status_code=409,
            detail=f"Accounting period '{period.name}' is locked — cannot post a reversal on {rdate}.",
        )

    now = datetime.now(timezone.utc)
    rev = JournalEntry(
        org_id=org_id, entry_date=rdate, memo=f"Reversal of entry {original.id}",
        source="reversal", source_id=original.source_id, status="posted",
        period_id=period.id if period else None,
        posted_by=actor.id if actor else None, posted_at=now, reversal_of_id=original.id,
    )
    db.add(rev)
    await db.flush()
    for ln in lines:
        db.add(JournalLine(
            org_id=org_id, entry_id=rev.id, account_id=ln.account_id,
            debit=ln.credit, credit=ln.debit,  # mirror
            description=f"Reversal: {ln.description or ''}".strip(),
        ))
    original.reversed_by_id = rev.id
    original.reversed_at = now
    await db.flush()

    await log_action(
        db, AuditAction.RECORD_UPDATED, org_id, actor=actor,
        resource_type="JournalEntry", resource_id=original.id, resource_label="reversed journal entry",
        old_values={"reversed": False}, new_values={"reversed": True, "reversed_by": rev.id},
        severity="warning", request=request,
    )
    return rev
