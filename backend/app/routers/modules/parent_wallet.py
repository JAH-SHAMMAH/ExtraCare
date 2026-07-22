"""Parent Wallet router (Wallet Manager), prefix ``/finance``.

A parent-level funding wallet keyed by the parent-role User. One wallet per
parent; children are the students linked to that user via ParentGuardian.
Balances are DERIVED from the subledger over non-reversed journal entries — never
stored. The wallet float is a LIABILITY control account (holds the parent's money).

  • credit (Add Credit)  → payments:post  — Dr Cash / Cr Parent Wallet Float
  • debit  (refund/pay)  → payments:post  — Dr Parent Wallet Float / Cr Cash (no-overdraw)
  • initialize / settings → payments:write
  • list / detail / summary → payments:read

DVA / virtual-account funding (Requery, Bulk Requery, virtual account numbers,
BVN, gateway/DVA-bank config) is deferred to the Payment Gateways feature and is
intentionally NOT implemented here.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.tenant import require_module
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.modules.school import Student, SchoolClass, ParentGuardian
from app.models.modules.finance import LedgerAccount, JournalEntry
from app.models.modules.wallet import ParentWallet, ParentWalletEntry, ParentWalletSettings
from app.schemas.wallet import (
    ParentWalletResponse, ParentWalletListResponse, ParentWalletChild,
    ParentWalletEntryResponse, ParentWalletDetailResponse, ParentWalletSummaryResponse,
    ParentWalletSettingsResponse, ParentWalletSettingsUpdate,
    ParentCreditRequest, ParentDebitRequest, ParentWalletInitializeResponse,
)
from app.services import ledger
from app.services.ledger import money

router = APIRouter(
    prefix="/finance",
    tags=["Parent Wallet (Wallet Manager)"],
    dependencies=[Depends(require_module("school"))],
)

_fin_read = Depends(PermissionChecker("payments:read"))
_fin_write = Depends(PermissionChecker("payments:write"))
_fin_post = Depends(PermissionChecker("payments:post"))

PARENT_WALLET_FLOAT_CODE = "2210"
PARENT_WALLET_FLOAT_NAME = "Parent Wallet Float"


# ── helpers ────────────────────────────────────────────────────────────────────

async def _ensure_account(db: AsyncSession, org_id: str, code: str, name: str, type_: str) -> LedgerAccount:
    a = (await db.execute(
        select(LedgerAccount).where(
            LedgerAccount.org_id == org_id, LedgerAccount.code == code, LedgerAccount.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if a:
        return a
    a = LedgerAccount(code=code, name=name, type=type_, is_active=True, org_id=org_id)
    db.add(a)
    await db.flush()
    return a


async def _require_cash(db: AsyncSession, org_id: str, account_id: str) -> LedgerAccount:
    a = (await db.execute(
        select(LedgerAccount).where(
            LedgerAccount.id == account_id, LedgerAccount.org_id == org_id, LedgerAccount.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="account not found in your organisation.")
    return a


async def _parent_children(db: AsyncSession, org_id: str, user_id: str) -> list[ParentWalletChild]:
    rows = (await db.execute(
        select(Student.id, Student.first_name, Student.last_name, SchoolClass.name)
        .select_from(ParentGuardian)
        .join(Student, Student.id == ParentGuardian.student_id)
        .outerjoin(SchoolClass, SchoolClass.id == Student.class_id)
        .where(ParentGuardian.user_id == user_id, ParentGuardian.org_id == org_id)
        .order_by(Student.first_name)
    )).all()
    return [ParentWalletChild(id=r[0], name=f"{r[1]} {r[2]}".strip(), class_name=r[3]) for r in rows]


async def _entry_sum(db: AsyncSession, org_id: str, user_id: str, *conds) -> Decimal:
    total = (await db.execute(
        select(func.coalesce(func.sum(ParentWalletEntry.signed_amount), 0))
        .select_from(ParentWalletEntry).join(JournalEntry, JournalEntry.id == ParentWalletEntry.journal_entry_id)
        .where(ParentWalletEntry.org_id == org_id, ParentWalletEntry.user_id == user_id,
               JournalEntry.reversed_at.is_(None), *conds)
    )).scalar()
    return money(total or 0)


async def _parent_wallet_response(db: AsyncSession, w: ParentWallet, org_id: str) -> ParentWalletResponse:
    u = (await db.execute(select(User.full_name, User.email, User.phone).where(User.id == w.user_id))).first()
    credit = await _entry_sum(db, org_id, w.user_id, ParentWalletEntry.kind == "credit")
    debit = await _entry_sum(db, org_id, w.user_id, ParentWalletEntry.kind == "debit")
    return ParentWalletResponse(
        id=w.id, user_id=w.user_id,
        parent_name=u.full_name if u else None, parent_email=u.email if u else None, parent_phone=u.phone if u else None,
        is_active=w.is_active,
        credit_total=float(credit), debit_total=float(-debit), balance=float(credit + debit),
        children=await _parent_children(db, org_id, w.user_id),
        created_at=w.created_at, org_id=w.org_id,
    )


async def _load_wallet(db: AsyncSession, wid: str, org_id: str) -> ParentWallet:
    w = (await db.execute(select(ParentWallet).where(ParentWallet.id == wid, ParentWallet.org_id == org_id))).scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="Parent wallet not found.")
    return w


async def _post_parent_move(db, current_user, w: ParentWallet, kind: str, amount: Decimal,
                            lines: list[dict], entry_date, memo, request) -> ParentWalletEntry:
    entry = await ledger.post_journal_entry(
        db, org_id=current_user.org_id, entry_date=entry_date, memo=memo or f"Parent wallet {kind}",
        source="parent_wallet", source_id=w.user_id, lines=lines, actor=current_user, request=request,
    )
    signed = amount if kind == "credit" else -amount
    e = ParentWalletEntry(wallet_id=w.id, user_id=w.user_id, kind=kind, signed_amount=signed,
                          journal_entry_id=entry.id, memo=memo, created_by=current_user.id, org_id=current_user.org_id)
    db.add(e)
    await db.flush()
    return e


async def _parent_user_ids(db: AsyncSession, org_id: str) -> list[str]:
    """Distinct parent-role Users in the org — anyone linked to a student as a guardian."""
    return list((await db.execute(
        select(ParentGuardian.user_id).where(ParentGuardian.org_id == org_id).distinct()
    )).scalars().all())


# ── Wallets ─────────────────────────────────────────────────────────────────────

@router.get("/parent-wallets", response_model=ParentWalletListResponse, dependencies=[_fin_read])
async def list_parent_wallets(
    page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    base = select(ParentWallet).where(ParentWallet.org_id == current_user.org_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(base.order_by(ParentWallet.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return ParentWalletListResponse(items=[await _parent_wallet_response(db, w, current_user.org_id) for w in rows],
                                    total=total, page=page, page_size=page_size)


@router.post("/parent-wallets", response_model=ParentWalletResponse, status_code=201, dependencies=[_fin_write])
async def create_parent_wallet(user_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    # The user must be a guardian (parent) in this org.
    is_parent = (await db.execute(
        select(ParentGuardian.id).where(ParentGuardian.user_id == user_id, ParentGuardian.org_id == current_user.org_id).limit(1)
    )).scalar_one_or_none()
    if not is_parent:
        raise HTTPException(status_code=404, detail="No parent/guardian with children found for that user.")
    w = ParentWallet(user_id=user_id, is_active=True, org_id=current_user.org_id)
    db.add(w)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="This parent already has a wallet.")
    return await _parent_wallet_response(db, w, current_user.org_id)


@router.post("/parent-wallets/initialize", response_model=ParentWalletInitializeResponse, dependencies=[_fin_write])
async def initialize_parent_wallets(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Initialize Wallet for all new Parents — create a wallet for every parent
    (guardian) in the org who doesn't already have one. Idempotent."""
    org_id = current_user.org_id
    parents = await _parent_user_ids(db, org_id)
    existing = set((await db.execute(select(ParentWallet.user_id).where(ParentWallet.org_id == org_id))).scalars().all())
    created = 0
    for uid in parents:
        if uid in existing:
            continue
        db.add(ParentWallet(user_id=uid, is_active=True, org_id=org_id))
        created += 1
    if created:
        await db.flush()
    return ParentWalletInitializeResponse(created=created, total_parents=len(parents))


@router.get("/parent-wallets-summary", response_model=ParentWalletSummaryResponse, dependencies=[_fin_read])
async def parent_wallet_summary(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    org_id = current_user.org_id
    today = datetime.now(timezone.utc).date()

    async def _sum(*conds) -> Decimal:
        total = (await db.execute(
            select(func.coalesce(func.sum(ParentWalletEntry.signed_amount), 0))
            .select_from(ParentWalletEntry).join(JournalEntry, JournalEntry.id == ParentWalletEntry.journal_entry_id)
            .where(ParentWalletEntry.org_id == org_id, JournalEntry.reversed_at.is_(None), *conds)
        )).scalar()
        return money(total or 0)

    credits = await _sum(ParentWalletEntry.kind == "credit")
    debits = await _sum(ParentWalletEntry.kind == "debit")
    today_credits = await _sum(ParentWalletEntry.kind == "credit", JournalEntry.entry_date == today)
    today_debits = await _sum(ParentWalletEntry.kind == "debit", JournalEntry.entry_date == today)
    balance = await _sum()
    active = (await db.execute(select(func.count()).select_from(ParentWallet).where(
        ParentWallet.org_id == org_id, ParentWallet.is_active == True))).scalar() or 0  # noqa: E712
    return ParentWalletSummaryResponse(
        total_credits=float(credits), today_credits=float(today_credits),
        total_debits=float(-debits), today_debits=float(-today_debits),
        cumulative_balance=float(balance), total_active_wallets=active,
    )


@router.get("/parent-wallets/{wallet_id}", response_model=ParentWalletDetailResponse, dependencies=[_fin_read])
async def get_parent_wallet(wallet_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    w = await _load_wallet(db, wallet_id, current_user.org_id)
    base = await _parent_wallet_response(db, w, current_user.org_id)
    rows = (await db.execute(
        select(ParentWalletEntry, JournalEntry.reversed_at)
        .outerjoin(JournalEntry, JournalEntry.id == ParentWalletEntry.journal_entry_id)
        .where(ParentWalletEntry.wallet_id == w.id, ParentWalletEntry.org_id == current_user.org_id)
        .order_by(ParentWalletEntry.created_at.desc())
    )).all()
    entries = [ParentWalletEntryResponse(id=e.id, kind=e.kind, signed_amount=float(e.signed_amount), memo=e.memo,
                                         journal_entry_id=e.journal_entry_id, reversed=rev is not None, created_at=e.created_at)
               for e, rev in rows]
    return ParentWalletDetailResponse(**base.model_dump(), entries=entries)


@router.post("/parent-wallets/{wallet_id}/credit", response_model=ParentWalletResponse, dependencies=[_fin_post])
async def credit_parent_wallet(wallet_id: str, payload: ParentCreditRequest, request: Request = None,
                               db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Add Credit — Dr Cash / Cr Parent Wallet Float (holding the parent's money, a liability)."""
    w = await _load_wallet(db, wallet_id, current_user.org_id)
    if not w.is_active:
        raise HTTPException(status_code=409, detail="Wallet is inactive.")
    cash = await _require_cash(db, current_user.org_id, payload.cash_account_id)
    float_acct = await _ensure_account(db, current_user.org_id, PARENT_WALLET_FLOAT_CODE, PARENT_WALLET_FLOAT_NAME, "liability")
    amount = money(payload.amount)
    entry_date = payload.txn_date or datetime.now(timezone.utc).date()
    await _post_parent_move(db, current_user, w, "credit", amount,
                            [{"account_id": cash.id, "debit": amount, "credit": 0, "description": "Wallet credit"},
                             {"account_id": float_acct.id, "debit": 0, "credit": amount, "description": payload.memo}],
                            entry_date, payload.memo, request)
    return await _parent_wallet_response(db, w, current_user.org_id)


@router.post("/parent-wallets/{wallet_id}/debit", response_model=ParentWalletResponse, dependencies=[_fin_post])
async def debit_parent_wallet(wallet_id: str, payload: ParentDebitRequest, request: Request = None,
                              db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Manual debit / refund — Dr Parent Wallet Float / Cr Cash. Hard no-overdraw."""
    w = await _load_wallet(db, wallet_id, current_user.org_id)
    amount = money(payload.amount)
    balance = await _entry_sum(db, current_user.org_id, w.user_id)
    if amount > balance:
        raise HTTPException(status_code=422, detail="Insufficient wallet balance.")
    cash = await _require_cash(db, current_user.org_id, payload.cash_account_id)
    float_acct = await _ensure_account(db, current_user.org_id, PARENT_WALLET_FLOAT_CODE, PARENT_WALLET_FLOAT_NAME, "liability")
    entry_date = payload.txn_date or datetime.now(timezone.utc).date()
    await _post_parent_move(db, current_user, w, "debit", amount,
                            [{"account_id": float_acct.id, "debit": amount, "credit": 0, "description": "Wallet debit"},
                             {"account_id": cash.id, "debit": 0, "credit": amount, "description": payload.memo}],
                            entry_date, payload.memo, request)
    return await _parent_wallet_response(db, w, current_user.org_id)


@router.get("/parent-wallets/{wallet_id}/ledger.csv", dependencies=[_fin_read])
async def download_parent_wallet_ledger(wallet_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Download Wallet Ledger — CSV of this wallet's transaction entries."""
    w = await _load_wallet(db, wallet_id, current_user.org_id)
    u = (await db.execute(select(User.full_name).where(User.id == w.user_id))).scalar_one_or_none()
    rows = (await db.execute(
        select(ParentWalletEntry, JournalEntry.reversed_at)
        .outerjoin(JournalEntry, JournalEntry.id == ParentWalletEntry.journal_entry_id)
        .where(ParentWalletEntry.wallet_id == w.id, ParentWalletEntry.org_id == current_user.org_id)
        .order_by(ParentWalletEntry.created_at.asc())
    )).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Type", "Amount", "Memo", "Reversed"])
    for e, rev in rows:
        writer.writerow([e.created_at.date().isoformat(), e.kind, float(e.signed_amount), e.memo or "", "yes" if rev else "no"])
    filename = f"wallet-ledger-{(u or 'parent').replace(' ', '-')}.csv"
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ── Settings ─────────────────────────────────────────────────────────────────────

async def _get_or_create_parent_settings(db: AsyncSession, org_id: str) -> ParentWalletSettings:
    s = (await db.execute(select(ParentWalletSettings).where(ParentWalletSettings.org_id == org_id))).scalar_one_or_none()
    if not s:
        s = ParentWalletSettings(org_id=org_id)
        db.add(s)
        await db.flush()
    return s


def _parent_settings_response(s: ParentWalletSettings) -> ParentWalletSettingsResponse:
    return ParentWalletSettingsResponse(auto_invoice_pay=s.auto_invoice_pay, correspondent_email=s.correspondent_email, org_id=s.org_id)


@router.get("/parent-wallet-settings", response_model=ParentWalletSettingsResponse, dependencies=[_fin_read])
async def get_parent_wallet_settings(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_or_create_parent_settings(db, current_user.org_id)
    return _parent_settings_response(s)


@router.put("/parent-wallet-settings", response_model=ParentWalletSettingsResponse, dependencies=[_fin_write])
async def update_parent_wallet_settings(payload: ParentWalletSettingsUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_or_create_parent_settings(db, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    if "auto_invoice_pay" in data:
        s.auto_invoice_pay = data["auto_invoice_pay"]
    if "correspondent_email" in data:
        s.correspondent_email = data["correspondent_email"] or None
    await db.flush()
    return _parent_settings_response(s)
