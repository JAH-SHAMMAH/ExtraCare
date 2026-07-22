"""Student Wallet / PocketMoney + Cooperative router (Batch 6), prefix ``/finance``.

Real student money, ledger-backed. Balances are DERIVED from the subledger over
non-reversed journal entries — never stored. Wallet float + cooperative fund are
LIABILITY control accounts (auto-ensured in the Chart of Accounts); income is
recognised only on a SPEND.

RBAC (segregation of duties):
  • top-up / withdraw / cooperative contribute+payout  → payments:post (real cash)
  • spend (draw a student's OWN wallet down to income)  → the dedicated, constrained
    ``wallet:spend`` scope (till staff) — cannot move cash or post anything else.
  • administer (create wallet/member, set limits, view) → payments:write
No-overdraw is a HARD block; the daily spend limit (PocketMoney) is a hard block;
all postings inherit the engine's double-entry + period-lock guards.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.tenant import require_module
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.modules.school import Student, SchoolClass
from app.models.modules.finance import LedgerAccount, JournalEntry, JournalLine
from app.models.modules.wallet import StudentWallet, WalletEntry, CooperativeMember, CoopEntry, WalletSettings
from app.schemas.wallet import (
    WalletCreate, WalletUpdate, WalletResponse, WalletListResponse,
    WalletEntryResponse, WalletDetailResponse,
    WalletSummaryResponse, WalletSettingsResponse, WalletSettingsUpdate,
    TopUpRequest, WithdrawRequest, SpendRequest,
    CoopMemberCreate, CoopMemberResponse, CoopMemberListResponse,
    CoopEntryResponse, CoopMemberDetailResponse, CoopMoveRequest,
    ReconciliationResponse,
)
from app.services import ledger
from app.services.ledger import money

router = APIRouter(
    prefix="/finance",
    tags=["Wallet & Cooperative"],
    dependencies=[Depends(require_module("school"))],
)

_fin_read = Depends(PermissionChecker("payments:read"))
_fin_write = Depends(PermissionChecker("payments:write"))
_fin_post = Depends(PermissionChecker("payments:post"))
_spend = Depends(PermissionChecker("wallet:spend"))   # dedicated, constrained scope

WALLET_FLOAT_CODE = "2200"
COOP_FUND_CODE = "2300"


# ── shared helpers ────────────────────────────────────────────────────────────

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


async def _require_account(db: AsyncSession, org_id: str, account_id: str, must_type: str | None = None) -> LedgerAccount:
    a = (await db.execute(
        select(LedgerAccount).where(
            LedgerAccount.id == account_id, LedgerAccount.org_id == org_id, LedgerAccount.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="account not found in your organisation.")
    if must_type and a.type != must_type:
        raise HTTPException(status_code=422, detail=f"account must be of type '{must_type}'.")
    return a


async def _student_name(db: AsyncSession, org_id: str, student_id: str) -> str | None:
    r = (await db.execute(
        select(Student.first_name, Student.last_name).where(Student.id == student_id, Student.org_id == org_id)
    )).first()
    return f"{r.first_name} {r.last_name}".strip() if r else None


async def _student_meta(db: AsyncSession, org_id: str, student_id: str) -> dict:
    """Parent-centric display fields for a wallet: the student's name, funding
    guardian, and class — one query, LEFT-joined to the class."""
    r = (await db.execute(
        select(Student.first_name, Student.last_name, Student.guardian_name,
               Student.guardian_phone, SchoolClass.name)
        .outerjoin(SchoolClass, SchoolClass.id == Student.class_id)
        .where(Student.id == student_id, Student.org_id == org_id)
    )).first()
    if not r:
        return {"student_name": None, "guardian_name": None, "guardian_phone": None, "class_name": None}
    return {
        "student_name": f"{r.first_name} {r.last_name}".strip(),
        "guardian_name": r.guardian_name,
        "guardian_phone": r.guardian_phone,
        "class_name": r[4],
    }


async def _wallet_balance(db: AsyncSession, org_id: str, student_id: str) -> Decimal:
    total = (await db.execute(
        select(func.coalesce(func.sum(WalletEntry.signed_amount), 0))
        .select_from(WalletEntry).join(JournalEntry, JournalEntry.id == WalletEntry.journal_entry_id)
        .where(WalletEntry.org_id == org_id, WalletEntry.student_id == student_id, JournalEntry.reversed_at.is_(None))
    )).scalar()
    return money(total or 0)


async def _spent_on(db: AsyncSession, org_id: str, student_id: str, d) -> Decimal:
    total = (await db.execute(
        select(func.coalesce(func.sum(WalletEntry.signed_amount), 0))
        .select_from(WalletEntry).join(JournalEntry, JournalEntry.id == WalletEntry.journal_entry_id)
        .where(WalletEntry.org_id == org_id, WalletEntry.student_id == student_id,
               WalletEntry.kind == "spend", JournalEntry.reversed_at.is_(None), JournalEntry.entry_date == d)
    )).scalar()
    return money(-(total or 0))   # spends are negative; return positive spent amount


async def _coop_balance(db: AsyncSession, org_id: str, member_id: str) -> Decimal:
    total = (await db.execute(
        select(func.coalesce(func.sum(CoopEntry.signed_amount), 0))
        .select_from(CoopEntry).join(JournalEntry, JournalEntry.id == CoopEntry.journal_entry_id)
        .where(CoopEntry.org_id == org_id, CoopEntry.member_id == member_id, JournalEntry.reversed_at.is_(None))
    )).scalar()
    return money(total or 0)


async def _liability_gl_balance(db: AsyncSession, org_id: str, account_id: str) -> Decimal:
    """Credit-normal liability balance = Σ credits − Σ debits over non-reversed entries."""
    row = (await db.execute(
        select(func.coalesce(func.sum(JournalLine.credit), 0), func.coalesce(func.sum(JournalLine.debit), 0))
        .select_from(JournalLine).join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(JournalLine.org_id == org_id, JournalLine.account_id == account_id, JournalEntry.reversed_at.is_(None))
    )).first()
    return money((row[0] or 0) - (row[1] or 0))


# ── Wallets ───────────────────────────────────────────────────────────────────

async def _wallet_response(db, w: StudentWallet, org_id: str) -> WalletResponse:
    meta = await _student_meta(db, org_id, w.student_id)
    return WalletResponse(
        id=w.id, student_id=w.student_id, student_name=meta["student_name"],
        guardian_name=meta["guardian_name"], guardian_phone=meta["guardian_phone"], class_name=meta["class_name"],
        spend_limit_daily=float(w.spend_limit_daily) if w.spend_limit_daily is not None else None,
        is_active=w.is_active, balance=float(await _wallet_balance(db, org_id, w.student_id)),
        created_at=w.created_at, org_id=w.org_id,
    )


async def _load_wallet(db, wid, org_id) -> StudentWallet:
    w = (await db.execute(select(StudentWallet).where(StudentWallet.id == wid, StudentWallet.org_id == org_id))).scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="Wallet not found.")
    return w


@router.get("/wallets", response_model=WalletListResponse, dependencies=[_fin_read])
async def list_wallets(
    page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    base = select(StudentWallet).where(StudentWallet.org_id == current_user.org_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(base.order_by(StudentWallet.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return WalletListResponse(items=[await _wallet_response(db, w, current_user.org_id) for w in rows],
                              total=total, page=page, page_size=page_size)


@router.post("/wallets", response_model=WalletResponse, status_code=201, dependencies=[_fin_write])
async def create_wallet(payload: WalletCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = (await db.execute(select(Student).where(Student.id == payload.student_id, Student.org_id == current_user.org_id, Student.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not s:
        raise HTTPException(status_code=404, detail="student not found in your organisation.")
    # Default the daily spend limit from Wallet Settings when the creator omits it.
    limit = payload.spend_limit_daily
    if limit is None:
        settings = await _get_or_create_wallet_settings(db, current_user.org_id)
        limit = settings.default_daily_limit
    w = StudentWallet(student_id=s.id, spend_limit_daily=money(limit) if limit is not None else None,
                      is_active=True, org_id=current_user.org_id)
    db.add(w)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="This student already has a wallet.")
    return await _wallet_response(db, w, current_user.org_id)


@router.patch("/wallets/{wallet_id}", response_model=WalletResponse, dependencies=[_fin_write])
async def update_wallet(wallet_id: str, payload: WalletUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    w = await _load_wallet(db, wallet_id, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    if "spend_limit_daily" in data:
        w.spend_limit_daily = money(data["spend_limit_daily"]) if data["spend_limit_daily"] is not None else None
    if "is_active" in data:
        w.is_active = data["is_active"]
    await db.flush()
    return await _wallet_response(db, w, current_user.org_id)


@router.get("/wallets/{wallet_id}", response_model=WalletDetailResponse, dependencies=[_fin_read])
async def get_wallet(wallet_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    w = await _load_wallet(db, wallet_id, current_user.org_id)
    base = await _wallet_response(db, w, current_user.org_id)
    rows = (await db.execute(
        select(WalletEntry, JournalEntry.reversed_at)
        .outerjoin(JournalEntry, JournalEntry.id == WalletEntry.journal_entry_id)
        .where(WalletEntry.wallet_id == w.id, WalletEntry.org_id == current_user.org_id)
        .order_by(WalletEntry.created_at.desc())
    )).all()
    entries = [WalletEntryResponse(id=e.id, kind=e.kind, signed_amount=float(e.signed_amount), memo=e.memo,
                                   journal_entry_id=e.journal_entry_id, reversed=rev is not None, created_at=e.created_at)
               for e, rev in rows]
    return WalletDetailResponse(**base.model_dump(), entries=entries)


async def _post_wallet_move(db, current_user, w: StudentWallet, kind: str, amount: Decimal,
                            lines: list[dict], entry_date, memo, request) -> WalletEntry:
    entry = await ledger.post_journal_entry(
        db, org_id=current_user.org_id, entry_date=entry_date, memo=memo or f"Wallet {kind}",
        source="wallet", source_id=w.student_id, lines=lines, actor=current_user, request=request,
    )
    signed = amount if kind == "top_up" else -amount
    we = WalletEntry(wallet_id=w.id, student_id=w.student_id, kind=kind, signed_amount=signed,
                     journal_entry_id=entry.id, memo=memo, created_by=current_user.id, org_id=current_user.org_id)
    db.add(we)
    await db.flush()
    return we


@router.post("/wallets/{wallet_id}/topup", response_model=WalletResponse, dependencies=[_fin_post])
async def topup_wallet(wallet_id: str, payload: TopUpRequest, request: Request = None,
                       db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    w = await _load_wallet(db, wallet_id, current_user.org_id)
    settings = await _get_or_create_wallet_settings(db, current_user.org_id)
    if not settings.allow_topup:
        raise HTTPException(status_code=409, detail="Top-ups are disabled in Wallet Settings.")
    cash = await _require_account(db, current_user.org_id, payload.cash_account_id)
    float_acct = await _ensure_account(db, current_user.org_id, WALLET_FLOAT_CODE, "Student Wallet Float", "liability")
    amount = money(payload.amount)
    entry_date = payload.txn_date or datetime.now(timezone.utc).date()
    # Dr Cash / Cr Wallet Float — holding the parent's money (a liability), NOT income.
    await _post_wallet_move(db, current_user, w, "top_up", amount,
                            [{"account_id": cash.id, "debit": amount, "credit": 0, "description": "Wallet top-up"},
                             {"account_id": float_acct.id, "debit": 0, "credit": amount, "description": payload.memo}],
                            entry_date, payload.memo, request)
    return await _wallet_response(db, w, current_user.org_id)


@router.post("/wallets/{wallet_id}/withdraw", response_model=WalletResponse, dependencies=[_fin_post])
async def withdraw_wallet(wallet_id: str, payload: WithdrawRequest, request: Request = None,
                          db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    w = await _load_wallet(db, wallet_id, current_user.org_id)
    amount = money(payload.amount)
    if amount > await _wallet_balance(db, current_user.org_id, w.student_id):
        raise HTTPException(status_code=422, detail="Insufficient wallet balance.")   # no-overdraw
    cash = await _require_account(db, current_user.org_id, payload.cash_account_id)
    float_acct = await _ensure_account(db, current_user.org_id, WALLET_FLOAT_CODE, "Student Wallet Float", "liability")
    entry_date = payload.txn_date or datetime.now(timezone.utc).date()
    await _post_wallet_move(db, current_user, w, "withdrawal", amount,
                            [{"account_id": float_acct.id, "debit": amount, "credit": 0, "description": "Wallet refund"},
                             {"account_id": cash.id, "debit": 0, "credit": amount, "description": payload.memo}],
                            entry_date, payload.memo, request)
    return await _wallet_response(db, w, current_user.org_id)


@router.post("/wallets/{wallet_id}/spend", response_model=WalletResponse, dependencies=[_spend])
async def spend_wallet(wallet_id: str, payload: SpendRequest, request: Request = None,
                       db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """The ONLY thing a wallet:spend holder can do: draw this student's wallet down
    to an income account. No cash movement, no arbitrary entries."""
    w = await _load_wallet(db, wallet_id, current_user.org_id)
    if not w.is_active:
        raise HTTPException(status_code=409, detail="Wallet is inactive.")
    amount = money(payload.amount)
    entry_date = payload.txn_date or datetime.now(timezone.utc).date()
    if amount > await _wallet_balance(db, current_user.org_id, w.student_id):
        raise HTTPException(status_code=422, detail="Insufficient wallet balance.")   # no-overdraw HARD block
    if w.spend_limit_daily is not None:
        spent = await _spent_on(db, current_user.org_id, w.student_id, entry_date)
        if spent + amount > money(w.spend_limit_daily):
            raise HTTPException(status_code=422, detail=f"Daily spend limit reached ({money(w.spend_limit_daily)}).")
    income = await _require_account(db, current_user.org_id, payload.income_account_id, must_type="income")
    float_acct = await _ensure_account(db, current_user.org_id, WALLET_FLOAT_CODE, "Student Wallet Float", "liability")
    # Income is recognised HERE, on spend: Dr Wallet Float / Cr Income.
    await _post_wallet_move(db, current_user, w, "spend", amount,
                            [{"account_id": float_acct.id, "debit": amount, "credit": 0, "description": "Wallet spend"},
                             {"account_id": income.id, "debit": 0, "credit": amount, "description": payload.memo}],
                            entry_date, payload.memo, request)
    return await _wallet_response(db, w, current_user.org_id)


@router.post("/wallets/{wallet_id}/entries/{entry_id}/reverse", response_model=WalletResponse, dependencies=[_fin_post])
async def reverse_wallet_entry(wallet_id: str, entry_id: str, request: Request = None,
                               db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    w = await _load_wallet(db, wallet_id, current_user.org_id)
    we = (await db.execute(select(WalletEntry).where(WalletEntry.id == entry_id, WalletEntry.wallet_id == w.id, WalletEntry.org_id == current_user.org_id))).scalar_one_or_none()
    if not we:
        raise HTTPException(status_code=404, detail="Wallet entry not found.")
    if we.journal_entry_id:
        await ledger.reverse_entry(db, entry_id=we.journal_entry_id, org_id=current_user.org_id, actor=current_user, request=request)
    return await _wallet_response(db, w, current_user.org_id)


@router.get("/wallets-reconciliation", response_model=ReconciliationResponse, dependencies=[_fin_read])
async def wallet_reconciliation(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    float_acct = await _ensure_account(db, current_user.org_id, WALLET_FLOAT_CODE, "Student Wallet Float", "liability")
    gl = await _liability_gl_balance(db, current_user.org_id, float_acct.id)
    wallets = (await db.execute(select(StudentWallet.student_id).where(StudentWallet.org_id == current_user.org_id))).scalars().all()
    subtotal = money(0)
    for sid in wallets:
        subtotal += await _wallet_balance(db, current_user.org_id, sid)
    return ReconciliationResponse(control_account=f"{float_acct.code} {float_acct.name}",
                                  gl_balance=float(gl), subledger_total=float(subtotal), balanced=(gl == subtotal))


# ── Wallet Manager: dashboard summary + settings ──────────────────────────────

@router.get("/wallets-summary", response_model=WalletSummaryResponse, dependencies=[_fin_read])
async def wallet_summary(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Org-wide roll-up for the Wallet Manager dashboard cards. Balances/totals
    are derived over non-reversed entries only (consistent with per-wallet balance)."""
    org_id = current_user.org_id
    total_wallets = (await db.execute(select(func.count()).select_from(StudentWallet).where(StudentWallet.org_id == org_id))).scalar() or 0
    active = (await db.execute(select(func.count()).select_from(StudentWallet).where(StudentWallet.org_id == org_id, StudentWallet.is_active == True))).scalar() or 0  # noqa: E712

    async def _sum(*conds) -> Decimal:
        total = (await db.execute(
            select(func.coalesce(func.sum(WalletEntry.signed_amount), 0))
            .select_from(WalletEntry).join(JournalEntry, JournalEntry.id == WalletEntry.journal_entry_id)
            .where(WalletEntry.org_id == org_id, JournalEntry.reversed_at.is_(None), *conds)
        )).scalar()
        return money(total or 0)

    balance = await _sum()
    topped_up = await _sum(WalletEntry.kind == "top_up")
    spent = await _sum(WalletEntry.kind == "spend")
    return WalletSummaryResponse(
        total_wallets=total_wallets, active_wallets=active, inactive_wallets=total_wallets - active,
        total_balance=float(balance), total_topped_up=float(topped_up), total_spent=float(-spent),
    )


async def _get_or_create_wallet_settings(db: AsyncSession, org_id: str) -> WalletSettings:
    s = (await db.execute(select(WalletSettings).where(WalletSettings.org_id == org_id))).scalar_one_or_none()
    if not s:
        s = WalletSettings(org_id=org_id)
        db.add(s)
        await db.flush()
    return s


def _wallet_settings_response(s: WalletSettings) -> WalletSettingsResponse:
    return WalletSettingsResponse(
        default_daily_limit=float(s.default_daily_limit) if s.default_daily_limit is not None else None,
        low_balance_threshold=float(s.low_balance_threshold) if s.low_balance_threshold is not None else None,
        notify_low_balance=s.notify_low_balance, allow_topup=s.allow_topup, org_id=s.org_id,
    )


@router.get("/wallet-settings", response_model=WalletSettingsResponse, dependencies=[_fin_read])
async def get_wallet_settings(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_or_create_wallet_settings(db, current_user.org_id)
    return _wallet_settings_response(s)


@router.put("/wallet-settings", response_model=WalletSettingsResponse, dependencies=[_fin_write])
async def update_wallet_settings(payload: WalletSettingsUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_or_create_wallet_settings(db, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    if "default_daily_limit" in data:
        s.default_daily_limit = money(data["default_daily_limit"]) if data["default_daily_limit"] is not None else None
    if "low_balance_threshold" in data:
        s.low_balance_threshold = money(data["low_balance_threshold"]) if data["low_balance_threshold"] is not None else None
    if "notify_low_balance" in data:
        s.notify_low_balance = data["notify_low_balance"]
    if "allow_topup" in data:
        s.allow_topup = data["allow_topup"]
    await db.flush()
    return _wallet_settings_response(s)


# ── Cooperative ───────────────────────────────────────────────────────────────

async def _coop_response(db, m: CooperativeMember, org_id: str) -> CoopMemberResponse:
    return CoopMemberResponse(id=m.id, member_name=m.member_name, member_user_id=m.member_user_id,
                              is_active=m.is_active, joined_on=m.joined_on,
                              balance=float(await _coop_balance(db, org_id, m.id)), created_at=m.created_at, org_id=m.org_id)


async def _load_member(db, mid, org_id) -> CooperativeMember:
    m = (await db.execute(select(CooperativeMember).where(CooperativeMember.id == mid, CooperativeMember.org_id == org_id))).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Member not found.")
    return m


@router.get("/cooperative/members", response_model=CoopMemberListResponse, dependencies=[_fin_read])
async def list_members(page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
                       db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    base = select(CooperativeMember).where(CooperativeMember.org_id == current_user.org_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(base.order_by(CooperativeMember.member_name).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return CoopMemberListResponse(items=[await _coop_response(db, m, current_user.org_id) for m in rows],
                                  total=total, page=page, page_size=page_size)


@router.post("/cooperative/members", response_model=CoopMemberResponse, status_code=201, dependencies=[_fin_write])
async def create_member(payload: CoopMemberCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    m = CooperativeMember(member_name=payload.member_name, member_user_id=payload.member_user_id,
                          is_active=True, joined_on=payload.joined_on, org_id=current_user.org_id)
    db.add(m)
    await db.flush()
    return await _coop_response(db, m, current_user.org_id)


@router.get("/cooperative/members/{member_id}", response_model=CoopMemberDetailResponse, dependencies=[_fin_read])
async def get_member(member_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    m = await _load_member(db, member_id, current_user.org_id)
    base = await _coop_response(db, m, current_user.org_id)
    rows = (await db.execute(
        select(CoopEntry, JournalEntry.reversed_at)
        .outerjoin(JournalEntry, JournalEntry.id == CoopEntry.journal_entry_id)
        .where(CoopEntry.member_id == m.id, CoopEntry.org_id == current_user.org_id)
        .order_by(CoopEntry.created_at.desc())
    )).all()
    entries = [CoopEntryResponse(id=e.id, kind=e.kind, signed_amount=float(e.signed_amount), memo=e.memo,
                                 journal_entry_id=e.journal_entry_id, reversed=rev is not None, created_at=e.created_at)
               for e, rev in rows]
    return CoopMemberDetailResponse(**base.model_dump(), entries=entries)


async def _post_coop_move(db, current_user, m, kind, amount, lines, entry_date, memo, request):
    entry = await ledger.post_journal_entry(
        db, org_id=current_user.org_id, entry_date=entry_date, memo=memo or f"Cooperative {kind}",
        source="cooperative", source_id=m.id, lines=lines, actor=current_user, request=request,
    )
    signed = amount if kind == "contribution" else -amount
    db.add(CoopEntry(member_id=m.id, kind=kind, signed_amount=signed, journal_entry_id=entry.id,
                     memo=memo, created_by=current_user.id, org_id=current_user.org_id))
    await db.flush()


@router.post("/cooperative/members/{member_id}/contribute", response_model=CoopMemberResponse, dependencies=[_fin_post])
async def contribute(member_id: str, payload: CoopMoveRequest, request: Request = None,
                     db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    m = await _load_member(db, member_id, current_user.org_id)
    cash = await _require_account(db, current_user.org_id, payload.cash_account_id)
    fund = await _ensure_account(db, current_user.org_id, COOP_FUND_CODE, "Cooperative Members Fund", "liability")
    amount = money(payload.amount)
    entry_date = payload.txn_date or datetime.now(timezone.utc).date()
    # Dr Cash / Cr Cooperative Fund — funds held on the member's behalf (liability).
    await _post_coop_move(db, current_user, m, "contribution", amount,
                          [{"account_id": cash.id, "debit": amount, "credit": 0, "description": "Coop contribution"},
                           {"account_id": fund.id, "debit": 0, "credit": amount, "description": payload.memo}],
                          entry_date, payload.memo, request)
    return await _coop_response(db, m, current_user.org_id)


@router.post("/cooperative/members/{member_id}/payout", response_model=CoopMemberResponse, dependencies=[_fin_post])
async def payout(member_id: str, payload: CoopMoveRequest, request: Request = None,
                 db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    m = await _load_member(db, member_id, current_user.org_id)
    amount = money(payload.amount)
    if amount > await _coop_balance(db, current_user.org_id, m.id):
        raise HTTPException(status_code=422, detail="Insufficient cooperative balance.")   # no-overdraw
    cash = await _require_account(db, current_user.org_id, payload.cash_account_id)
    fund = await _ensure_account(db, current_user.org_id, COOP_FUND_CODE, "Cooperative Members Fund", "liability")
    entry_date = payload.txn_date or datetime.now(timezone.utc).date()
    await _post_coop_move(db, current_user, m, "payout", amount,
                          [{"account_id": fund.id, "debit": amount, "credit": 0, "description": "Coop payout"},
                           {"account_id": cash.id, "debit": 0, "credit": amount, "description": payload.memo}],
                          entry_date, payload.memo, request)
    return await _coop_response(db, m, current_user.org_id)


@router.get("/cooperative/reconciliation", response_model=ReconciliationResponse, dependencies=[_fin_read])
async def coop_reconciliation(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    fund = await _ensure_account(db, current_user.org_id, COOP_FUND_CODE, "Cooperative Members Fund", "liability")
    gl = await _liability_gl_balance(db, current_user.org_id, fund.id)
    members = (await db.execute(select(CooperativeMember.id).where(CooperativeMember.org_id == current_user.org_id))).scalars().all()
    subtotal = money(0)
    for mid in members:
        subtotal += await _coop_balance(db, current_user.org_id, mid)
    return ReconciliationResponse(control_account=f"{fund.code} {fund.name}",
                                  gl_balance=float(gl), subledger_total=float(subtotal), balanced=(gl == subtotal))
