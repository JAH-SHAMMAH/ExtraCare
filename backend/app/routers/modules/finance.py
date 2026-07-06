"""Finance & Accounting router (Batch 5), prefix ``/finance``.

Chart of Accounts, Accounting Periods, the general-ledger journal, Invoices and
Payroll. Every money posting goes through ``app.services.ledger`` so double-entry
integrity, immutability, period-lock and audit are enforced in one place.

RBAC (segregation of duties): ``payments:read`` view · ``payments:write`` draft
(manager + accountant + admin) · ``payments:post`` post to ledger (accountant +
admin, NOT manager). Payroll approval additionally requires approver != creator
(two-person). Gated ``require_module("school")`` + payments, so the finance-only
accountant role needs no school scope.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, date
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
from app.models.payment import StudentFeeRecord, TenantPaymentSettings, PaymentProvider
from app.models.modules.finance import (
    LedgerAccount, AccountingPeriod, JournalEntry, JournalLine,
    Invoice, InvoiceLine, PayrollRun, SchoolPayslip,
    SalaryAdvance, SalaryAdvanceRepayment,
    PayAdjustmentPack, PayAdjustmentItem,
    Requisition, RequisitionItem,
    FeeDiscount, BankAccount, OrgFinanceSettings,
)
from app.schemas.finance import (
    LedgerAccountCreate, LedgerAccountUpdate, LedgerAccountResponse,
    PeriodCreate, PeriodResponse,
    ManualJournalCreate, JournalEntryResponse, JournalLineResponse, JournalListResponse,
    InvoiceCreate, InvoiceUpdate, InvoiceResponse, InvoiceLineResponse, InvoiceListResponse, PaymentRequest,
    PayrollRunCreate, PayrollRunResponse, PayslipResponse, PayrollListResponse,
    FinancialStatements, TrialBalanceRow,
    SalaryAdvanceCreate, SalaryAdvanceApprove, SalaryAdvanceRepay, SalaryAdvanceResponse,
    PayAdjustmentCreate, PayAdjustmentResponse, PayAdjustmentItemResponse, PAY_ADJUSTMENT_KINDS,
    RequisitionCreate, RequisitionResponse, RequisitionItemResponse,
    IncomeExpenseReport, ReportAccountRow, ReportSourceRow,
    DiscountCreate, DiscountResponse, DISCOUNT_TYPES,
    FeeRecordCreate, FeeRecordUpdate, FeeRecordResponse, ClassFeeAssign, ClassFeeAssignResult, ClassOption,
    BankAccountCreate, BankAccountUpdate, BankAccountResponse, BankAccountPublic,
    FinanceSettingsUpdate, FinanceSettingsResponse,
    PaymentGatewayCreate, PaymentGatewayUpdate, PaymentGatewayResponse, GATEWAY_MODES, GATEWAY_PROVIDERS,
    ACCOUNT_TYPES,
)
from app.services import ledger
from app.services.ledger import money
from app.services import crypto
from app.services.audit_service import log_action
from app.models.audit import AuditAction

router = APIRouter(
    prefix="/finance",
    tags=["Finance & Accounting"],
    dependencies=[Depends(require_module("school"))],
)

_fin_read = Depends(PermissionChecker("payments:read"))
_fin_write = Depends(PermissionChecker("payments:write"))
_fin_post = Depends(PermissionChecker("payments:post"))
# Managing live gateway API secrets is org_admin-only. DELIBERATELY on its own
# `payment_gateways` namespace, NOT a `payments:*` sub-scope — a `payments:gateways:*`
# scope would be auto-granted to every `payments:write` holder (accountant/manager)
# by the permission hierarchy. See ENCRYPTION_SERVICE_SPEC.md §9.
_gw_read = Depends(PermissionChecker("payment_gateways:read"))
_gw_write = Depends(PermissionChecker("payment_gateways:write"))


async def _account_meta(db: AsyncSession, org_id: str, ids: set[str]) -> dict[str, tuple[str, str]]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(
        select(LedgerAccount.id, LedgerAccount.code, LedgerAccount.name).where(
            LedgerAccount.org_id == org_id, LedgerAccount.id.in_(ids))
    )).all()
    return {r.id: (r.code, r.name) for r in rows}


async def _require_account(db: AsyncSession, org_id: str, account_id: str) -> LedgerAccount:
    a = (await db.execute(
        select(LedgerAccount).where(
            LedgerAccount.id == account_id, LedgerAccount.org_id == org_id,
            LedgerAccount.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="account not found in your organisation.")
    return a


# ── Chart of Accounts ──────────────────────────────────────────────────────────

def _account_response(a: LedgerAccount) -> LedgerAccountResponse:
    return LedgerAccountResponse(
        id=a.id, code=a.code, name=a.name, type=a.type, parent_id=a.parent_id,
        description=a.description, is_active=a.is_active, created_at=a.created_at, org_id=a.org_id,
    )


@router.get("/accounts", response_model=list[LedgerAccountResponse], dependencies=[_fin_read])
async def list_accounts(
    type: str | None = Query(default=None),
    active_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(LedgerAccount).where(
        LedgerAccount.org_id == current_user.org_id, LedgerAccount.is_deleted == False)  # noqa: E712
    if type:
        q = q.where(LedgerAccount.type == type)
    if active_only:
        q = q.where(LedgerAccount.is_active == True)  # noqa: E712
    rows = (await db.execute(q.order_by(LedgerAccount.code))).scalars().all()
    return [_account_response(a) for a in rows]


@router.post("/accounts", response_model=LedgerAccountResponse, status_code=201, dependencies=[_fin_write])
async def create_account(
    payload: LedgerAccountCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.type not in ACCOUNT_TYPES:
        raise HTTPException(status_code=422, detail=f"type must be one of {sorted(ACCOUNT_TYPES)}")
    if payload.parent_id:
        await _require_account(db, current_user.org_id, payload.parent_id)
    a = LedgerAccount(
        code=payload.code.strip(), name=payload.name, type=payload.type,
        parent_id=payload.parent_id, description=payload.description, is_active=True,
        org_id=current_user.org_id,
    )
    db.add(a)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Account code '{payload.code}' already exists.")
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="LedgerAccount", resource_id=a.id, resource_label=f"account {a.code} {a.name}", request=request,
    )
    return _account_response(a)


@router.patch("/accounts/{account_id}", response_model=LedgerAccountResponse, dependencies=[_fin_write])
async def update_account(
    account_id: str,
    payload: LedgerAccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    a = await _require_account(db, current_user.org_id, account_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(a, field, value)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Account code already exists.")
    return _account_response(a)


@router.delete("/accounts/{account_id}", status_code=204, dependencies=[_fin_write])
async def delete_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    a = await _require_account(db, current_user.org_id, account_id)
    used = (await db.execute(
        select(func.count()).select_from(JournalLine).where(JournalLine.account_id == a.id)
    )).scalar() or 0
    if used:
        raise HTTPException(status_code=409, detail="Account has postings; deactivate it instead of deleting.")
    a.is_deleted = True
    a.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Accounting Periods ─────────────────────────────────────────────────────────

def _period_response(p: AccountingPeriod) -> PeriodResponse:
    return PeriodResponse(
        id=p.id, name=p.name, start_date=p.start_date, end_date=p.end_date, status=p.status,
        locked_at=p.locked_at, locked_by=p.locked_by, created_at=p.created_at, org_id=p.org_id,
    )


@router.get("/periods", response_model=list[PeriodResponse], dependencies=[_fin_read])
async def list_periods(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows = (await db.execute(
        select(AccountingPeriod).where(AccountingPeriod.org_id == current_user.org_id)
        .order_by(AccountingPeriod.start_date.desc())
    )).scalars().all()
    return [_period_response(p) for p in rows]


@router.post("/periods", response_model=PeriodResponse, status_code=201, dependencies=[_fin_write])
async def create_period(
    payload: PeriodCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date.")
    p = AccountingPeriod(
        name=payload.name, start_date=payload.start_date, end_date=payload.end_date,
        status="open", org_id=current_user.org_id,
    )
    db.add(p)
    await db.flush()
    return _period_response(p)


async def _load_period(db, pid, org_id) -> AccountingPeriod:
    p = (await db.execute(
        select(AccountingPeriod).where(AccountingPeriod.id == pid, AccountingPeriod.org_id == org_id)
    )).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Period not found.")
    return p


@router.post("/periods/{period_id}/lock", response_model=PeriodResponse, dependencies=[_fin_post])
async def lock_period(
    period_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    p = await _load_period(db, period_id, current_user.org_id)
    p.status = "locked"
    p.locked_at = datetime.now(timezone.utc)
    p.locked_by = current_user.id
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="AccountingPeriod", resource_id=p.id, resource_label=f"locked period {p.name}",
        old_values={"status": "open"}, new_values={"status": "locked"}, severity="warning", request=request,
    )
    return _period_response(p)


@router.post("/periods/{period_id}/unlock", response_model=PeriodResponse, dependencies=[_fin_post])
async def unlock_period(
    period_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    p = await _load_period(db, period_id, current_user.org_id)
    p.status = "open"
    p.locked_at = None
    p.locked_by = None
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="AccountingPeriod", resource_id=p.id, resource_label=f"unlocked period {p.name}",
        old_values={"status": "locked"}, new_values={"status": "open"}, severity="warning", request=request,
    )
    return _period_response(p)


# ── Journal (general ledger) ───────────────────────────────────────────────────

async def _entry_response(db: AsyncSession, e: JournalEntry, org_id: str) -> JournalEntryResponse:
    lines = (await db.execute(
        select(JournalLine).where(JournalLine.entry_id == e.id).order_by(JournalLine.created_at)
    )).scalars().all()
    meta = await _account_meta(db, org_id, {ln.account_id for ln in lines})
    total = sum(money(ln.debit) for ln in lines)
    return JournalEntryResponse(
        id=e.id, entry_date=e.entry_date, memo=e.memo, source=e.source, source_id=e.source_id,
        status=e.status, period_id=e.period_id, posted_by=e.posted_by, posted_at=e.posted_at,
        reversal_of_id=e.reversal_of_id, reversed_by_id=e.reversed_by_id, reversed_at=e.reversed_at,
        total=float(total),
        lines=[
            JournalLineResponse(
                id=ln.id, account_id=ln.account_id,
                account_code=meta.get(ln.account_id, (None, None))[0],
                account_name=meta.get(ln.account_id, (None, None))[1],
                debit=float(ln.debit or 0), credit=float(ln.credit or 0), description=ln.description,
            ) for ln in lines
        ],
        created_at=e.created_at, org_id=e.org_id,
    )


@router.get("/journal", response_model=JournalListResponse, dependencies=[_fin_read])
async def list_journal(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = select(JournalEntry).where(JournalEntry.org_id == current_user.org_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    items = [await _entry_response(db, e, current_user.org_id) for e in rows]
    return JournalListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/journal", response_model=JournalEntryResponse, status_code=201, dependencies=[_fin_post])
async def post_manual_journal(
    payload: ManualJournalCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    entry = await ledger.post_journal_entry(
        db, org_id=current_user.org_id, entry_date=payload.entry_date, memo=payload.memo,
        source="manual", source_id=None,
        lines=[ln.model_dump() for ln in payload.lines], actor=current_user, request=request,
    )
    return await _entry_response(db, entry, current_user.org_id)


@router.post("/journal/{entry_id}/reverse", response_model=JournalEntryResponse, dependencies=[_fin_post])
async def reverse_journal(
    entry_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rev = await ledger.reverse_entry(db, entry_id=entry_id, org_id=current_user.org_id, actor=current_user, request=request)
    return await _entry_response(db, rev, current_user.org_id)


# ── Financial Statements (NEW) ───────────────────────────────────────────────────
# Read-only reporting derived from the ledger. Reversals are themselves cancelling
# entries, so summing ALL posted lines yields correct net balances (no filtering).

@router.get("/statements", response_model=FinancialStatements, dependencies=[_fin_write])
async def financial_statements(
    as_of: date | None = Query(default=None, description="Include entries on/before this date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = (
        select(JournalLine.account_id, func.sum(JournalLine.debit), func.sum(JournalLine.credit))
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(JournalEntry.org_id == current_user.org_id)
        .group_by(JournalLine.account_id)
    )
    if as_of:
        q = q.where(JournalEntry.entry_date <= as_of)
    sums = {aid: (money(d or 0), money(c or 0)) for aid, d, c in (await db.execute(q)).all()}

    accounts = (
        await db.execute(
            select(LedgerAccount).where(
                LedgerAccount.org_id == current_user.org_id,
                LedgerAccount.is_deleted == False,  # noqa: E712
            ).order_by(LedgerAccount.code)
        )
    ).scalars().all()

    rows: list[TrialBalanceRow] = []
    total_debit = total_credit = Decimal("0")
    income = expense = assets = liabilities = equity = Decimal("0")
    for acct in accounts:
        d, c = sums.get(acct.id, (Decimal("0"), Decimal("0")))
        if not d and not c:
            continue
        total_debit += d
        total_credit += c
        debit_normal = acct.type in ("asset", "expense")
        balance = (d - c) if debit_normal else (c - d)
        rows.append(TrialBalanceRow(
            account_id=acct.id, code=acct.code, name=acct.name, type=acct.type,
            debit=float(d), credit=float(c), balance=float(balance),
        ))
        if acct.type == "income":
            income += (c - d)
        elif acct.type == "expense":
            expense += (d - c)
        elif acct.type == "asset":
            assets += (d - c)
        elif acct.type == "liability":
            liabilities += (c - d)
        elif acct.type == "equity":
            equity += (c - d)

    net_income = income - expense
    return FinancialStatements(
        as_of=as_of,
        trial_balance=rows,
        total_debit=float(total_debit),
        total_credit=float(total_credit),
        balanced=(total_debit == total_credit),
        income=float(income),
        expense=float(expense),
        net_income=float(net_income),
        assets=float(assets),
        liabilities=float(liabilities),
        equity=float(equity),
        balance_sheet_balanced=(assets == liabilities + equity + net_income),
    )


# ── Finance Reports (read-only, period-scoped) ──────────────────────────────────
# A period Income & Expense report over the ledger — the flow counterpart to
# /statements (which is an as-of cumulative snapshot). READ-ONLY: it only reads
# posted journal lines (which payroll, requisitions, pay-adjustments, petty cash,
# invoices, etc. all write) and summarises them; it modifies nothing. Income/expense
# use the SAME sign convention as /statements so the two always agree.


# Gated payments:WRITE (not read) — the same bar as /statements. `payments:read`
# is granted to parents for their own invoice/fee visibility, so a read gate would
# leak the school's whole P&L to parents. Org-wide financials require payments:write.
@router.get("/reports/income-expense", response_model=IncomeExpenseReport, dependencies=[_fin_write])
async def income_expense_report(
    start: date | None = Query(default=None, description="Include entries on/after this date"),
    end: date | None = Query(default=None, description="Include entries on/before this date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if start and end and end < start:
        raise HTTPException(status_code=422, detail="Report end date cannot be before its start date.")

    def _window(q):
        if start:
            q = q.where(JournalEntry.entry_date >= start)
        if end:
            q = q.where(JournalEntry.entry_date <= end)
        return q

    # Per-account debit/credit within the window (reversals net out, as in /statements).
    aq = _window(
        select(JournalLine.account_id, func.sum(JournalLine.debit), func.sum(JournalLine.credit))
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(JournalEntry.org_id == current_user.org_id)
        .group_by(JournalLine.account_id)
    )
    sums = {aid: (money(d or 0), money(c or 0)) for aid, d, c in (await db.execute(aq)).all()}

    accounts = (await db.execute(
        select(LedgerAccount).where(
            LedgerAccount.org_id == current_user.org_id,
            LedgerAccount.is_deleted == False,           # noqa: E712
            LedgerAccount.type.in_(("income", "expense")),
        ).order_by(LedgerAccount.code)
    )).scalars().all()

    income = expense = Decimal("0")
    by_account: list[ReportAccountRow] = []
    for acct in accounts:
        d, c = sums.get(acct.id, (Decimal("0"), Decimal("0")))
        if not d and not c:
            continue
        amount = (c - d) if acct.type == "income" else (d - c)
        if acct.type == "income":
            income += amount
        else:
            expense += amount
        by_account.append(ReportAccountRow(
            account_id=acct.id, code=acct.code, name=acct.name, type=acct.type, amount=float(money(amount)),
        ))
    by_account.sort(key=lambda r: (r.type, -r.amount))

    # Per-source income/expense within the window (which feature drove the money).
    sq = _window(
        select(JournalEntry.source, LedgerAccount.type,
               func.sum(JournalLine.debit), func.sum(JournalLine.credit))
        .select_from(JournalLine)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .join(LedgerAccount, LedgerAccount.id == JournalLine.account_id)
        .where(
            JournalEntry.org_id == current_user.org_id,
            LedgerAccount.type.in_(("income", "expense")),
        )
        .group_by(JournalEntry.source, LedgerAccount.type)
    )
    src: dict[str, dict[str, Decimal]] = {}
    for source, atype, d, c in (await db.execute(sq)).all():
        bucket = src.setdefault(source or "manual", {"income": Decimal("0"), "expense": Decimal("0")})
        if atype == "income":
            bucket["income"] += money(c or 0) - money(d or 0)
        else:
            bucket["expense"] += money(d or 0) - money(c or 0)
    by_source = [
        ReportSourceRow(source=s, income=float(money(v["income"])), expense=float(money(v["expense"])))
        for s, v in src.items()
    ]
    by_source.sort(key=lambda r: -(abs(r.income) + abs(r.expense)))

    return IncomeExpenseReport(
        start=start, end=end,
        income=float(money(income)), expense=float(money(expense)), net=float(money(income - expense)),
        by_account=by_account, by_source=by_source,
    )


# ── Invoices ───────────────────────────────────────────────────────────────────

async def _invoice_response(db: AsyncSession, inv: Invoice, org_id: str) -> InvoiceResponse:
    lines = (await db.execute(
        select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id).order_by(InvoiceLine.created_at)
    )).scalars().all()
    meta = await _account_meta(db, org_id, {ln.income_account_id for ln in lines})
    return InvoiceResponse(
        id=inv.id, number=inv.number, customer_name=inv.customer_name, student_id=inv.student_id,
        invoice_date=inv.invoice_date, due_date=inv.due_date, status=inv.status, total=float(inv.total or 0),
        memo=inv.memo, receivable_account_id=inv.receivable_account_id, journal_entry_id=inv.journal_entry_id,
        payment_entry_id=inv.payment_entry_id, created_by=inv.created_by, posted_by=inv.posted_by,
        posted_at=inv.posted_at,
        lines=[
            InvoiceLineResponse(
                id=ln.id, description=ln.description, quantity=float(ln.quantity or 0),
                unit_price=float(ln.unit_price or 0), amount=float(ln.amount or 0),
                income_account_id=ln.income_account_id,
                income_account_name=meta.get(ln.income_account_id, (None, None))[1],
            ) for ln in lines
        ],
        created_at=inv.created_at, org_id=inv.org_id,
    )


async def _load_invoice(db, iid, org_id) -> Invoice:
    inv = (await db.execute(
        select(Invoice).where(Invoice.id == iid, Invoice.org_id == org_id, Invoice.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return inv


@router.get("/invoices", response_model=InvoiceListResponse, dependencies=[_fin_read])
async def list_invoices(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = select(Invoice).where(Invoice.org_id == current_user.org_id, Invoice.is_deleted == False)  # noqa: E712
    if status:
        base = base.where(Invoice.status == status)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(Invoice.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    items = [await _invoice_response(db, inv, current_user.org_id) for inv in rows]
    return InvoiceListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse, dependencies=[_fin_read])
async def get_invoice(invoice_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return await _invoice_response(db, await _load_invoice(db, invoice_id, current_user.org_id), current_user.org_id)


async def _set_invoice_lines(db, inv: Invoice, org_id: str, lines):
    """Validate income accounts + replace the invoice's lines; returns total."""
    total = money(0)
    for ln in lines:
        await _require_account(db, org_id, ln.income_account_id)
        amount = money(ln.quantity) * money(ln.unit_price)
        amount = money(amount)
        db.add(InvoiceLine(
            org_id=org_id, invoice_id=inv.id, description=ln.description,
            quantity=money(ln.quantity), unit_price=money(ln.unit_price), amount=amount,
            income_account_id=ln.income_account_id,
        ))
        total += amount
    return money(total)


@router.post("/invoices", response_model=InvoiceResponse, status_code=201, dependencies=[_fin_write])
async def create_invoice(
    payload: InvoiceCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _require_account(db, current_user.org_id, payload.receivable_account_id)
    if payload.student_id:
        s = (await db.execute(
            select(Student).where(Student.id == payload.student_id, Student.org_id == current_user.org_id)
        )).scalar_one_or_none()
        if not s:
            raise HTTPException(status_code=404, detail="student not found in your organisation.")
    number = (payload.number or f"INV-{uuid.uuid4().hex[:8].upper()}").strip()
    inv = Invoice(
        number=number, customer_name=payload.customer_name, student_id=payload.student_id,
        invoice_date=payload.invoice_date, due_date=payload.due_date, status="draft",
        memo=payload.memo, receivable_account_id=payload.receivable_account_id,
        created_by=current_user.id, org_id=current_user.org_id, total=money(0),
    )
    db.add(inv)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Invoice number '{number}' already exists.")
    inv.total = await _set_invoice_lines(db, inv, current_user.org_id, payload.lines)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="Invoice", resource_id=inv.id, resource_label=f"invoice {inv.number} (draft)", request=request,
    )
    return await _invoice_response(db, inv, current_user.org_id)


@router.patch("/invoices/{invoice_id}", response_model=InvoiceResponse, dependencies=[_fin_write])
async def update_invoice(
    invoice_id: str,
    payload: InvoiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    inv = await _load_invoice(db, invoice_id, current_user.org_id)
    if inv.status != "draft":
        raise HTTPException(status_code=409, detail="Only a draft invoice can be edited. Post a correction instead.")
    data = payload.model_dump(exclude_unset=True)
    if data.get("receivable_account_id"):
        await _require_account(db, current_user.org_id, data["receivable_account_id"])
    for field in ("customer_name", "student_id", "invoice_date", "due_date", "memo", "receivable_account_id"):
        if field in data:
            setattr(inv, field, data[field])
    if payload.lines is not None:
        existing = (await db.execute(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id))).scalars().all()
        for ln in existing:
            await db.delete(ln)
        await db.flush()
        inv.total = await _set_invoice_lines(db, inv, current_user.org_id, payload.lines)
    await db.flush()
    return await _invoice_response(db, inv, current_user.org_id)


@router.delete("/invoices/{invoice_id}", status_code=204, dependencies=[_fin_write])
async def delete_invoice(invoice_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    inv = await _load_invoice(db, invoice_id, current_user.org_id)
    if inv.status != "draft":
        raise HTTPException(status_code=409, detail="Only a draft invoice can be deleted; void a posted invoice instead.")
    inv.is_deleted = True
    inv.deleted_at = datetime.now(timezone.utc)
    await db.flush()


@router.post("/invoices/{invoice_id}/post", response_model=InvoiceResponse, dependencies=[_fin_post])
async def post_invoice(
    invoice_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    inv = await _load_invoice(db, invoice_id, current_user.org_id)
    if inv.status != "draft":
        raise HTTPException(status_code=409, detail=f"Invoice is already {inv.status}.")
    lines = (await db.execute(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id))).scalars().all()
    if not lines:
        raise HTTPException(status_code=422, detail="Cannot post an invoice with no lines.")
    total = money(sum(money(ln.amount) for ln in lines))
    if total <= 0:
        raise HTTPException(status_code=422, detail="Invoice total must be positive to post.")
    # Dr Receivable (total) / Cr each income account (line amount).
    journal_lines = [{"account_id": inv.receivable_account_id, "debit": total, "credit": 0, "description": f"Invoice {inv.number}"}]
    for ln in lines:
        journal_lines.append({"account_id": ln.income_account_id, "debit": 0, "credit": money(ln.amount), "description": ln.description})
    entry = await ledger.post_journal_entry(
        db, org_id=current_user.org_id, entry_date=inv.invoice_date or datetime.now(timezone.utc).date(),
        memo=f"Invoice {inv.number} — {inv.customer_name}", source="invoice", source_id=inv.id,
        lines=journal_lines, actor=current_user, request=request,
    )
    inv.status = "posted"
    inv.total = total
    inv.journal_entry_id = entry.id
    inv.posted_by = current_user.id
    inv.posted_at = datetime.now(timezone.utc)
    await db.flush()
    return await _invoice_response(db, inv, current_user.org_id)


@router.post("/invoices/{invoice_id}/pay", response_model=InvoiceResponse, dependencies=[_fin_post])
async def pay_invoice(
    invoice_id: str,
    payload: PaymentRequest,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    inv = await _load_invoice(db, invoice_id, current_user.org_id)
    if inv.status != "posted":
        raise HTTPException(status_code=409, detail="Only a posted invoice can be paid.")
    await _require_account(db, current_user.org_id, payload.cash_account_id)
    amount = money(payload.amount) if payload.amount is not None else money(inv.total)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Payment amount must be positive.")
    # Dr Cash / Cr Receivable.
    entry = await ledger.post_journal_entry(
        db, org_id=current_user.org_id, entry_date=payload.payment_date or datetime.now(timezone.utc).date(),
        memo=f"Payment for invoice {inv.number}", source="invoice", source_id=inv.id,
        lines=[
            {"account_id": payload.cash_account_id, "debit": amount, "credit": 0, "description": f"Payment {inv.number}"},
            {"account_id": inv.receivable_account_id, "debit": 0, "credit": amount, "description": f"Settle {inv.number}"},
        ],
        actor=current_user, request=request,
    )
    inv.payment_entry_id = entry.id
    if amount >= money(inv.total):
        inv.status = "paid"
    await db.flush()
    return await _invoice_response(db, inv, current_user.org_id)


@router.post("/invoices/{invoice_id}/void", response_model=InvoiceResponse, dependencies=[_fin_post])
async def void_invoice(
    invoice_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    inv = await _load_invoice(db, invoice_id, current_user.org_id)
    if inv.status == "void":
        raise HTTPException(status_code=409, detail="Invoice already void.")
    # Reverse any posted journal entries (immutable correction, never delete).
    for eid in (inv.payment_entry_id, inv.journal_entry_id):
        if eid:
            e = (await db.execute(select(JournalEntry).where(JournalEntry.id == eid))).scalar_one_or_none()
            if e and not e.reversed_by_id:
                await ledger.reverse_entry(db, entry_id=eid, org_id=current_user.org_id, actor=current_user, request=request)
    inv.status = "void"
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="Invoice", resource_id=inv.id, resource_label=f"voided invoice {inv.number}",
        new_values={"status": "void"}, severity="warning", request=request,
    )
    return await _invoice_response(db, inv, current_user.org_id)


# ── Payroll ────────────────────────────────────────────────────────────────────

async def _payroll_response(db: AsyncSession, run: PayrollRun, org_id: str) -> PayrollRunResponse:
    slips = (await db.execute(
        select(SchoolPayslip).where(SchoolPayslip.run_id == run.id).order_by(SchoolPayslip.created_at)
    )).scalars().all()
    return PayrollRunResponse(
        id=run.id, period_label=run.period_label, run_date=run.run_date, status=run.status,
        total_gross=float(run.total_gross or 0), total_deductions=float(run.total_deductions or 0),
        total_net=float(run.total_net or 0), expense_account_id=run.expense_account_id,
        net_account_id=run.net_account_id, deductions_account_id=run.deductions_account_id,
        journal_entry_id=run.journal_entry_id, created_by=run.created_by, approved_by=run.approved_by,
        approved_at=run.approved_at,
        payslips=[
            PayslipResponse(
                id=s.id, staff_user_id=s.staff_user_id, staff_name=s.staff_name,
                gross=float(s.gross or 0), deductions=float(s.deductions or 0), net=float(s.net or 0), notes=s.notes,
            ) for s in slips
        ],
        created_at=run.created_at, org_id=run.org_id,
    )


async def _load_run(db, rid, org_id) -> PayrollRun:
    run = (await db.execute(
        select(PayrollRun).where(PayrollRun.id == rid, PayrollRun.org_id == org_id, PayrollRun.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found.")
    return run


@router.get("/payroll", response_model=PayrollListResponse, dependencies=[_fin_read])
async def list_payroll(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = select(PayrollRun).where(PayrollRun.org_id == current_user.org_id, PayrollRun.is_deleted == False)  # noqa: E712
    if status:
        base = base.where(PayrollRun.status == status)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(PayrollRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    items = [await _payroll_response(db, r, current_user.org_id) for r in rows]
    return PayrollListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/payroll", response_model=PayrollRunResponse, status_code=201, dependencies=[_fin_write])
async def create_payroll(
    payload: PayrollRunCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _require_account(db, current_user.org_id, payload.expense_account_id)
    await _require_account(db, current_user.org_id, payload.net_account_id)
    if payload.deductions_account_id:
        await _require_account(db, current_user.org_id, payload.deductions_account_id)
    run = PayrollRun(
        period_label=payload.period_label, run_date=payload.run_date, status="draft",
        expense_account_id=payload.expense_account_id, net_account_id=payload.net_account_id,
        deductions_account_id=payload.deductions_account_id, created_by=current_user.id,
        org_id=current_user.org_id, total_gross=money(0), total_deductions=money(0), total_net=money(0),
    )
    db.add(run)
    await db.flush()
    tg = td = tn = money(0)
    for s in payload.payslips:
        gross = money(s.gross)
        deductions = money(s.deductions)
        net = money(gross - deductions)
        db.add(SchoolPayslip(
            org_id=current_user.org_id, run_id=run.id, staff_user_id=s.staff_user_id, staff_name=s.staff_name,
            gross=gross, deductions=deductions, net=net, notes=s.notes,
        ))
        tg += gross; td += deductions; tn += net
    run.total_gross, run.total_deductions, run.total_net = money(tg), money(td), money(tn)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="PayrollRun", resource_id=run.id, resource_label=f"payroll run {run.period_label} (draft)", request=request,
    )
    return await _payroll_response(db, run, current_user.org_id)


@router.post("/payroll/{run_id}/approve", response_model=PayrollRunResponse, dependencies=[_fin_post])
async def approve_payroll(
    run_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Two-person control: the approver (payments:post) must NOT be the creator.
    Approval posts the balanced payroll journal — atomic, audited."""
    run = await _load_run(db, run_id, current_user.org_id)
    if run.status != "draft":
        raise HTTPException(status_code=409, detail=f"Payroll run is already {run.status}.")
    if run.created_by and run.created_by == current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Segregation of duties: payroll must be approved by someone other than its creator.",
        )
    slips = (await db.execute(select(SchoolPayslip).where(SchoolPayslip.run_id == run.id))).scalars().all()
    if not slips:
        raise HTTPException(status_code=422, detail="Cannot approve a payroll run with no payslips.")
    gross = money(sum(money(s.gross) for s in slips))
    deductions = money(sum(money(s.deductions) for s in slips))
    net = money(gross - deductions)
    if gross <= 0:
        raise HTTPException(status_code=422, detail="Payroll gross must be positive.")
    # Dr Salary Expense (gross) / Cr Net Pay (net) [+ Cr Deductions Payable].
    lines = [
        {"account_id": run.expense_account_id, "debit": gross, "credit": 0, "description": "Salary expense"},
        {"account_id": run.net_account_id, "debit": 0, "credit": net, "description": "Net pay"},
    ]
    if deductions > 0:
        acct = run.deductions_account_id or run.net_account_id
        lines.append({"account_id": acct, "debit": 0, "credit": deductions, "description": "Deductions payable"})
    entry = await ledger.post_journal_entry(
        db, org_id=current_user.org_id, entry_date=run.run_date or datetime.now(timezone.utc).date(),
        memo=f"Payroll {run.period_label}", source="payroll", source_id=run.id,
        lines=lines, actor=current_user, request=request,
    )
    run.status = "posted"
    run.total_gross, run.total_deductions, run.total_net = gross, deductions, net
    run.journal_entry_id = entry.id
    run.approved_by = current_user.id
    run.approved_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="PayrollRun", resource_id=run.id, resource_label=f"approved+posted payroll {run.period_label}",
        old_values={"status": "draft"}, new_values={"status": "posted", "approved_by": current_user.id},
        metadata={"created_by": run.created_by}, severity="warning", request=request,
    )
    return await _payroll_response(db, run, current_user.org_id)


@router.post("/payroll/{run_id}/void", response_model=PayrollRunResponse, dependencies=[_fin_post])
async def void_payroll(
    run_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    run = await _load_run(db, run_id, current_user.org_id)
    if run.status == "void":
        raise HTTPException(status_code=409, detail="Payroll run already void.")
    if run.journal_entry_id:
        e = (await db.execute(select(JournalEntry).where(JournalEntry.id == run.journal_entry_id))).scalar_one_or_none()
        if e and not e.reversed_by_id:
            await ledger.reverse_entry(db, entry_id=run.journal_entry_id, org_id=current_user.org_id, actor=current_user, request=request)
    run.status = "void"
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="PayrollRun", resource_id=run.id, resource_label=f"voided payroll {run.period_label}",
        new_values={"status": "void"}, severity="warning", request=request,
    )
    return await _payroll_response(db, run, current_user.org_id)


@router.delete("/payroll/{run_id}", status_code=204, dependencies=[_fin_write])
async def delete_payroll(run_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    run = await _load_run(db, run_id, current_user.org_id)
    if run.status != "draft":
        raise HTTPException(status_code=409, detail="Only a draft run can be deleted; void a posted run instead.")
    run.is_deleted = True
    run.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Salary Advance ────────────────────────────────────────────────────────────
# A salary advance is a short-term loan to a staff member, recovered later (via
# payroll or cash). It rides the SAME ledger engine payroll uses, so every
# disbursement/repayment is balanced double-entry, period-lock-aware, immutable
# and audited. Lifecycle: pending → approve(=DISBURSE) → repay… → repaid.
#   Disburse:  Dr Staff Advances (asset)  / Cr Cash        (school pays out now)
#   Repay:     Dr Cash                    / Cr Staff Advances (recovering it)

STAFF_ADVANCE_ACCOUNT_CODE = "1300"
STAFF_ADVANCE_ACCOUNT_NAME = "Staff Advances"


async def _ensure_advance_account(db: AsyncSession, org_id: str) -> LedgerAccount:
    """Find-or-create the dedicated 'Staff Advances' asset account (code 1300).
    Advances are receivables from staff, so they live as an asset until recovered."""
    a = (await db.execute(
        select(LedgerAccount).where(
            LedgerAccount.org_id == org_id,
            LedgerAccount.code == STAFF_ADVANCE_ACCOUNT_CODE,
            LedgerAccount.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if a:
        return a
    a = LedgerAccount(
        code=STAFF_ADVANCE_ACCOUNT_CODE, name=STAFF_ADVANCE_ACCOUNT_NAME, type="asset",
        description="Advances paid to staff, recovered via payroll or cash.", org_id=org_id,
    )
    db.add(a)
    await db.flush()
    return a


async def _pick_cash_account(db: AsyncSession, org_id: str, exclude_id: str | None) -> LedgerAccount | None:
    """Pick a default cash/bank asset account (the first asset that isn't Staff
    Advances). Used when the caller doesn't name one explicitly."""
    accts = (await db.execute(
        select(LedgerAccount).where(
            LedgerAccount.org_id == org_id,
            LedgerAccount.type == "asset",
            LedgerAccount.is_active == True,   # noqa: E712
            LedgerAccount.is_deleted == False)  # noqa: E712
        .order_by(LedgerAccount.code)
    )).scalars().all()
    for a in accts:
        if a.id != exclude_id:
            return a
    return None


def _advance_response(a: SalaryAdvance) -> SalaryAdvanceResponse:
    outstanding = money(money(a.amount) - money(a.amount_repaid))
    return SalaryAdvanceResponse(
        id=a.id, staff_user_id=a.staff_user_id, staff_name=a.staff_name, amount=float(a.amount),
        reason=a.reason, status=a.status, amount_repaid=float(a.amount_repaid), outstanding=float(outstanding),
        requested_by=a.requested_by, approved_by=a.approved_by, approved_at=a.approved_at,
        disburse_entry_id=a.disburse_entry_id, notes=a.notes, created_at=a.created_at, org_id=a.org_id,
    )


async def _load_advance(db: AsyncSession, advance_id: str, org_id: str) -> SalaryAdvance:
    a = (await db.execute(
        select(SalaryAdvance).where(
            SalaryAdvance.id == advance_id, SalaryAdvance.org_id == org_id,
            SalaryAdvance.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Salary advance not found.")
    return a


@router.get("/salary-advances", response_model=list[SalaryAdvanceResponse], dependencies=[_fin_read])
async def list_salary_advances(
    status: str | None = Query(None, description="Filter by status: pending|approved|rejected|repaid"),
    staff_user_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(SalaryAdvance).where(
        SalaryAdvance.org_id == current_user.org_id, SalaryAdvance.is_deleted == False)  # noqa: E712
    if status:
        q = q.where(SalaryAdvance.status == status)
    if staff_user_id:
        q = q.where(SalaryAdvance.staff_user_id == staff_user_id)
    rows = (await db.execute(q.order_by(SalaryAdvance.created_at.desc()))).scalars().all()
    return [_advance_response(a) for a in rows]


@router.post("/salary-advances", response_model=SalaryAdvanceResponse, status_code=201, dependencies=[_fin_write])
async def create_salary_advance(
    payload: SalaryAdvanceCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Request an advance for a staff member. Creates a PENDING record only — no
    money moves until it's approved (which disburses through the ledger)."""
    staff = (await db.execute(
        select(User).where(User.id == payload.staff_user_id, User.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found in your organisation.")
    a = SalaryAdvance(
        staff_user_id=staff.id, staff_name=staff.full_name, amount=money(payload.amount),
        reason=payload.reason, notes=payload.notes, status="pending", amount_repaid=money(0),
        requested_by=current_user.id, org_id=current_user.org_id,
    )
    db.add(a)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="SalaryAdvance", resource_id=a.id,
        resource_label=f"salary advance request {a.staff_name} {money(a.amount)}", request=request,
    )
    return _advance_response(a)


@router.post("/salary-advances/{advance_id}/approve", response_model=SalaryAdvanceResponse, dependencies=[_fin_post])
async def approve_salary_advance(
    advance_id: str,
    payload: SalaryAdvanceApprove = SalaryAdvanceApprove(),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Approve DISBURSES the advance: posts Dr Staff Advances / Cr Cash through the
    ledger. Two-person control (like payroll): the approver must NOT be the requester."""
    a = await _load_advance(db, advance_id, current_user.org_id)
    if a.status != "pending":
        raise HTTPException(status_code=409, detail=f"Advance is already {a.status}.")
    if a.requested_by and a.requested_by == current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Segregation of duties: an advance must be approved by someone other than its requester.",
        )
    amount = money(a.amount)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Advance amount must be positive.")
    advance_acct = await _ensure_advance_account(db, current_user.org_id)
    if payload and payload.cash_account_id:
        cash = await _require_account(db, current_user.org_id, payload.cash_account_id)
    else:
        cash = await _pick_cash_account(db, current_user.org_id, advance_acct.id)
    if not cash:
        raise HTTPException(
            status_code=422,
            detail="No cash/bank asset account available to disburse from. Create one under Chart of Accounts first.",
        )
    # Dr Staff Advances (asset ↑) / Cr Cash (asset ↓) — the school pays out now.
    lines = [
        {"account_id": advance_acct.id, "debit": amount, "credit": 0, "description": f"Advance to {a.staff_name}"},
        {"account_id": cash.id, "debit": 0, "credit": amount, "description": "Cash disbursed"},
    ]
    entry = await ledger.post_journal_entry(
        db, org_id=current_user.org_id, entry_date=datetime.now(timezone.utc).date(),
        memo=f"Salary advance to {a.staff_name}", source="salary_advance", source_id=a.id,
        lines=lines, actor=current_user, request=request,
    )
    a.status = "approved"
    a.approved_by = current_user.id
    a.approved_at = datetime.now(timezone.utc)
    a.disburse_entry_id = entry.id
    a.advance_account_id = advance_acct.id
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="SalaryAdvance", resource_id=a.id,
        resource_label=f"approved+disbursed advance {a.staff_name} {amount}",
        old_values={"status": "pending"}, new_values={"status": "approved", "approved_by": current_user.id},
        metadata={"requested_by": a.requested_by, "journal_entry_id": entry.id}, severity="warning", request=request,
    )
    return _advance_response(a)


@router.post("/salary-advances/{advance_id}/reject", response_model=SalaryAdvanceResponse, dependencies=[_fin_post])
async def reject_salary_advance(
    advance_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Reject a pending request. No ledger impact — nothing was ever disbursed."""
    a = await _load_advance(db, advance_id, current_user.org_id)
    if a.status != "pending":
        raise HTTPException(status_code=409, detail=f"Only a pending advance can be rejected (this one is {a.status}).")
    a.status = "rejected"
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="SalaryAdvance", resource_id=a.id, resource_label=f"rejected advance {a.staff_name}",
        old_values={"status": "pending"}, new_values={"status": "rejected"}, severity="warning", request=request,
    )
    return _advance_response(a)


@router.post("/salary-advances/{advance_id}/repay", response_model=SalaryAdvanceResponse, dependencies=[_fin_post])
async def repay_salary_advance(
    advance_id: str,
    payload: SalaryAdvanceRepay,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Record a repayment against a disbursed advance. Posts Dr Cash / Cr Staff
    Advances and accrues ``amount_repaid``. Marks the advance ``repaid`` once
    fully recovered. Over-repayment is rejected (422)."""
    a = await _load_advance(db, advance_id, current_user.org_id)
    if a.status != "approved":
        raise HTTPException(
            status_code=409,
            detail="Only an approved (disbursed) advance can be repaid.",
        )
    outstanding = money(money(a.amount) - money(a.amount_repaid))
    amt = money(payload.amount)
    if amt <= 0:
        raise HTTPException(status_code=422, detail="Repayment amount must be positive.")
    if amt > outstanding:
        raise HTTPException(
            status_code=422,
            detail=f"Repayment {amt} exceeds outstanding balance {outstanding}.",
        )
    advance_acct = None
    if a.advance_account_id:
        advance_acct = (await db.execute(
            select(LedgerAccount).where(
                LedgerAccount.id == a.advance_account_id, LedgerAccount.org_id == current_user.org_id)
        )).scalar_one_or_none()
    if not advance_acct:
        advance_acct = await _ensure_advance_account(db, current_user.org_id)
    if payload.cash_account_id:
        cash = await _require_account(db, current_user.org_id, payload.cash_account_id)
    else:
        cash = await _pick_cash_account(db, current_user.org_id, advance_acct.id)
    if not cash:
        raise HTTPException(
            status_code=422,
            detail="No cash/bank asset account available to receive repayment. Create one under Chart of Accounts first.",
        )
    # Dr Cash (asset ↑) / Cr Staff Advances (asset ↓) — recovering the advance.
    lines = [
        {"account_id": cash.id, "debit": amt, "credit": 0, "description": f"Advance repayment {a.staff_name}"},
        {"account_id": advance_acct.id, "debit": 0, "credit": amt, "description": "Advance recovered"},
    ]
    entry = await ledger.post_journal_entry(
        db, org_id=current_user.org_id, entry_date=datetime.now(timezone.utc).date(),
        memo=f"Salary advance repayment ({payload.method}) — {a.staff_name}",
        source="salary_advance_repay", source_id=a.id, lines=lines, actor=current_user, request=request,
    )
    db.add(SalaryAdvanceRepayment(
        org_id=current_user.org_id, advance_id=a.id, amount=amt, method=payload.method,
        payroll_run_id=payload.payroll_run_id, journal_entry_id=entry.id, recorded_by=current_user.id,
    ))
    a.amount_repaid = money(money(a.amount_repaid) + amt)
    fully_paid = money(a.amount_repaid) >= money(a.amount)
    if fully_paid:
        a.status = "repaid"
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="SalaryAdvance", resource_id=a.id,
        resource_label=f"repayment {amt} on advance {a.staff_name}",
        new_values={"amount_repaid": str(a.amount_repaid), "status": a.status},
        metadata={"method": payload.method, "journal_entry_id": entry.id}, request=request,
    )
    return _advance_response(a)


@router.delete("/salary-advances/{advance_id}", status_code=204, dependencies=[_fin_write])
async def delete_salary_advance(
    advance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a request that never disbursed. An approved (disbursed) advance
    cannot be deleted — its ledger entry is immutable; repay it instead."""
    a = await _load_advance(db, advance_id, current_user.org_id)
    if a.status not in ("pending", "rejected"):
        raise HTTPException(
            status_code=409,
            detail="A disbursed advance cannot be deleted; repay it to close the balance instead.",
        )
    a.is_deleted = True
    a.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Bonus / Reduction Pack (pay adjustments) ────────────────────────────────────
# A "pack" is a batch of one-off pay adjustments applied across staff — either
# BONUSES (extra pay, an expense) or REDUCTIONS (amounts withheld/recovered). It
# rides the SAME ledger engine + two-person control as payroll, but does NOT touch
# the payroll approval flow (recorded independently, reconciled into pay manually).
#   bonus     → Dr expense_account (P&L)         / Cr settle_account (cash/payable)
#   reduction → Dr settle_account (cash/payable) / Cr expense_account (income/offset)


async def _load_pack(db: AsyncSession, pack_id: str, org_id: str) -> PayAdjustmentPack:
    p = (await db.execute(
        select(PayAdjustmentPack).where(
            PayAdjustmentPack.id == pack_id, PayAdjustmentPack.org_id == org_id,
            PayAdjustmentPack.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Pay adjustment pack not found.")
    return p


async def _pack_response(db: AsyncSession, p: PayAdjustmentPack) -> PayAdjustmentResponse:
    items = (await db.execute(
        select(PayAdjustmentItem).where(PayAdjustmentItem.pack_id == p.id).order_by(PayAdjustmentItem.created_at)
    )).scalars().all()
    return PayAdjustmentResponse(
        id=p.id, label=p.label, kind=p.kind, status=p.status, total_amount=float(p.total_amount),
        reason=p.reason, expense_account_id=p.expense_account_id, settle_account_id=p.settle_account_id,
        journal_entry_id=p.journal_entry_id, created_by=p.created_by, approved_by=p.approved_by,
        approved_at=p.approved_at, created_at=p.created_at, org_id=p.org_id,
        items=[PayAdjustmentItemResponse(
            id=i.id, staff_user_id=i.staff_user_id, staff_name=i.staff_name, amount=float(i.amount), note=i.note,
        ) for i in items],
    )


@router.get("/pay-adjustments", response_model=list[PayAdjustmentResponse], dependencies=[_fin_read])
async def list_pay_adjustments(
    kind: str | None = Query(None, description="bonus | reduction"),
    status: str | None = Query(None, description="draft | approved | void"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(PayAdjustmentPack).where(
        PayAdjustmentPack.org_id == current_user.org_id, PayAdjustmentPack.is_deleted == False)  # noqa: E712
    if kind:
        q = q.where(PayAdjustmentPack.kind == kind)
    if status:
        q = q.where(PayAdjustmentPack.status == status)
    packs = (await db.execute(q.order_by(PayAdjustmentPack.created_at.desc()))).scalars().all()
    return [await _pack_response(db, p) for p in packs]


@router.post("/pay-adjustments", response_model=PayAdjustmentResponse, status_code=201, dependencies=[_fin_write])
async def create_pay_adjustment(
    payload: PayAdjustmentCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a DRAFT pack of bonuses/reductions. No money moves until it's approved."""
    if payload.kind not in PAY_ADJUSTMENT_KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of {sorted(PAY_ADJUSTMENT_KINDS)}.")
    await _require_account(db, current_user.org_id, payload.expense_account_id)
    await _require_account(db, current_user.org_id, payload.settle_account_id)
    if payload.expense_account_id == payload.settle_account_id:
        raise HTTPException(status_code=422, detail="The P&L account and the cash/payable account must differ.")
    pack = PayAdjustmentPack(
        label=payload.label, kind=payload.kind, status="draft", reason=payload.reason,
        expense_account_id=payload.expense_account_id, settle_account_id=payload.settle_account_id,
        created_by=current_user.id, org_id=current_user.org_id, total_amount=money(0),
    )
    db.add(pack)
    await db.flush()
    total = money(0)
    for it in payload.items:
        amt = money(it.amount)
        db.add(PayAdjustmentItem(
            org_id=current_user.org_id, pack_id=pack.id, staff_user_id=it.staff_user_id,
            staff_name=it.staff_name, amount=amt, note=it.note,
        ))
        total += amt
    pack.total_amount = money(total)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="PayAdjustmentPack", resource_id=pack.id,
        resource_label=f"{pack.kind} pack '{pack.label}' (draft) {pack.total_amount}", request=request,
    )
    return await _pack_response(db, pack)


@router.post("/pay-adjustments/{pack_id}/approve", response_model=PayAdjustmentResponse, dependencies=[_fin_post])
async def approve_pay_adjustment(
    pack_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Approve POSTS the pack to the ledger. Two-person control: approver != creator."""
    pack = await _load_pack(db, pack_id, current_user.org_id)
    if pack.status != "draft":
        raise HTTPException(status_code=409, detail=f"Pack is already {pack.status}.")
    if pack.created_by and pack.created_by == current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Segregation of duties: a pay adjustment must be approved by someone other than its creator.",
        )
    items = (await db.execute(select(PayAdjustmentItem).where(PayAdjustmentItem.pack_id == pack.id))).scalars().all()
    if not items:
        raise HTTPException(status_code=422, detail="Cannot approve a pack with no line items.")
    total = money(sum(money(i.amount) for i in items))
    if total <= 0:
        raise HTTPException(status_code=422, detail="Pack total must be positive.")
    exp = await _require_account(db, current_user.org_id, pack.expense_account_id)
    settle = await _require_account(db, current_user.org_id, pack.settle_account_id)
    if pack.kind == "bonus":
        # Extra pay to staff: Dr Bonus Expense / Cr Cash (or payable).
        lines = [
            {"account_id": exp.id, "debit": total, "credit": 0, "description": f"Bonus: {pack.label}"},
            {"account_id": settle.id, "debit": 0, "credit": total, "description": "Bonus settlement"},
        ]
    else:
        # Amount withheld/recovered: Dr Cash (or payable) / Cr Income/offset.
        lines = [
            {"account_id": settle.id, "debit": total, "credit": 0, "description": f"Reduction: {pack.label}"},
            {"account_id": exp.id, "debit": 0, "credit": total, "description": "Reduction offset"},
        ]
    entry = await ledger.post_journal_entry(
        db, org_id=current_user.org_id, entry_date=datetime.now(timezone.utc).date(),
        memo=f"{pack.kind.title()} pack: {pack.label}", source="pay_adjustment", source_id=pack.id,
        lines=lines, actor=current_user, request=request,
    )
    pack.status = "approved"
    pack.total_amount = total
    pack.journal_entry_id = entry.id
    pack.approved_by = current_user.id
    pack.approved_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="PayAdjustmentPack", resource_id=pack.id,
        resource_label=f"approved+posted {pack.kind} pack '{pack.label}' {total}",
        old_values={"status": "draft"}, new_values={"status": "approved", "approved_by": current_user.id},
        metadata={"created_by": pack.created_by, "journal_entry_id": entry.id}, severity="warning", request=request,
    )
    return await _pack_response(db, pack)


@router.post("/pay-adjustments/{pack_id}/void", response_model=PayAdjustmentResponse, dependencies=[_fin_post])
async def void_pay_adjustment(
    pack_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Void an approved pack — reverses its ledger entry (immutable audit trail)."""
    pack = await _load_pack(db, pack_id, current_user.org_id)
    if pack.status == "void":
        raise HTTPException(status_code=409, detail="Pack already void.")
    if pack.journal_entry_id:
        e = (await db.execute(select(JournalEntry).where(JournalEntry.id == pack.journal_entry_id))).scalar_one_or_none()
        if e and not e.reversed_by_id:
            await ledger.reverse_entry(db, entry_id=pack.journal_entry_id, org_id=current_user.org_id, actor=current_user, request=request)
    pack.status = "void"
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="PayAdjustmentPack", resource_id=pack.id,
        resource_label=f"voided {pack.kind} pack '{pack.label}'",
        new_values={"status": "void"}, severity="warning", request=request,
    )
    return await _pack_response(db, pack)


@router.delete("/pay-adjustments/{pack_id}", status_code=204, dependencies=[_fin_write])
async def delete_pay_adjustment(
    pack_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a draft pack. A posted (approved) pack must be voided instead."""
    pack = await _load_pack(db, pack_id, current_user.org_id)
    if pack.status != "draft":
        raise HTTPException(status_code=409, detail="Only a draft pack can be deleted; void a posted pack instead.")
    pack.is_deleted = True
    pack.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Requisitions / Request Form ─────────────────────────────────────────────────
# A requisition is a staff request to spend, routed through approval. The Request
# Form (frontend) POSTs here to raise a DRAFT; Requisitions (frontend) lists +
# approves/rejects/voids. Approve POSTS the spend to the ledger through the SAME
# engine payroll uses, with two-person control (approver ≠ requester):
#   approve → Dr expense_account / Cr settle_account (cash|payable)


async def _load_requisition(db: AsyncSession, req_id: str, org_id: str) -> Requisition:
    r = (await db.execute(
        select(Requisition).where(
            Requisition.id == req_id, Requisition.org_id == org_id,
            Requisition.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Requisition not found.")
    return r


async def _requisition_response(db: AsyncSession, r: Requisition) -> RequisitionResponse:
    items = (await db.execute(
        select(RequisitionItem).where(RequisitionItem.requisition_id == r.id).order_by(RequisitionItem.created_at)
    )).scalars().all()
    return RequisitionResponse(
        id=r.id, title=r.title, department=r.department, category=r.category, status=r.status,
        total_amount=float(r.total_amount), justification=r.justification, notes=r.notes,
        expense_account_id=r.expense_account_id, settle_account_id=r.settle_account_id,
        journal_entry_id=r.journal_entry_id, requested_by=r.requested_by, approved_by=r.approved_by,
        approved_at=r.approved_at, created_at=r.created_at, org_id=r.org_id,
        items=[RequisitionItemResponse(
            id=i.id, description=i.description, quantity=float(i.quantity), unit_cost=float(i.unit_cost),
            amount=float(i.amount), note=i.note,
        ) for i in items],
    )


@router.get("/requisitions", response_model=list[RequisitionResponse], dependencies=[_fin_read])
async def list_requisitions(
    status: str | None = Query(None, description="draft | approved | rejected | void"),
    department: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(Requisition).where(
        Requisition.org_id == current_user.org_id, Requisition.is_deleted == False)  # noqa: E712
    if status:
        q = q.where(Requisition.status == status)
    if department:
        q = q.where(Requisition.department == department)
    rows = (await db.execute(q.order_by(Requisition.created_at.desc()))).scalars().all()
    return [await _requisition_response(db, r) for r in rows]


@router.post("/requisitions", response_model=RequisitionResponse, status_code=201, dependencies=[_fin_write])
async def create_requisition(
    payload: RequisitionCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Raise a DRAFT requisition (the Request Form intake). No money moves until
    it's approved (which posts the spend to the ledger)."""
    await _require_account(db, current_user.org_id, payload.expense_account_id)
    await _require_account(db, current_user.org_id, payload.settle_account_id)
    if payload.expense_account_id == payload.settle_account_id:
        raise HTTPException(status_code=422, detail="The expense account and the cash/payable account must differ.")
    req = Requisition(
        title=payload.title, department=payload.department, category=payload.category, status="draft",
        justification=payload.justification, notes=payload.notes,
        expense_account_id=payload.expense_account_id, settle_account_id=payload.settle_account_id,
        requested_by=current_user.id, org_id=current_user.org_id, total_amount=money(0),
    )
    db.add(req)
    await db.flush()
    total = money(0)
    for it in payload.items:
        qty = money(it.quantity)
        unit = money(it.unit_cost)
        amt = money(qty * unit)
        db.add(RequisitionItem(
            org_id=current_user.org_id, requisition_id=req.id, description=it.description,
            quantity=qty, unit_cost=unit, amount=amt, note=it.note,
        ))
        total += amt
    if total <= 0:
        raise HTTPException(status_code=422, detail="Requisition total must be positive (set a quantity and unit cost).")
    req.total_amount = money(total)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="Requisition", resource_id=req.id,
        resource_label=f"requisition '{req.title}' (draft) {req.total_amount}", request=request,
    )
    return await _requisition_response(db, req)


@router.post("/requisitions/{req_id}/approve", response_model=RequisitionResponse, dependencies=[_fin_post])
async def approve_requisition(
    req_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Approve POSTS the spend to the ledger. Two-person control: approver != requester."""
    req = await _load_requisition(db, req_id, current_user.org_id)
    if req.status != "draft":
        raise HTTPException(status_code=409, detail=f"Requisition is already {req.status}.")
    if req.requested_by and req.requested_by == current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Segregation of duties: a requisition must be approved by someone other than its requester.",
        )
    items = (await db.execute(select(RequisitionItem).where(RequisitionItem.requisition_id == req.id))).scalars().all()
    if not items:
        raise HTTPException(status_code=422, detail="Cannot approve a requisition with no line items.")
    total = money(sum(money(i.amount) for i in items))
    if total <= 0:
        raise HTTPException(status_code=422, detail="Requisition total must be positive.")
    exp = await _require_account(db, current_user.org_id, req.expense_account_id)
    settle = await _require_account(db, current_user.org_id, req.settle_account_id)
    # Dr Expense (total) / Cr Cash|Payable (total) — the spend is booked on approval.
    lines = [
        {"account_id": exp.id, "debit": total, "credit": 0, "description": f"Requisition: {req.title}"},
        {"account_id": settle.id, "debit": 0, "credit": total, "description": "Requisition settlement"},
    ]
    entry = await ledger.post_journal_entry(
        db, org_id=current_user.org_id, entry_date=datetime.now(timezone.utc).date(),
        memo=f"Requisition: {req.title}", source="requisition", source_id=req.id,
        lines=lines, actor=current_user, request=request,
    )
    req.status = "approved"
    req.total_amount = total
    req.journal_entry_id = entry.id
    req.approved_by = current_user.id
    req.approved_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="Requisition", resource_id=req.id,
        resource_label=f"approved+posted requisition '{req.title}' {total}",
        old_values={"status": "draft"}, new_values={"status": "approved", "approved_by": current_user.id},
        metadata={"requested_by": req.requested_by, "journal_entry_id": entry.id}, severity="warning", request=request,
    )
    return await _requisition_response(db, req)


@router.post("/requisitions/{req_id}/reject", response_model=RequisitionResponse, dependencies=[_fin_post])
async def reject_requisition(
    req_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Reject a draft requisition. No ledger impact — nothing was spent."""
    req = await _load_requisition(db, req_id, current_user.org_id)
    if req.status != "draft":
        raise HTTPException(status_code=409, detail=f"Only a draft requisition can be rejected (this one is {req.status}).")
    req.status = "rejected"
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="Requisition", resource_id=req.id, resource_label=f"rejected requisition '{req.title}'",
        old_values={"status": "draft"}, new_values={"status": "rejected"}, severity="warning", request=request,
    )
    return await _requisition_response(db, req)


@router.post("/requisitions/{req_id}/void", response_model=RequisitionResponse, dependencies=[_fin_post])
async def void_requisition(
    req_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Void an approved requisition — reverses its ledger entry (immutable trail)."""
    req = await _load_requisition(db, req_id, current_user.org_id)
    if req.status == "void":
        raise HTTPException(status_code=409, detail="Requisition already void.")
    if req.status != "approved":
        raise HTTPException(status_code=409, detail="Only an approved requisition can be voided.")
    if req.journal_entry_id:
        e = (await db.execute(select(JournalEntry).where(JournalEntry.id == req.journal_entry_id))).scalar_one_or_none()
        if e and not e.reversed_by_id:
            await ledger.reverse_entry(db, entry_id=req.journal_entry_id, org_id=current_user.org_id, actor=current_user, request=request)
    req.status = "void"
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="Requisition", resource_id=req.id, resource_label=f"voided requisition '{req.title}'",
        new_values={"status": "void"}, severity="warning", request=request,
    )
    return await _requisition_response(db, req)


@router.delete("/requisitions/{req_id}", status_code=204, dependencies=[_fin_write])
async def delete_requisition(
    req_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a requisition that never posted (draft or rejected). An approved one
    must be voided instead — its ledger entry is immutable."""
    req = await _load_requisition(db, req_id, current_user.org_id)
    if req.status not in ("draft", "rejected"):
        raise HTTPException(status_code=409, detail="An approved requisition cannot be deleted; void it instead.")
    req.is_deleted = True
    req.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Fee Discounts (Manage Discounts) ────────────────────────────────────────────
# A discount/scholarship/waiver granted to a student. Approval does BOTH: it reduces
# the student's fee record (visible to parents in Fee Management) AND posts a ledger
# contra Dr Fee Discounts / Cr Accounts Receivable (visible in Finance Reports).
# RBAC: propose = payments:write · approve/reject/void = payments:post (approver ≠
# proposer). The list is gated payments:WRITE (not read) so parents — who hold
# payments:read for their own fees — can't see other families' discounts; a parent
# sees only their own reduced balance via Fee Management.

FEE_DISCOUNT_ACCOUNT_CODE = "5900"
FEE_DISCOUNT_ACCOUNT_NAME = "Fee Discounts & Concessions"
RECEIVABLE_ACCOUNT_CODE = "1100"
RECEIVABLE_ACCOUNT_NAME = "Accounts Receivable"


async def _ensure_account_by_code(db: AsyncSession, org_id: str, code: str, name: str, type_: str) -> LedgerAccount:
    a = (await db.execute(
        select(LedgerAccount).where(
            LedgerAccount.org_id == org_id, LedgerAccount.code == code,
            LedgerAccount.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if a:
        return a
    a = LedgerAccount(code=code, name=name, type=type_, org_id=org_id)
    db.add(a)
    await db.flush()
    return a


def _recompute_fee_record(fr: StudentFeeRecord) -> None:
    """outstanding = total − paid − discount (floored at 0); status derived."""
    total = money(fr.total_fee or 0)
    paid = money(fr.paid_amount or 0)
    disc = money(fr.discount_amount or 0)
    out = total - paid - disc
    if out < 0:
        out = money(0)
    fr.outstanding_balance = out
    if out <= 0:
        fr.is_paid = True
        fr.payment_status = "paid"
    elif paid > 0:
        fr.is_paid = False
        fr.payment_status = "partial"
    else:
        fr.is_paid = False
        fr.payment_status = "unpaid"


async def _latest_fee_record(db: AsyncSession, org_id: str, student_id: str) -> StudentFeeRecord | None:
    return (await db.execute(
        select(StudentFeeRecord).where(
            StudentFeeRecord.org_id == org_id, StudentFeeRecord.student_id == student_id,
            StudentFeeRecord.is_deleted == False)  # noqa: E712
        .order_by(StudentFeeRecord.created_at.desc())
    )).scalars().first()


async def _load_discount(db: AsyncSession, discount_id: str, org_id: str) -> FeeDiscount:
    d = (await db.execute(
        select(FeeDiscount).where(
            FeeDiscount.id == discount_id, FeeDiscount.org_id == org_id,
            FeeDiscount.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Discount not found.")
    return d


def _discount_response(d: FeeDiscount) -> DiscountResponse:
    return DiscountResponse(
        id=d.id, student_id=d.student_id, student_name=d.student_name, fee_record_id=d.fee_record_id,
        discount_type=d.discount_type, value=float(d.value), amount=float(d.amount), reason=d.reason,
        status=d.status, proposed_by=d.proposed_by, approved_by=d.approved_by, approved_at=d.approved_at,
        journal_entry_id=d.journal_entry_id, created_at=d.created_at, org_id=d.org_id,
    )


@router.get("/discounts", response_model=list[DiscountResponse], dependencies=[_fin_write])
async def list_discounts(
    status: str | None = Query(None, description="draft | approved | rejected | void"),
    student_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(FeeDiscount).where(
        FeeDiscount.org_id == current_user.org_id, FeeDiscount.is_deleted == False)  # noqa: E712
    if status:
        q = q.where(FeeDiscount.status == status)
    if student_id:
        q = q.where(FeeDiscount.student_id == student_id)
    rows = (await db.execute(q.order_by(FeeDiscount.created_at.desc()))).scalars().all()
    return [_discount_response(d) for d in rows]


@router.post("/discounts", response_model=DiscountResponse, status_code=201, dependencies=[_fin_write])
async def create_discount(
    payload: DiscountCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Propose a DRAFT discount. Nothing changes until it's approved."""
    if payload.discount_type not in DISCOUNT_TYPES:
        raise HTTPException(status_code=422, detail=f"discount_type must be one of {sorted(DISCOUNT_TYPES)}.")
    student = (await db.execute(
        select(Student).where(Student.id == payload.student_id, Student.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found in your organisation.")
    fr = await _latest_fee_record(db, current_user.org_id, student.id)
    if not fr:
        raise HTTPException(status_code=422, detail="This student has no fee record to apply a discount to.")
    total = money(fr.total_fee or 0)
    outstanding = money(fr.outstanding_balance or 0)
    if payload.discount_type == "percent":
        amount = money(total * money(payload.value) / money(100))
    else:
        amount = money(payload.value)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Computed discount must be positive.")
    if amount > outstanding:
        raise HTTPException(
            status_code=422,
            detail=f"Discount {amount} exceeds the student's outstanding balance {outstanding}.",
        )
    student_name = " ".join(p for p in [getattr(student, "first_name", None), getattr(student, "last_name", None)] if p) or None
    d = FeeDiscount(
        student_id=student.id, student_name=student_name, fee_record_id=fr.id,
        discount_type=payload.discount_type, value=money(payload.value), amount=amount,
        reason=payload.reason, notes=payload.notes, status="draft",
        proposed_by=current_user.id, org_id=current_user.org_id,
    )
    db.add(d)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="FeeDiscount", resource_id=d.id,
        resource_label=f"discount {amount} for {student_name} (draft)", request=request,
    )
    return _discount_response(d)


@router.post("/discounts/{discount_id}/approve", response_model=DiscountResponse, dependencies=[_fin_post])
async def approve_discount(
    discount_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Approve APPLIES the discount: reduces the student's fee record AND posts the
    ledger contra. Two-person control: approver ≠ proposer."""
    d = await _load_discount(db, discount_id, current_user.org_id)
    if d.status != "draft":
        raise HTTPException(status_code=409, detail=f"Discount is already {d.status}.")
    if d.proposed_by and d.proposed_by == current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Segregation of duties: a discount must be approved by someone other than its proposer.",
        )
    amount = money(d.amount)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Discount amount must be positive.")
    fr = None
    if d.fee_record_id:
        fr = (await db.execute(
            select(StudentFeeRecord).where(
                StudentFeeRecord.id == d.fee_record_id, StudentFeeRecord.org_id == current_user.org_id)
        )).scalar_one_or_none()
    if not fr:
        raise HTTPException(status_code=422, detail="The student's fee record no longer exists; cannot apply.")
    # Guard against over-discounting if the fee record moved since proposal.
    room = money(money(fr.total_fee or 0) - money(fr.paid_amount or 0) - money(fr.discount_amount or 0))
    if amount > room:
        raise HTTPException(
            status_code=422,
            detail=f"Discount {amount} exceeds the fee record's remaining balance {room}.",
        )
    discount_acct = await _ensure_account_by_code(db, current_user.org_id, FEE_DISCOUNT_ACCOUNT_CODE, FEE_DISCOUNT_ACCOUNT_NAME, "expense")
    receivable_acct = await _ensure_account_by_code(db, current_user.org_id, RECEIVABLE_ACCOUNT_CODE, RECEIVABLE_ACCOUNT_NAME, "asset")
    # Ledger contra: Dr Fee Discounts (expense) / Cr Accounts Receivable (asset).
    entry = await ledger.post_journal_entry(
        db, org_id=current_user.org_id, entry_date=datetime.now(timezone.utc).date(),
        memo=f"Fee discount — {d.student_name}", source="fee_discount", source_id=d.id,
        lines=[
            {"account_id": discount_acct.id, "debit": amount, "credit": 0, "description": f"Discount: {d.reason or 'concession'}"},
            {"account_id": receivable_acct.id, "debit": 0, "credit": amount, "description": "Receivable reduced"},
        ],
        actor=current_user, request=request,
    )
    # Fee-record side: accumulate the discount and recompute what's owed.
    fr.discount_amount = money(money(fr.discount_amount or 0) + amount)
    if not fr.discount_reason and d.reason:
        fr.discount_reason = d.reason
    _recompute_fee_record(fr)
    d.status = "approved"
    d.approved_by = current_user.id
    d.approved_at = datetime.now(timezone.utc)
    d.journal_entry_id = entry.id
    d.discount_account_id = discount_acct.id
    d.receivable_account_id = receivable_acct.id
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="FeeDiscount", resource_id=d.id,
        resource_label=f"approved discount {amount} for {d.student_name}",
        old_values={"status": "draft"}, new_values={"status": "approved", "approved_by": current_user.id},
        metadata={"proposed_by": d.proposed_by, "journal_entry_id": entry.id, "fee_record_id": fr.id},
        severity="warning", request=request,
    )
    return _discount_response(d)


@router.post("/discounts/{discount_id}/reject", response_model=DiscountResponse, dependencies=[_fin_post])
async def reject_discount(
    discount_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Reject a draft discount. No fee-record or ledger impact — nothing was applied."""
    d = await _load_discount(db, discount_id, current_user.org_id)
    if d.status != "draft":
        raise HTTPException(status_code=409, detail=f"Only a draft discount can be rejected (this one is {d.status}).")
    d.status = "rejected"
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="FeeDiscount", resource_id=d.id, resource_label=f"rejected discount for {d.student_name}",
        old_values={"status": "draft"}, new_values={"status": "rejected"}, severity="warning", request=request,
    )
    return _discount_response(d)


@router.post("/discounts/{discount_id}/void", response_model=DiscountResponse, dependencies=[_fin_post])
async def void_discount(
    discount_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Void an approved discount — reverses BOTH sides: the ledger contra is reversed
    and the fee record's discount is removed (balance restored)."""
    d = await _load_discount(db, discount_id, current_user.org_id)
    if d.status != "approved":
        raise HTTPException(status_code=409, detail="Only an approved discount can be voided.")
    if d.journal_entry_id:
        e = (await db.execute(select(JournalEntry).where(JournalEntry.id == d.journal_entry_id))).scalar_one_or_none()
        if e and not e.reversed_by_id:
            await ledger.reverse_entry(db, entry_id=d.journal_entry_id, org_id=current_user.org_id, actor=current_user, request=request)
    if d.fee_record_id:
        fr = (await db.execute(
            select(StudentFeeRecord).where(
                StudentFeeRecord.id == d.fee_record_id, StudentFeeRecord.org_id == current_user.org_id)
        )).scalar_one_or_none()
        if fr:
            fr.discount_amount = money(max(money(0), money(fr.discount_amount or 0) - money(d.amount)))
            _recompute_fee_record(fr)
    d.status = "void"
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="FeeDiscount", resource_id=d.id, resource_label=f"voided discount for {d.student_name}",
        new_values={"status": "void"}, severity="warning", request=request,
    )
    return _discount_response(d)


@router.delete("/discounts/{discount_id}", status_code=204, dependencies=[_fin_write])
async def delete_discount(
    discount_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a discount that never applied (draft or rejected). An approved one must
    be voided instead."""
    d = await _load_discount(db, discount_id, current_user.org_id)
    if d.status not in ("draft", "rejected"):
        raise HTTPException(status_code=409, detail="An approved discount cannot be deleted; void it instead.")
    d.is_deleted = True
    d.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Fee Assignment (populate StudentFeeRecord) ──────────────────────────────────
# Sets what a student owes — the data every other fee surface reads (parent Fee
# Management, accountant summaries, and Manage Discounts). This is the ONLY write
# path to StudentFeeRecord. Gated payments:WRITE (not read): parents hold
# payments:read for their OWN fees, but must not assign fees; they see their record
# via the parent outstanding-fees endpoint, not here.

_FEE_FIELDS = ("tuition_fee", "exam_fee", "activity_fee", "transport_fee", "hostel_fee", "other_fees")


def _sum_breakdown(p) -> Decimal:
    return money(sum(money(getattr(p, f) or 0) for f in _FEE_FIELDS))


def _to_dt(d: date | None):
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc) if d else None


async def _student_names(db: AsyncSession, org_id: str, ids: set[str]) -> dict[str, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(
        select(Student.id, Student.first_name, Student.last_name).where(
            Student.org_id == org_id, Student.id.in_(ids))
    )).all()
    return {r.id: " ".join(p for p in [r.first_name, r.last_name] if p) or r.id for r in rows}


def _fee_record_response(fr: StudentFeeRecord, name: str | None) -> FeeRecordResponse:
    return FeeRecordResponse(
        id=fr.id, student_id=fr.student_id, student_name=name, term=fr.term, session_year=fr.session_year,
        tuition_fee=float(fr.tuition_fee or 0), exam_fee=float(fr.exam_fee or 0), activity_fee=float(fr.activity_fee or 0),
        transport_fee=float(fr.transport_fee or 0), hostel_fee=float(fr.hostel_fee or 0), other_fees=float(fr.other_fees or 0),
        total_fee=float(fr.total_fee or 0), paid_amount=float(fr.paid_amount or 0), discount_amount=float(fr.discount_amount or 0),
        outstanding_balance=float(fr.outstanding_balance or 0), is_paid=bool(fr.is_paid), payment_status=fr.payment_status or "unpaid",
        due_date=fr.due_date.date() if fr.due_date else None, created_at=fr.created_at, org_id=fr.org_id,
    )


async def _existing_fee_record(db: AsyncSession, org_id: str, student_id: str, term: str, session_year: str) -> StudentFeeRecord | None:
    return (await db.execute(
        select(StudentFeeRecord).where(
            StudentFeeRecord.org_id == org_id, StudentFeeRecord.student_id == student_id,
            StudentFeeRecord.term == term, StudentFeeRecord.session_year == session_year,
            StudentFeeRecord.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()


def _apply_breakdown(fr: StudentFeeRecord, p) -> None:
    for f in _FEE_FIELDS:
        setattr(fr, f, money(getattr(p, f) or 0))
    fr.total_fee = _sum_breakdown(p)
    _recompute_fee_record(fr)


@router.get("/classes", response_model=list[ClassOption], dependencies=[_fin_write])
async def list_finance_classes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Classes (id, name, student count) for finance dropdowns like Fee Assignment.
    Gated payments:write — the same audience as Fee Assignment (managers, accountants,
    admins). Exists because there is no general /school/classes list endpoint, and an
    accountant holds payments:write but NOT school:read, so a school-gated list would
    leave their class dropdown empty."""
    classes = (await db.execute(
        select(SchoolClass).where(SchoolClass.org_id == current_user.org_id).order_by(SchoolClass.name)
    )).scalars().all()
    counts = dict((await db.execute(
        select(Student.class_id, func.count(Student.id)).where(
            Student.org_id == current_user.org_id, Student.is_deleted == False)  # noqa: E712
        .group_by(Student.class_id)
    )).all())
    return [ClassOption(id=c.id, name=c.name, student_count=int(counts.get(c.id, 0))) for c in classes]


@router.get("/fee-records", response_model=list[FeeRecordResponse], dependencies=[_fin_write])
async def list_fee_records(
    student_id: str | None = Query(None),
    term: str | None = Query(None),
    session_year: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(StudentFeeRecord).where(
        StudentFeeRecord.org_id == current_user.org_id, StudentFeeRecord.is_deleted == False)  # noqa: E712
    if student_id:
        q = q.where(StudentFeeRecord.student_id == student_id)
    if term:
        q = q.where(StudentFeeRecord.term == term)
    if session_year:
        q = q.where(StudentFeeRecord.session_year == session_year)
    rows = (await db.execute(q.order_by(StudentFeeRecord.created_at.desc()))).scalars().all()
    names = await _student_names(db, current_user.org_id, {r.student_id for r in rows})
    return [_fee_record_response(fr, names.get(fr.student_id)) for fr in rows]


@router.post("/fee-records", response_model=FeeRecordResponse, status_code=201, dependencies=[_fin_write])
async def create_fee_record(
    payload: FeeRecordCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Assign fees to one student for a term (creates their StudentFeeRecord)."""
    student = (await db.execute(
        select(Student).where(Student.id == payload.student_id, Student.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found in your organisation.")
    if _sum_breakdown(payload) <= 0:
        raise HTTPException(status_code=422, detail="Total fee must be positive (set at least one fee component).")
    if await _existing_fee_record(db, current_user.org_id, student.id, payload.term, payload.session_year):
        raise HTTPException(status_code=409, detail="This student already has a fee record for that term/session — edit it instead.")
    fr = StudentFeeRecord(
        org_id=current_user.org_id, student_id=student.id, term=payload.term, session_year=payload.session_year,
        paid_amount=money(0), discount_amount=money(0), due_date=_to_dt(payload.due_date),
    )
    _apply_breakdown(fr, payload)
    db.add(fr)
    await db.flush()
    name = " ".join(p for p in [getattr(student, "first_name", None), getattr(student, "last_name", None)] if p) or None
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="StudentFeeRecord", resource_id=fr.id,
        resource_label=f"assigned fees {money(fr.total_fee)} to {name} ({payload.term})", request=request,
    )
    return _fee_record_response(fr, name)


@router.patch("/fee-records/{record_id}", response_model=FeeRecordResponse, dependencies=[_fin_write])
async def update_fee_record(
    record_id: str,
    payload: FeeRecordUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a fee record's breakdown; total + outstanding recompute (paid and any
    approved discount are preserved)."""
    fr = (await db.execute(
        select(StudentFeeRecord).where(
            StudentFeeRecord.id == record_id, StudentFeeRecord.org_id == current_user.org_id,
            StudentFeeRecord.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not fr:
        raise HTTPException(status_code=404, detail="Fee record not found.")
    if _sum_breakdown(payload) <= 0:
        raise HTTPException(status_code=422, detail="Total fee must be positive.")
    _apply_breakdown(fr, payload)
    if payload.due_date is not None:
        fr.due_date = _to_dt(payload.due_date)
    await db.flush()
    names = await _student_names(db, current_user.org_id, {fr.student_id})
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="StudentFeeRecord", resource_id=fr.id,
        resource_label=f"updated fees to {money(fr.total_fee)} ({fr.term})", request=request,
    )
    return _fee_record_response(fr, names.get(fr.student_id))


@router.delete("/fee-records/{record_id}", status_code=204, dependencies=[_fin_write])
async def delete_fee_record(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    fr = (await db.execute(
        select(StudentFeeRecord).where(
            StudentFeeRecord.id == record_id, StudentFeeRecord.org_id == current_user.org_id,
            StudentFeeRecord.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not fr:
        raise HTTPException(status_code=404, detail="Fee record not found.")
    fr.is_deleted = True
    fr.deleted_at = datetime.now(timezone.utc)
    await db.flush()


@router.post("/fee-records/assign-class", response_model=ClassFeeAssignResult, dependencies=[_fin_write])
async def assign_class_fees(
    payload: ClassFeeAssign,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Assign the same fees to every student in a class for a term. Students who
    already have a record for that term/session are skipped (edit theirs instead)."""
    cls = (await db.execute(
        select(SchoolClass).where(SchoolClass.id == payload.class_id, SchoolClass.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found in your organisation.")
    if _sum_breakdown(payload) <= 0:
        raise HTTPException(status_code=422, detail="Total fee must be positive (set at least one fee component).")
    students = (await db.execute(
        select(Student).where(
            Student.class_id == cls.id, Student.org_id == current_user.org_id,
            Student.is_deleted == False)  # noqa: E712
    )).scalars().all()
    created: list[StudentFeeRecord] = []
    skipped = 0
    for s in students:
        if await _existing_fee_record(db, current_user.org_id, s.id, payload.term, payload.session_year):
            skipped += 1
            continue
        fr = StudentFeeRecord(
            org_id=current_user.org_id, student_id=s.id, term=payload.term, session_year=payload.session_year,
            paid_amount=money(0), discount_amount=money(0), due_date=_to_dt(payload.due_date),
        )
        _apply_breakdown(fr, payload)
        db.add(fr)
        created.append(fr)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="StudentFeeRecord", resource_id=cls.id,
        resource_label=f"assigned {payload.term} fees to class {getattr(cls, 'name', cls.id)}: {len(created)} created, {skipped} skipped",
        request=request,
    )
    names = await _student_names(db, current_user.org_id, {fr.student_id for fr in created})
    return ClassFeeAssignResult(
        created=len(created), skipped=skipped, total_students=len(students),
        records=[_fee_record_response(fr, names.get(fr.student_id)) for fr in created],
    )


# ── Bank Accounts (Account Numbers) ─────────────────────────────────────────────
# The school's own bank accounts (where fees are received). Reference data shown on
# invoices / receipts. Managed by finance (payments:write); the school's receiving
# account is not secret (it's on every invoice), unlike staff salary accounts or
# payment-gateway credentials. Exactly one account is is_primary (the default).


def _bank_account_response(b: BankAccount) -> BankAccountResponse:
    return BankAccountResponse(
        id=b.id, bank_name=b.bank_name, account_name=b.account_name, account_number=b.account_number,
        bank_code=b.bank_code, account_type=b.account_type, purpose=b.purpose,
        is_primary=bool(b.is_primary), is_active=bool(b.is_active), notes=b.notes,
        created_at=b.created_at, org_id=b.org_id,
    )


async def _load_bank_account(db: AsyncSession, account_id: str, org_id: str) -> BankAccount:
    b = (await db.execute(
        select(BankAccount).where(
            BankAccount.id == account_id, BankAccount.org_id == org_id,
            BankAccount.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Bank account not found.")
    return b


async def _clear_other_primaries(db: AsyncSession, org_id: str, keep_id: str | None) -> None:
    rows = (await db.execute(
        select(BankAccount).where(
            BankAccount.org_id == org_id, BankAccount.is_primary == True,  # noqa: E712
            BankAccount.is_deleted == False)  # noqa: E712
    )).scalars().all()
    for r in rows:
        if r.id != keep_id:
            r.is_primary = False


@router.get("/bank-accounts", response_model=list[BankAccountResponse], dependencies=[_fin_write])
async def list_bank_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows = (await db.execute(
        select(BankAccount).where(
            BankAccount.org_id == current_user.org_id, BankAccount.is_deleted == False)  # noqa: E712
        .order_by(BankAccount.is_primary.desc(), BankAccount.created_at.desc())
    )).scalars().all()
    return [_bank_account_response(b) for b in rows]


@router.get("/bank-accounts/primary", response_model=BankAccountPublic | None, dependencies=[_fin_read])
async def primary_bank_account(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """The primary active 'pay to' account, public subset — gated payments:READ so
    fee-payers (parents) can see where to pay. Returns null if none is set."""
    b = (await db.execute(
        select(BankAccount).where(
            BankAccount.org_id == current_user.org_id, BankAccount.is_primary == True,  # noqa: E712
            BankAccount.is_active == True, BankAccount.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not b:
        return None
    return BankAccountPublic(
        bank_name=b.bank_name, account_name=b.account_name, account_number=b.account_number,
        bank_code=b.bank_code, account_type=b.account_type, purpose=b.purpose,
    )


@router.post("/bank-accounts", response_model=BankAccountResponse, status_code=201, dependencies=[_fin_write])
async def create_bank_account(
    payload: BankAccountCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    existing_count = (await db.execute(
        select(func.count(BankAccount.id)).where(
            BankAccount.org_id == current_user.org_id, BankAccount.is_deleted == False)  # noqa: E712
    )).scalar() or 0
    make_primary = payload.is_primary or existing_count == 0   # first account is primary
    b = BankAccount(
        bank_name=payload.bank_name, account_name=payload.account_name, account_number=payload.account_number,
        bank_code=payload.bank_code, account_type=payload.account_type, purpose=payload.purpose,
        is_primary=make_primary, is_active=payload.is_active, notes=payload.notes, org_id=current_user.org_id,
    )
    db.add(b)
    await db.flush()
    if make_primary:
        await _clear_other_primaries(db, current_user.org_id, keep_id=b.id)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="BankAccount", resource_id=b.id,
        resource_label=f"{b.bank_name} {b.account_number}", request=request,
    )
    return _bank_account_response(b)


@router.patch("/bank-accounts/{account_id}", response_model=BankAccountResponse, dependencies=[_fin_write])
async def update_bank_account(
    account_id: str,
    payload: BankAccountUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    b = await _load_bank_account(db, account_id, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    for f, v in data.items():
        setattr(b, f, v)
    await db.flush()
    if data.get("is_primary") is True:
        await _clear_other_primaries(db, current_user.org_id, keep_id=b.id)
        await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="BankAccount", resource_id=b.id, resource_label=f"{b.bank_name} {b.account_number}",
        request=request,
    )
    return _bank_account_response(b)


@router.post("/bank-accounts/{account_id}/set-primary", response_model=BankAccountResponse, dependencies=[_fin_write])
async def set_primary_bank_account(
    account_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    b = await _load_bank_account(db, account_id, current_user.org_id)
    b.is_primary = True
    await _clear_other_primaries(db, current_user.org_id, keep_id=b.id)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="BankAccount", resource_id=b.id, resource_label=f"set primary {b.bank_name} {b.account_number}",
        request=request,
    )
    return _bank_account_response(b)


@router.delete("/bank-accounts/{account_id}", status_code=204, dependencies=[_fin_write])
async def delete_bank_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    b = await _load_bank_account(db, account_id, current_user.org_id)
    b.is_deleted = True
    b.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Accounts Setup (default posting accounts) ───────────────────────────────────
# Per-org mapping of which ledger account is the default for cash / fees-income /
# receivable / expense. Finance forms pre-fill from these (still overridable).
# Gated payments:write (matches the route); each default must be the right account
# type so a misconfigured default can't slip in.

_DEFAULT_TYPES = {
    "default_cash_account_id": ("asset", "cash/bank"),
    "default_income_account_id": ("income", "income"),
    "default_receivable_account_id": ("asset", "receivable"),
    "default_expense_account_id": ("expense", "expense"),
}


async def _settings_response(db: AsyncSession, s: OrgFinanceSettings | None, org_id: str) -> FinanceSettingsResponse:
    ids = {}
    if s:
        ids = {
            "cash": s.default_cash_account_id, "income": s.default_income_account_id,
            "receivable": s.default_receivable_account_id, "expense": s.default_expense_account_id,
        }
    meta = await _account_meta(db, org_id, {v for v in ids.values() if v})
    name = lambda aid: meta.get(aid, (None, None))[1] if aid else None
    return FinanceSettingsResponse(
        default_cash_account_id=ids.get("cash"), default_cash_account_name=name(ids.get("cash")),
        default_income_account_id=ids.get("income"), default_income_account_name=name(ids.get("income")),
        default_receivable_account_id=ids.get("receivable"), default_receivable_account_name=name(ids.get("receivable")),
        default_expense_account_id=ids.get("expense"), default_expense_account_name=name(ids.get("expense")),
        org_id=org_id,
    )


@router.get("/settings", response_model=FinanceSettingsResponse, dependencies=[_fin_write])
async def get_finance_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    s = (await db.execute(
        select(OrgFinanceSettings).where(OrgFinanceSettings.org_id == current_user.org_id)
    )).scalar_one_or_none()
    return await _settings_response(db, s, current_user.org_id)


@router.put("/settings", response_model=FinanceSettingsResponse, dependencies=[_fin_write])
async def update_finance_settings(
    payload: FinanceSettingsUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    data = payload.model_dump(exclude_unset=True)
    # Validate each supplied account exists in-org and is the right type.
    for field, aid in data.items():
        if aid:
            acct = await _require_account(db, current_user.org_id, aid)
            expected, label = _DEFAULT_TYPES[field]
            if acct.type != expected:
                raise HTTPException(
                    status_code=422,
                    detail=f"The {label} default must be a{'n' if expected[0] in 'aeiou' else ''} {expected} account (got '{acct.type}').",
                )
    s = (await db.execute(
        select(OrgFinanceSettings).where(OrgFinanceSettings.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if not s:
        s = OrgFinanceSettings(org_id=current_user.org_id)
        db.add(s)
    for field, aid in data.items():
        setattr(s, field, aid)   # present-and-null clears; omitted untouched
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="OrgFinanceSettings", resource_id=s.id, resource_label="default posting accounts",
        new_values={k: str(v) for k, v in data.items()}, request=request,
    )
    return await _settings_response(db, s, current_user.org_id)


# ── Payment Gateways (per-org gateway credentials; secrets encrypted at rest) ──────
# org_admin-only (payment_gateways:* — see the gate definitions above). Backed by
# `TenantPaymentSettings` — the SAME model the billing resolver consumes, so a
# gateway configured here is what `payment_resolver.resolve_for_org` decrypts and
# uses for live fee payments (Paystack today). Secret key + webhook secret are
# stored ENCRYPTED (crypto.encrypt → AES-256-GCM) in the `encrypted_*` columns;
# label / mode / public_key (non-sensitive) live in the `metadata` JSON. This
# router NEVER returns a plaintext secret and NEVER decrypts to render the list —
# only whether a secret is set. Decryption happens only at the gateway call site.
#
# CONSUMPTION STATUS (flagged): Paystack is wired into live payments via the
# resolver. Remita (separate /payments/remita router, 3-part creds read from env)
# and Flutterwave (no provider adapter yet) are STORED here but NOT yet consumed —
# tracked in POST_LAUNCH_BACKLOG.md.

def _gw_meta(row: TenantPaymentSettings) -> dict:
    return dict(row.metadata_ or {})


async def _load_gateway(db: AsyncSession, gid: str, org_id: str) -> TenantPaymentSettings:
    g = (await db.execute(
        select(TenantPaymentSettings).where(
            TenantPaymentSettings.id == gid, TenantPaymentSettings.org_id == org_id,
            TenantPaymentSettings.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Payment gateway not found.")
    return g


def _gateway_response(g: TenantPaymentSettings) -> PaymentGatewayResponse:
    md = _gw_meta(g)
    return PaymentGatewayResponse(
        id=g.id, provider=g.provider.value if hasattr(g.provider, "value") else str(g.provider),
        label=md.get("label"), mode=md.get("mode", "test"), public_key=md.get("public_key"),
        # set-ness only — never decrypt a secret to render a page.
        secret_key_set=bool(g.encrypted_secret_key), webhook_secret_set=bool(g.encrypted_webhook_secret),
        is_active=bool(g.is_active), created_at=g.created_at, org_id=g.org_id,
    )


def _require_crypto_for(*secrets: str | None) -> None:
    """If any secret is being stored, the encryption key must be configured —
    fail closed with a clear 503 rather than persisting a recoverable secret."""
    if any(s for s in secrets) and not crypto.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Encryption is not configured (ENCRYPTION_KEY unset) — cannot store gateway secrets. "
                   "Set ENCRYPTION_KEY on the server first. See ENCRYPTION_SERVICE_SPEC.md.",
        )


def _apply_gateway_fields(g: TenantPaymentSettings, *, label=..., mode=..., public_key=...,
                          secret_key=..., webhook_secret=..., is_active=...) -> bool:
    """Apply provided fields onto a TenantPaymentSettings row. Sentinels (...) mean
    'not supplied → leave unchanged'. Secrets are encrypted; non-secret display
    fields go into metadata. Returns True if a secret was (re)written."""
    md = _gw_meta(g)
    if label is not ...:
        md["label"] = label
    if mode is not ...:
        md["mode"] = mode
    if public_key is not ...:
        md["public_key"] = public_key
    md.pop("platform_fallback", None)          # a real config is no longer a fallback
    g.metadata_ = md                           # reassign so the JSON column is marked dirty
    if is_active is not ...:
        g.is_active = is_active
    wrote_secret = False
    if secret_key is not ...:
        g.encrypted_secret_key = crypto.encrypt(secret_key) if secret_key else None
        wrote_secret = True
    if webhook_secret is not ...:
        g.encrypted_webhook_secret = crypto.encrypt(webhook_secret) if webhook_secret else None
        wrote_secret = True
    return wrote_secret


@router.get("/payment-gateways", response_model=list[PaymentGatewayResponse], dependencies=[_gw_read])
async def list_payment_gateways(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(
        select(TenantPaymentSettings).where(
            TenantPaymentSettings.org_id == current_user.org_id, TenantPaymentSettings.is_deleted == False)  # noqa: E712
        .order_by(TenantPaymentSettings.provider)
    )).scalars().all()
    return [_gateway_response(g) for g in rows]


@router.post("/payment-gateways", response_model=PaymentGatewayResponse, status_code=201, dependencies=[_gw_write])
async def create_payment_gateway(
    payload: PaymentGatewayCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.provider not in GATEWAY_PROVIDERS:
        raise HTTPException(status_code=422, detail=f"Unknown provider. Choose one of: {', '.join(GATEWAY_PROVIDERS)}.")
    if payload.mode not in GATEWAY_MODES:
        raise HTTPException(status_code=422, detail="mode must be 'test' or 'live'.")
    _require_crypto_for(payload.secret_key, payload.webhook_secret)
    provider = PaymentProvider(payload.provider)

    # At most one active config per provider per org. If a row already exists it's
    # either a real admin config (409 — edit it) or a platform-fallback placeholder
    # that school_payments auto-created for FK integrity (adopt it in place).
    existing = (await db.execute(
        select(TenantPaymentSettings).where(
            TenantPaymentSettings.org_id == current_user.org_id, TenantPaymentSettings.provider == provider,
            TenantPaymentSettings.is_deleted == False)  # noqa: E712
        .order_by(TenantPaymentSettings.created_at)
    )).scalars().first()
    if existing and not (existing.metadata_ or {}).get("platform_fallback"):
        raise HTTPException(status_code=409, detail=f"A {payload.provider} gateway is already configured. Edit it instead.")

    g = existing or TenantPaymentSettings(org_id=current_user.org_id, provider=provider, is_active=True)
    g.configured_by_user_id = current_user.id
    _apply_gateway_fields(
        g, label=payload.label, mode=payload.mode, public_key=payload.public_key,
        secret_key=payload.secret_key or None, webhook_secret=payload.webhook_secret or None,
        is_active=payload.is_active,
    )
    if existing is None:
        db.add(g)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="TenantPaymentSettings", resource_id=g.id,
        resource_label=f"{payload.provider} gateway ({payload.mode})",
        # NEVER log secret values — only that they were set.
        new_values={"provider": payload.provider, "mode": payload.mode,
                    "secret_key_set": bool(payload.secret_key), "webhook_secret_set": bool(payload.webhook_secret)},
        severity="warning", request=request,
    )
    return _gateway_response(g)


@router.patch("/payment-gateways/{gateway_id}", response_model=PaymentGatewayResponse, dependencies=[_gw_write])
async def update_payment_gateway(
    gateway_id: str,
    payload: PaymentGatewayUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    g = await _load_gateway(db, gateway_id, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    if "mode" in data and data["mode"] not in GATEWAY_MODES:
        raise HTTPException(status_code=422, detail="mode must be 'test' or 'live'.")
    _require_crypto_for(data.get("secret_key"), data.get("webhook_secret"))

    changed_secret = _apply_gateway_fields(
        g,
        label=data["label"] if "label" in data else ...,
        mode=data["mode"] if "mode" in data else ...,
        public_key=data["public_key"] if "public_key" in data else ...,
        secret_key=(data["secret_key"] or None) if "secret_key" in data else ...,
        webhook_secret=(data["webhook_secret"] or None) if "webhook_secret" in data else ...,
        is_active=data["is_active"] if "is_active" in data else ...,
    )
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="TenantPaymentSettings", resource_id=g.id, resource_label=f"{g.provider.value} gateway",
        new_values={k: v for k, v in data.items() if k not in ("secret_key", "webhook_secret")}
                   | ({"secrets_rotated": True} if changed_secret else {}),
        severity="warning", request=request,
    )
    return _gateway_response(g)


@router.delete("/payment-gateways/{gateway_id}", status_code=204, dependencies=[_gw_write])
async def delete_payment_gateway(
    gateway_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    g = await _load_gateway(db, gateway_id, current_user.org_id)
    g.is_deleted = True
    g.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
        resource_type="TenantPaymentSettings", resource_id=g.id, resource_label=f"{g.provider.value} gateway",
        severity="warning", request=request,
    )
