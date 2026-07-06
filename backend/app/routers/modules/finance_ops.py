"""Finance ops router (Batch 5, second half), prefix ``/finance``.

Petty Cash & Budget, Cash Transactions, Store & Inventory. Every money movement
posts through ``app.services.ledger.post_journal_entry`` — so these features
INHERIT the double-entry, account-validation and period-lock guards (proven per
feature in tests, not assumed). Budget enforcement is a SOFT over-budget warning.

RBAC: recording a posting needs ``payments:post`` (it writes to the ledger);
budgets + store-item setup + non-financial stock moves need ``payments:write``.
"""
from __future__ import annotations

from datetime import datetime, timezone, date as date_type
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.tenant import require_module
from app.core.permissions import PermissionChecker, AnyPermissionChecker
from app.models.user import User
from app.models.modules.school import Student
from app.models.modules.finance import (
    LedgerAccount, JournalEntry, JournalLine,
    Budget, PettyCashTxn, CashTransaction, StoreItem, StockMovement,
    StoreSale, StoreSaleLine, OrgFinanceSettings, Warehouse, WarehouseStock,
    PickupPoint, Pickup,
)
from app.schemas.finance_ops import (
    BudgetCreate, BudgetUpdate, BudgetResponse,
    PettyCashCreate, PettyCashResponse, PettyCashListResponse,
    CashTxnCreate, CashTxnResponse, CashTxnListResponse,
    StoreItemCreate, StoreItemUpdate, StoreItemResponse, StoreItemListResponse,
    PurchaseCreate, StockAdjustCreate, StockMovementResponse,
    StoreSaleCreate, StoreSaleResponse, StoreSaleLineResponse,
    StoreSalesSummary, SalesTopItem, SalesGroup,
    WarehouseCreate, WarehouseUpdate, WarehouseResponse, WarehouseStockRow,
    StockReceive, StockTransfer, StockIssue,
    PickupPointCreate, PickupPointUpdate, PickupPointResponse,
    PickupCreate, PickupResponse,
    CASH_TYPES, STOCK_MOVE_TYPES,
)
from app.services import ledger
from app.services.ledger import money

router = APIRouter(
    prefix="/finance",
    tags=["Finance Ops"],
    dependencies=[Depends(require_module("school"))],
)

_fin_read = Depends(PermissionChecker("payments:read"))
_fin_write = Depends(PermissionChecker("payments:write"))
_fin_post = Depends(PermissionChecker("payments:post"))
# Ringing up a store sale is a NARROW till-operator action — its own least-privilege
# gate, held by the Cashier role, so day-to-day till staff don't need the broad
# `payments:post` (which also approves payroll / discounts / arbitrary ledger posts).
# Stock PURCHASE stays on `payments:post` — that's inventory buying, a broader
# financial posting, not a till sale.
_store_sell = Depends(PermissionChecker("store:sell"))
# Marking a store pickup COLLECTED is a daily till-counter action with no money /
# ledger impact — the person handing the item over is usually the same cashier who
# rang up the sale. So `collect` accepts EITHER the narrow cashier gate OR the
# finance-clerk gate (a manager keeps access; a cashier gains it without needing
# `payments:write`). Point config + ticket create/cancel stay `payments:write`.
_pickup_collect = Depends(AnyPermissionChecker("store:sell", "payments:write"))


async def _account_meta(db: AsyncSession, org_id: str, ids: set[str]) -> dict[str, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(
        select(LedgerAccount.id, LedgerAccount.name).where(LedgerAccount.org_id == org_id, LedgerAccount.id.in_(ids))
    )).all()
    return {r.id: r.name for r in rows}


async def _require_account(db: AsyncSession, org_id: str, account_id: str) -> LedgerAccount:
    a = (await db.execute(
        select(LedgerAccount).where(
            LedgerAccount.id == account_id, LedgerAccount.org_id == org_id, LedgerAccount.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="account not found in your organisation.")
    return a


async def _account_spent(db: AsyncSession, org_id: str, account_id: str,
                         start: date_type | None = None, end: date_type | None = None) -> Decimal:
    """Non-reversed debits posted to an expense account (soft-budget basis).

    When ``start``/``end`` are given, spend is scoped to entries dated within that
    (inclusive) window — this is what makes per-period budget variance meaningful.
    With no window it totals all-time (backward-compatible with date-less budgets)."""
    q = (
        select(func.coalesce(func.sum(JournalLine.debit), 0))
        .select_from(JournalLine).join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(
            JournalLine.org_id == org_id, JournalLine.account_id == account_id,
            JournalEntry.reversed_at.is_(None),
        )
    )
    if start is not None:
        q = q.where(JournalEntry.entry_date >= start)
    if end is not None:
        q = q.where(JournalEntry.entry_date <= end)
    total = (await db.execute(q)).scalar()
    return money(total or 0)


# ── Budgets ─────────────────────────────────────────────────────────────────────

async def _budget_response(db: AsyncSession, b: Budget, org_id: str, account_name: str | None) -> BudgetResponse:
    spent = await _account_spent(db, org_id, b.account_id, b.start_date, b.end_date)
    amount = money(b.amount or 0)
    return BudgetResponse(
        id=b.id, account_id=b.account_id, account_name=account_name,
        period_label=b.period_label, start_date=b.start_date, end_date=b.end_date,
        amount=float(amount), spent=float(spent), remaining=float(money(amount - spent)),
        notes=b.notes, created_at=b.created_at, org_id=b.org_id,
    )


async def _load_budget(db: AsyncSession, budget_id: str, org_id: str) -> Budget:
    b = (await db.execute(select(Budget).where(Budget.id == budget_id, Budget.org_id == org_id))).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Budget not found.")
    return b


@router.get("/budgets", response_model=list[BudgetResponse], dependencies=[_fin_read])
async def list_budgets(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(
        select(Budget).where(Budget.org_id == current_user.org_id).order_by(Budget.created_at.desc())
    )).scalars().all()
    names = await _account_meta(db, current_user.org_id, {b.account_id for b in rows})
    return [await _budget_response(db, b, current_user.org_id, names.get(b.account_id)) for b in rows]


@router.post("/budgets", response_model=BudgetResponse, status_code=201, dependencies=[_fin_write])
async def create_budget(payload: BudgetCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    await _require_account(db, current_user.org_id, payload.account_id)
    if payload.start_date and payload.end_date and payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="Budget end date cannot be before its start date.")
    b = Budget(
        account_id=payload.account_id, period_label=payload.period_label,
        start_date=payload.start_date, end_date=payload.end_date,
        amount=money(payload.amount), notes=payload.notes, org_id=current_user.org_id,
    )
    db.add(b)
    await db.flush()
    names = await _account_meta(db, current_user.org_id, {b.account_id})
    return await _budget_response(db, b, current_user.org_id, names.get(b.account_id))


@router.patch("/budgets/{budget_id}", response_model=BudgetResponse, dependencies=[_fin_write])
async def update_budget(budget_id: str, payload: BudgetUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    b = await _load_budget(db, budget_id, current_user.org_id)
    if payload.period_label is not None:
        b.period_label = payload.period_label
    if payload.start_date is not None:
        b.start_date = payload.start_date
    if payload.end_date is not None:
        b.end_date = payload.end_date
    if payload.amount is not None:
        b.amount = money(payload.amount)
    if payload.notes is not None:
        b.notes = payload.notes
    if b.start_date and b.end_date and b.end_date < b.start_date:
        raise HTTPException(status_code=422, detail="Budget end date cannot be before its start date.")
    await db.flush()
    names = await _account_meta(db, current_user.org_id, {b.account_id})
    return await _budget_response(db, b, current_user.org_id, names.get(b.account_id))


@router.delete("/budgets/{budget_id}", status_code=204, dependencies=[_fin_write])
async def delete_budget(budget_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    b = await _load_budget(db, budget_id, current_user.org_id)
    await db.delete(b)


# ── Petty Cash ──────────────────────────────────────────────────────────────────

def _petty_response(t: PettyCashTxn, exp_name: str | None, warning: str | None = None) -> PettyCashResponse:
    return PettyCashResponse(
        id=t.id, txn_date=t.txn_date, description=t.description, amount=float(t.amount or 0),
        expense_account_id=t.expense_account_id, expense_account_name=exp_name, cash_account_id=t.cash_account_id,
        category=t.category, status=t.status, journal_entry_id=t.journal_entry_id, warning=warning,
        created_at=t.created_at, org_id=t.org_id,
    )


@router.get("/petty-cash", response_model=PettyCashListResponse, dependencies=[_fin_read])
async def list_petty_cash(
    page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    base = select(PettyCashTxn).where(PettyCashTxn.org_id == current_user.org_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(base.order_by(PettyCashTxn.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    names = await _account_meta(db, current_user.org_id, {r.expense_account_id for r in rows})
    return PettyCashListResponse(items=[_petty_response(r, names.get(r.expense_account_id)) for r in rows],
                                 total=total, page=page, page_size=page_size)


@router.post("/petty-cash", response_model=PettyCashResponse, status_code=201, dependencies=[_fin_post])
async def record_petty_cash(
    payload: PettyCashCreate, request: Request = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    exp = await _require_account(db, current_user.org_id, payload.expense_account_id)
    await _require_account(db, current_user.org_id, payload.cash_account_id)
    amount = money(payload.amount)
    entry_date = payload.txn_date or datetime.now(timezone.utc).date()
    # Dr Expense / Cr Petty-Cash — via the shared engine (inherits all guards).
    entry = await ledger.post_journal_entry(
        db, org_id=current_user.org_id, entry_date=entry_date,
        memo=f"Petty cash: {payload.description or payload.category or 'disbursement'}",
        source="petty_cash", source_id=None,
        lines=[
            {"account_id": exp.id, "debit": amount, "credit": 0, "description": payload.description},
            {"account_id": payload.cash_account_id, "debit": 0, "credit": amount, "description": "Petty cash out"},
        ],
        actor=current_user, request=request,
    )
    t = PettyCashTxn(
        txn_date=entry_date, description=payload.description, amount=amount,
        expense_account_id=exp.id, cash_account_id=payload.cash_account_id, category=payload.category,
        status="posted", journal_entry_id=entry.id, posted_by=current_user.id, org_id=current_user.org_id,
    )
    db.add(t)
    await db.flush()
    # SOFT budget check (non-blocking) — surface an over-budget warning only.
    warning = None
    budget = (await db.execute(
        select(Budget).where(Budget.org_id == current_user.org_id, Budget.account_id == exp.id).limit(1)
    )).scalar_one_or_none()
    if budget:
        spent = await _account_spent(db, current_user.org_id, exp.id)
        if spent > money(budget.amount):
            warning = f"Over budget for {exp.name}: spent {spent} of {money(budget.amount)}."
    return _petty_response(t, exp.name, warning)


@router.post("/petty-cash/{txn_id}/void", response_model=PettyCashResponse, dependencies=[_fin_post])
async def void_petty_cash(txn_id: str, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    t = (await db.execute(select(PettyCashTxn).where(PettyCashTxn.id == txn_id, PettyCashTxn.org_id == current_user.org_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    if t.status == "void":
        raise HTTPException(status_code=409, detail="Already void.")
    if t.journal_entry_id:
        e = (await db.execute(select(JournalEntry).where(JournalEntry.id == t.journal_entry_id))).scalar_one_or_none()
        if e and not e.reversed_by_id:
            await ledger.reverse_entry(db, entry_id=t.journal_entry_id, org_id=current_user.org_id, actor=current_user, request=request)
    t.status = "void"
    await db.flush()
    names = await _account_meta(db, current_user.org_id, {t.expense_account_id})
    return _petty_response(t, names.get(t.expense_account_id))


# ── Cash Transactions ───────────────────────────────────────────────────────────

def _cash_response(t: CashTransaction, cash_name: str | None, counter_name: str | None) -> CashTxnResponse:
    return CashTxnResponse(
        id=t.id, txn_date=t.txn_date, type=t.type, amount=float(t.amount or 0),
        cash_account_id=t.cash_account_id, cash_account_name=cash_name,
        counter_account_id=t.counter_account_id, counter_account_name=counter_name,
        counterparty=t.counterparty, description=t.description, status=t.status,
        journal_entry_id=t.journal_entry_id, created_at=t.created_at, org_id=t.org_id,
    )


@router.get("/cash", response_model=CashTxnListResponse, dependencies=[_fin_read])
async def list_cash(
    type: str | None = Query(default=None), page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    base = select(CashTransaction).where(CashTransaction.org_id == current_user.org_id)
    if type:
        base = base.where(CashTransaction.type == type)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(base.order_by(CashTransaction.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    names = await _account_meta(db, current_user.org_id, {r.cash_account_id for r in rows} | {r.counter_account_id for r in rows})
    return CashTxnListResponse(
        items=[_cash_response(r, names.get(r.cash_account_id), names.get(r.counter_account_id)) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/cash", response_model=CashTxnResponse, status_code=201, dependencies=[_fin_post])
async def record_cash(
    payload: CashTxnCreate, request: Request = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    if payload.type not in CASH_TYPES:
        raise HTTPException(status_code=422, detail=f"type must be one of {sorted(CASH_TYPES)}")
    cash = await _require_account(db, current_user.org_id, payload.cash_account_id)
    counter = await _require_account(db, current_user.org_id, payload.counter_account_id)
    amount = money(payload.amount)
    entry_date = payload.txn_date or datetime.now(timezone.utc).date()
    if payload.type == "receipt":
        lines = [{"account_id": cash.id, "debit": amount, "credit": 0, "description": "Cash receipt"},
                 {"account_id": counter.id, "debit": 0, "credit": amount, "description": payload.description}]
    else:  # payment
        lines = [{"account_id": counter.id, "debit": amount, "credit": 0, "description": payload.description},
                 {"account_id": cash.id, "debit": 0, "credit": amount, "description": "Cash payment"}]
    entry = await ledger.post_journal_entry(
        db, org_id=current_user.org_id, entry_date=entry_date,
        memo=f"Cash {payload.type}: {payload.counterparty or payload.description or ''}".strip(),
        source="cash", source_id=None, lines=lines, actor=current_user, request=request,
    )
    t = CashTransaction(
        txn_date=entry_date, type=payload.type, amount=amount, cash_account_id=cash.id,
        counter_account_id=counter.id, counterparty=payload.counterparty, description=payload.description,
        status="posted", journal_entry_id=entry.id, posted_by=current_user.id, org_id=current_user.org_id,
    )
    db.add(t)
    await db.flush()
    return _cash_response(t, cash.name, counter.name)


@router.post("/cash/{txn_id}/void", response_model=CashTxnResponse, dependencies=[_fin_post])
async def void_cash(txn_id: str, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    t = (await db.execute(select(CashTransaction).where(CashTransaction.id == txn_id, CashTransaction.org_id == current_user.org_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    if t.status == "void":
        raise HTTPException(status_code=409, detail="Already void.")
    if t.journal_entry_id:
        e = (await db.execute(select(JournalEntry).where(JournalEntry.id == t.journal_entry_id))).scalar_one_or_none()
        if e and not e.reversed_by_id:
            await ledger.reverse_entry(db, entry_id=t.journal_entry_id, org_id=current_user.org_id, actor=current_user, request=request)
    t.status = "void"
    await db.flush()
    names = await _account_meta(db, current_user.org_id, {t.cash_account_id, t.counter_account_id})
    return _cash_response(t, names.get(t.cash_account_id), names.get(t.counter_account_id))


# ── Store & Inventory ───────────────────────────────────────────────────────────

def _item_response(i: StoreItem) -> StoreItemResponse:
    qty = money(i.quantity)
    reorder = money(i.reorder_level)
    return StoreItemResponse(
        id=i.id, name=i.name, sku=i.sku, unit_price=float(i.unit_price or 0), cost_price=float(i.cost_price or 0),
        quantity=float(qty), reorder_level=float(reorder), is_active=i.is_active,
        low_stock=bool(reorder > 0 and qty <= reorder), created_at=i.created_at, org_id=i.org_id,
    )


async def _load_item(db, iid, org_id) -> StoreItem:
    i = (await db.execute(
        select(StoreItem).where(StoreItem.id == iid, StoreItem.org_id == org_id, StoreItem.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not i:
        raise HTTPException(status_code=404, detail="Store item not found.")
    return i


@router.get("/store/items", response_model=StoreItemListResponse, dependencies=[_fin_read])
async def list_store_items(
    page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    base = select(StoreItem).where(StoreItem.org_id == current_user.org_id, StoreItem.is_deleted == False)  # noqa: E712
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(base.order_by(StoreItem.name).offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return StoreItemListResponse(items=[_item_response(i) for i in rows], total=total, page=page, page_size=page_size)


@router.post("/store/items", response_model=StoreItemResponse, status_code=201, dependencies=[_fin_write])
async def create_store_item(payload: StoreItemCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    i = StoreItem(
        name=payload.name, sku=payload.sku, unit_price=money(payload.unit_price), cost_price=money(payload.cost_price),
        quantity=money(0), reorder_level=money(payload.reorder_level), is_active=True, org_id=current_user.org_id,
    )
    db.add(i)
    await db.flush()
    return _item_response(i)


@router.patch("/store/items/{item_id}", response_model=StoreItemResponse, dependencies=[_fin_write])
async def update_store_item(item_id: str, payload: StoreItemUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    i = await _load_item(db, item_id, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    for field in ("unit_price", "cost_price", "reorder_level"):
        if field in data and data[field] is not None:
            data[field] = money(data[field])
    for field, value in data.items():
        setattr(i, field, value)
    await db.flush()
    return _item_response(i)


@router.delete("/store/items/{item_id}", status_code=204, dependencies=[_fin_write])
async def delete_store_item(item_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    i = await _load_item(db, item_id, current_user.org_id)
    i.is_deleted = True
    i.deleted_at = datetime.now(timezone.utc)
    await db.flush()


@router.get("/store/items/{item_id}/movements", response_model=list[StockMovementResponse], dependencies=[_fin_read])
async def list_movements(item_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    await _load_item(db, item_id, current_user.org_id)
    rows = (await db.execute(
        select(StockMovement).where(StockMovement.item_id == item_id, StockMovement.org_id == current_user.org_id)
        .order_by(StockMovement.created_at.desc())
    )).scalars().all()
    return [StockMovementResponse(id=m.id, item_id=m.item_id, type=m.type, quantity=float(m.quantity or 0),
                                  unit_cost=float(m.unit_cost or 0), note=m.note, journal_entry_id=m.journal_entry_id,
                                  created_at=m.created_at, org_id=m.org_id) for m in rows]


@router.post("/store/items/{item_id}/purchase", response_model=StoreItemResponse, status_code=201, dependencies=[_fin_post])
async def purchase_stock(
    item_id: str, payload: PurchaseCreate, request: Request = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    """Stock-in purchase. Posts Dr Inventory / Cr funding through the ledger
    engine (purchase-side only; no COGS-on-sale), then increments quantity."""
    item = await _load_item(db, item_id, current_user.org_id)
    inv = await _require_account(db, current_user.org_id, payload.inventory_account_id)
    funding = await _require_account(db, current_user.org_id, payload.funding_account_id)
    qty = money(payload.quantity)
    unit_cost = money(payload.unit_cost)
    amount = money(qty * unit_cost)
    entry_date = payload.purchase_date or datetime.now(timezone.utc).date()
    entry = await ledger.post_journal_entry(
        db, org_id=current_user.org_id, entry_date=entry_date,
        memo=f"Stock purchase: {item.name}", source="store", source_id=item.id,
        lines=[{"account_id": inv.id, "debit": amount, "credit": 0, "description": f"Inventory {item.name}"},
               {"account_id": funding.id, "debit": 0, "credit": amount, "description": "Stock purchase"}],
        actor=current_user, request=request,
    )
    db.add(StockMovement(item_id=item.id, type="in", quantity=qty, unit_cost=unit_cost, note=payload.note,
                         journal_entry_id=entry.id, posted_by=current_user.id, org_id=current_user.org_id))
    item.quantity = money(money(item.quantity) + qty)
    await db.flush()
    return _item_response(item)


@router.post("/store/items/{item_id}/adjust", response_model=StoreItemResponse, status_code=201, dependencies=[_fin_write])
async def adjust_stock(
    item_id: str, payload: StockAdjustCreate,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    """Non-financial stock change: issue out / adjustment (quantity only)."""
    if payload.type not in STOCK_MOVE_TYPES:
        raise HTTPException(status_code=422, detail=f"type must be one of {sorted(STOCK_MOVE_TYPES)}")
    item = await _load_item(db, item_id, current_user.org_id)
    qty = money(payload.quantity)
    # out → decrement by qty; adjust → set absolute count (stock-take correction).
    new_qty = money(item.quantity) - qty if payload.type == "out" else qty
    if new_qty < 0:
        raise HTTPException(status_code=422, detail="Resulting stock cannot be negative.")
    db.add(StockMovement(item_id=item.id, type=payload.type, quantity=qty, unit_cost=money(0), note=payload.note,
                         posted_by=current_user.id, org_id=current_user.org_id))
    item.quantity = new_qty
    await db.flush()
    return _item_response(item)


# ── Store Front Desk (POS sales) ────────────────────────────────────────────────
# Recording a sale REDUCES stock (a StockMovement 'out' per line) AND posts revenue
# to the ledger (Dr Cash / Cr Store Sales income) — so it's a posting action:
# gated payments:post, like stock purchases. (v1: revenue + stock only; COGS-on-sale
# and till reconciliation are deliberate follow-ups.)

STORE_SALES_INCOME_CODE = "4100"
STORE_SALES_INCOME_NAME = "Store Sales"
STORE_CASH_CODE = "1000"
STORE_CASH_NAME = "Cash"


async def _ensure_ops_account(db: AsyncSession, org_id: str, code: str, name: str, type_: str) -> LedgerAccount:
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


async def _sale_response(db: AsyncSession, sale: StoreSale) -> StoreSaleResponse:
    lines = (await db.execute(
        select(StoreSaleLine).where(StoreSaleLine.sale_id == sale.id).order_by(StoreSaleLine.created_at)
    )).scalars().all()
    return StoreSaleResponse(
        id=sale.id, reference=sale.reference, customer_name=sale.customer_name, student_id=sale.student_id,
        subtotal=float(sale.subtotal or 0), discount=float(sale.discount or 0), total=float(sale.total or 0),
        payment_method=sale.payment_method, status=sale.status, journal_entry_id=sale.journal_entry_id,
        cashier_id=sale.cashier_id, notes=sale.notes, created_at=sale.created_at, org_id=sale.org_id,
        lines=[StoreSaleLineResponse(
            id=l.id, item_id=l.item_id, item_name=l.item_name, quantity=float(l.quantity or 0),
            unit_price=float(l.unit_price or 0), amount=float(l.amount or 0),
        ) for l in lines],
    )


async def _load_sale(db: AsyncSession, sale_id: str, org_id: str) -> StoreSale:
    s = (await db.execute(
        select(StoreSale).where(
            StoreSale.id == sale_id, StoreSale.org_id == org_id, StoreSale.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Sale not found.")
    return s


@router.get("/store/sales", response_model=list[StoreSaleResponse], dependencies=[_fin_read])
async def list_store_sales(
    status: str | None = Query(None, description="completed | void"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(StoreSale).where(
        StoreSale.org_id == current_user.org_id, StoreSale.is_deleted == False)  # noqa: E712
    if status:
        q = q.where(StoreSale.status == status)
    rows = (await db.execute(q.order_by(StoreSale.created_at.desc()))).scalars().all()
    return [await _sale_response(db, s) for s in rows]


@router.get("/store/sales/{sale_id}", response_model=StoreSaleResponse, dependencies=[_fin_read])
async def get_store_sale(
    sale_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await _sale_response(db, await _load_sale(db, sale_id, current_user.org_id))


@router.post("/store/sales", response_model=StoreSaleResponse, status_code=201, dependencies=[_store_sell])
async def create_store_sale(
    payload: StoreSaleCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Record an over-the-counter sale: price lines from the catalog, check stock,
    reduce stock, and post Dr Cash / Cr Store Sales income."""
    priced: list[tuple[StoreItem, Decimal, Decimal, Decimal]] = []
    subtotal = money(0)
    for ln in payload.lines:
        item = await _load_item(db, ln.item_id, current_user.org_id)
        qty = money(ln.quantity)
        if qty > money(item.quantity):
            raise HTTPException(status_code=422, detail=f"Not enough stock for '{item.name}': {money(item.quantity)} in stock, {qty} requested.")
        unit_price = money(item.unit_price)
        amount = money(qty * unit_price)
        priced.append((item, qty, unit_price, amount))
        subtotal += amount
    subtotal = money(subtotal)
    discount = money(payload.discount)
    if discount < 0:
        raise HTTPException(status_code=422, detail="Discount cannot be negative.")
    if discount > subtotal:
        raise HTTPException(status_code=422, detail="Discount exceeds the subtotal.")
    total = money(subtotal - discount)
    if total <= 0:
        raise HTTPException(status_code=422, detail="Sale total must be positive.")

    defaults = (await db.execute(
        select(OrgFinanceSettings).where(OrgFinanceSettings.org_id == current_user.org_id)
    )).scalar_one_or_none()
    if payload.cash_account_id:
        cash = await _require_account(db, current_user.org_id, payload.cash_account_id)
    elif defaults and defaults.default_cash_account_id:
        cash = await _require_account(db, current_user.org_id, defaults.default_cash_account_id)
    else:
        cash = await _ensure_ops_account(db, current_user.org_id, STORE_CASH_CODE, STORE_CASH_NAME, "asset")
    if payload.income_account_id:
        income = await _require_account(db, current_user.org_id, payload.income_account_id)
    else:
        income = await _ensure_ops_account(db, current_user.org_id, STORE_SALES_INCOME_CODE, STORE_SALES_INCOME_NAME, "income")

    sale = StoreSale(
        reference=payload.reference, customer_name=payload.customer_name, student_id=payload.student_id,
        subtotal=subtotal, discount=discount, total=total, payment_method=payload.payment_method,
        cash_account_id=cash.id, income_account_id=income.id, status="completed",
        cashier_id=current_user.id, notes=payload.notes, org_id=current_user.org_id,
    )
    db.add(sale)
    await db.flush()
    # Dr Cash / Cr Store Sales income.
    entry = await ledger.post_journal_entry(
        db, org_id=current_user.org_id, entry_date=datetime.now(timezone.utc).date(),
        memo=f"Store sale {sale.reference or sale.id[:8]}", source="store_sale", source_id=sale.id,
        lines=[{"account_id": cash.id, "debit": total, "credit": 0, "description": "Store sale"},
               {"account_id": income.id, "debit": 0, "credit": total, "description": "Store sales income"}],
        actor=current_user, request=request,
    )
    sale.journal_entry_id = entry.id
    for item, qty, unit_price, amount in priced:
        db.add(StoreSaleLine(
            org_id=current_user.org_id, sale_id=sale.id, item_id=item.id, item_name=item.name,
            quantity=qty, unit_price=unit_price, amount=amount,
        ))
        db.add(StockMovement(
            item_id=item.id, type="out", quantity=qty, unit_cost=money(0), note=f"Sale {sale.reference or ''}".strip(),
            posted_by=current_user.id, org_id=current_user.org_id,
        ))
        item.quantity = money(money(item.quantity) - qty)
    await db.flush()
    return await _sale_response(db, sale)


@router.post("/store/sales/{sale_id}/void", response_model=StoreSaleResponse, dependencies=[_store_sell])
async def void_store_sale(
    sale_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Void a sale — reverses the ledger entry and restores stock."""
    sale = await _load_sale(db, sale_id, current_user.org_id)
    if sale.status == "void":
        raise HTTPException(status_code=409, detail="Sale already void.")
    if sale.journal_entry_id:
        e = (await db.execute(select(JournalEntry).where(JournalEntry.id == sale.journal_entry_id))).scalar_one_or_none()
        if e and not e.reversed_by_id:
            await ledger.reverse_entry(db, entry_id=sale.journal_entry_id, org_id=current_user.org_id, actor=current_user, request=request)
    lines = (await db.execute(select(StoreSaleLine).where(StoreSaleLine.sale_id == sale.id))).scalars().all()
    for l in lines:
        if not l.item_id:
            continue
        item = (await db.execute(
            select(StoreItem).where(StoreItem.id == l.item_id, StoreItem.org_id == current_user.org_id)
        )).scalar_one_or_none()
        if item:
            db.add(StockMovement(
                item_id=item.id, type="in", quantity=money(l.quantity), unit_cost=money(0), note="Sale void",
                posted_by=current_user.id, org_id=current_user.org_id,
            ))
            item.quantity = money(money(item.quantity) + money(l.quantity))
    sale.status = "void"
    await db.flush()
    return await _sale_response(db, sale)


# ── Sales Monitor (read-only analytics over completed sales) ─────────────────────
# Period store-sales analytics: revenue, top items, by payment method, by cashier.
# Gated payments:WRITE (not read) so parents — who hold payments:read for their own
# fees — can't see store revenue/cashier activity. Read-only; excludes void sales.


def _dt_start(d: date_type | None):
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc) if d else None


def _dt_end(d: date_type | None):
    return datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc) if d else None


@router.get("/store/sales-summary", response_model=StoreSalesSummary, dependencies=[_fin_write])
async def store_sales_summary(
    start: date_type | None = Query(default=None, description="on/after this date"),
    end: date_type | None = Query(default=None, description="on/before this date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if start and end and end < start:
        raise HTTPException(status_code=422, detail="Report end date cannot be before its start date.")
    s_dt, e_dt = _dt_start(start), _dt_end(end)

    def _win(q):
        if s_dt is not None:
            q = q.where(StoreSale.created_at >= s_dt)
        if e_dt is not None:
            q = q.where(StoreSale.created_at <= e_dt)
        return q

    sales = (await db.execute(_win(
        select(StoreSale).where(
            StoreSale.org_id == current_user.org_id, StoreSale.status == "completed",
            StoreSale.is_deleted == False)  # noqa: E712
    ))).scalars().all()
    total_sales = len(sales)
    total_revenue = money(sum(money(s.total or 0) for s in sales))
    average = money(total_revenue / total_sales) if total_sales else money(0)

    pay: dict[str, list] = {}
    cash: dict[str, list] = {}
    for s in sales:
        pk = s.payment_method or "cash"
        pb = pay.setdefault(pk, [0, money(0)])
        pb[0] += 1
        pb[1] += money(s.total or 0)
        ck = s.cashier_id or ""
        cb = cash.setdefault(ck, [0, money(0)])
        cb[0] += 1
        cb[1] += money(s.total or 0)

    by_payment = [SalesGroup(key=k, label=k.title(), count=v[0], revenue=float(v[1])) for k, v in pay.items()]
    by_payment.sort(key=lambda g: -g.revenue)

    names: dict[str, str] = {}
    ids = {k for k in cash if k}
    if ids:
        rows = (await db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))).all()
        names = {r.id: r.full_name for r in rows}
    by_cashier = [
        SalesGroup(key=k or "unknown", label=(names.get(k) or "Unknown") if k else "Unknown", count=v[0], revenue=float(v[1]))
        for k, v in cash.items()
    ]
    by_cashier.sort(key=lambda g: -g.revenue)

    top_q = _win(
        select(StoreSaleLine.item_name, func.sum(StoreSaleLine.quantity), func.sum(StoreSaleLine.amount))
        .select_from(StoreSaleLine)
        .join(StoreSale, StoreSale.id == StoreSaleLine.sale_id)
        .where(
            StoreSale.org_id == current_user.org_id, StoreSale.status == "completed",
            StoreSale.is_deleted == False)  # noqa: E712
        .group_by(StoreSaleLine.item_name)
        .order_by(func.sum(StoreSaleLine.amount).desc())
        .limit(10)
    )
    top_items = [
        SalesTopItem(item_name=n or "—", quantity=float(money(q or 0)), revenue=float(money(a or 0)))
        for n, q, a in (await db.execute(top_q)).all()
    ]

    return StoreSalesSummary(
        start=start, end=end, total_sales=total_sales, total_revenue=float(total_revenue),
        average_sale=float(average), top_items=top_items, by_payment=by_payment, by_cashier=by_cashier,
    )


# ── Warehouse (multi-location stock) ────────────────────────────────────────────
# Its own module: tracks WHERE bulk stock sits across storage locations, separate
# from the sellable StoreItem.quantity (the store page/POS are untouched). Physical
# stock movements only — receive / transfer / issue — no ledger impact, so
# payments:write (like stock adjust), NOT payments:post.


async def _load_warehouse(db: AsyncSession, wid: str, org_id: str) -> Warehouse:
    w = (await db.execute(
        select(Warehouse).where(
            Warehouse.id == wid, Warehouse.org_id == org_id, Warehouse.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="Warehouse not found.")
    return w


async def _warehouse_response(db: AsyncSession, w: Warehouse) -> WarehouseResponse:
    agg = (await db.execute(
        select(func.count(WarehouseStock.id), func.coalesce(func.sum(WarehouseStock.quantity), 0))
        .where(WarehouseStock.warehouse_id == w.id, WarehouseStock.quantity > 0)
    )).one()
    return WarehouseResponse(
        id=w.id, name=w.name, location=w.location, is_active=w.is_active, notes=w.notes,
        item_count=int(agg[0] or 0), total_units=float(money(agg[1] or 0)),
        created_at=w.created_at, org_id=w.org_id,
    )


async def _stock(db: AsyncSession, wid: str, iid: str, org_id: str, create: bool = False) -> WarehouseStock | None:
    s = (await db.execute(
        select(WarehouseStock).where(WarehouseStock.warehouse_id == wid, WarehouseStock.item_id == iid)
    )).scalar_one_or_none()
    if s is None and create:
        s = WarehouseStock(org_id=org_id, warehouse_id=wid, item_id=iid, quantity=money(0))
        db.add(s)
        await db.flush()
    return s


def _stock_to_row(stock: WarehouseStock, item: StoreItem) -> WarehouseStockRow:
    qty = money(stock.quantity)
    reorder = money(item.reorder_level or 0)
    return WarehouseStockRow(
        item_id=item.id, item_name=item.name, sku=item.sku, quantity=float(qty),
        reorder_level=float(reorder), low_stock=bool(reorder > 0 and qty <= reorder),
    )


@router.get("/warehouses", response_model=list[WarehouseResponse], dependencies=[_fin_write])
async def list_warehouses(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(
        select(Warehouse).where(Warehouse.org_id == current_user.org_id, Warehouse.is_deleted == False)  # noqa: E712
        .order_by(Warehouse.name)
    )).scalars().all()
    return [await _warehouse_response(db, w) for w in rows]


@router.post("/warehouses", response_model=WarehouseResponse, status_code=201, dependencies=[_fin_write])
async def create_warehouse(payload: WarehouseCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    w = Warehouse(name=payload.name, location=payload.location, notes=payload.notes, is_active=True, org_id=current_user.org_id)
    db.add(w)
    await db.flush()
    return await _warehouse_response(db, w)


@router.patch("/warehouses/{warehouse_id}", response_model=WarehouseResponse, dependencies=[_fin_write])
async def update_warehouse(warehouse_id: str, payload: WarehouseUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    w = await _load_warehouse(db, warehouse_id, current_user.org_id)
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(w, f, v)
    await db.flush()
    return await _warehouse_response(db, w)


@router.delete("/warehouses/{warehouse_id}", status_code=204, dependencies=[_fin_write])
async def delete_warehouse(warehouse_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    w = await _load_warehouse(db, warehouse_id, current_user.org_id)
    held = (await db.execute(
        select(func.coalesce(func.sum(WarehouseStock.quantity), 0)).where(WarehouseStock.warehouse_id == w.id)
    )).scalar() or 0
    if money(held) > 0:
        raise HTTPException(status_code=409, detail="Warehouse still holds stock — transfer or issue it out first.")
    w.is_deleted = True
    w.deleted_at = datetime.now(timezone.utc)
    await db.flush()


@router.get("/warehouses/{warehouse_id}/stock", response_model=list[WarehouseStockRow], dependencies=[_fin_write])
async def warehouse_stock(warehouse_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    await _load_warehouse(db, warehouse_id, current_user.org_id)
    rows = (await db.execute(
        select(WarehouseStock, StoreItem)
        .join(StoreItem, StoreItem.id == WarehouseStock.item_id)
        .where(WarehouseStock.warehouse_id == warehouse_id, WarehouseStock.quantity > 0)
        .order_by(StoreItem.name)
    )).all()
    return [_stock_to_row(s, it) for s, it in rows]


@router.post("/warehouse/receive", response_model=list[WarehouseStockRow], status_code=201, dependencies=[_fin_write])
async def warehouse_receive(payload: StockReceive, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Receive stock INTO a warehouse (increments that location's on-hand)."""
    await _load_warehouse(db, payload.warehouse_id, current_user.org_id)
    item = await _load_item(db, payload.item_id, current_user.org_id)
    s = await _stock(db, payload.warehouse_id, item.id, current_user.org_id, create=True)
    s.quantity = money(money(s.quantity) + money(payload.quantity))
    await db.flush()
    return [_stock_to_row(s, item)]


@router.post("/warehouse/issue", response_model=list[WarehouseStockRow], status_code=201, dependencies=[_fin_write])
async def warehouse_issue(payload: StockIssue, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Issue stock OUT of a warehouse (consumption / damage / write-off)."""
    await _load_warehouse(db, payload.warehouse_id, current_user.org_id)
    item = await _load_item(db, payload.item_id, current_user.org_id)
    s = await _stock(db, payload.warehouse_id, item.id, current_user.org_id)
    qty = money(payload.quantity)
    if s is None or money(s.quantity) < qty:
        have = money(s.quantity) if s else money(0)
        raise HTTPException(status_code=422, detail=f"Not enough stock: {have} on hand, {qty} requested.")
    s.quantity = money(money(s.quantity) - qty)
    await db.flush()
    return [_stock_to_row(s, item)]


@router.post("/warehouse/transfer", response_model=list[WarehouseStockRow], status_code=201, dependencies=[_fin_write])
async def warehouse_transfer(payload: StockTransfer, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Transfer stock between two warehouses (out of source, into destination)."""
    if payload.from_warehouse_id == payload.to_warehouse_id:
        raise HTTPException(status_code=422, detail="Source and destination warehouses must differ.")
    await _load_warehouse(db, payload.from_warehouse_id, current_user.org_id)
    await _load_warehouse(db, payload.to_warehouse_id, current_user.org_id)
    item = await _load_item(db, payload.item_id, current_user.org_id)
    qty = money(payload.quantity)
    src = await _stock(db, payload.from_warehouse_id, item.id, current_user.org_id)
    if src is None or money(src.quantity) < qty:
        have = money(src.quantity) if src else money(0)
        raise HTTPException(status_code=422, detail=f"Not enough stock in source: {have} on hand, {qty} requested.")
    dst = await _stock(db, payload.to_warehouse_id, item.id, current_user.org_id, create=True)
    src.quantity = money(money(src.quantity) - qty)
    dst.quantity = money(money(dst.quantity) + qty)
    await db.flush()
    return [_stock_to_row(src, item), _stock_to_row(dst, item)]


# ── Store Pickup Unit ─────────────────────────────────────────────────────────────
# Configure the points where students collect store purchases, and track each
# collection ticket from `pending` → `collected` (or `cancelled`).
#
# RBAC: point config + ticket create/cancel/delete gate on `payments:write` (the
# finance-clerk gate). The `/pickups/{id}/collect` action is the exception — it
# accepts EITHER `store:sell` OR `payments:write` (see `_pickup_collect`), because
# handing an item over is a daily till-counter task with no money/ledger impact and
# is usually done by the same cashier who rang up the sale.

async def _load_pickup_point(db: AsyncSession, pid: str, org_id: str) -> PickupPoint:
    p = (await db.execute(
        select(PickupPoint).where(
            PickupPoint.id == pid, PickupPoint.org_id == org_id, PickupPoint.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Pickup point not found.")
    return p


async def _pending_at_point(db: AsyncSession, point_id: str) -> int:
    n = (await db.execute(
        select(func.count(Pickup.id)).where(
            Pickup.pickup_point_id == point_id, Pickup.status == "pending", Pickup.is_deleted == False)  # noqa: E712
    )).scalar() or 0
    return int(n)


async def _pickup_point_response(db: AsyncSession, p: PickupPoint) -> PickupPointResponse:
    return PickupPointResponse(
        id=p.id, name=p.name, location=p.location, is_active=p.is_active, notes=p.notes,
        pending_count=await _pending_at_point(db, p.id),
        created_at=p.created_at, org_id=p.org_id,
    )


async def _load_pickup(db: AsyncSession, pid: str, org_id: str) -> Pickup:
    p = (await db.execute(
        select(Pickup).where(
            Pickup.id == pid, Pickup.org_id == org_id, Pickup.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Pickup not found.")
    return p


def _pickup_response(p: Pickup, point_name: str | None) -> PickupResponse:
    return PickupResponse(
        id=p.id, pickup_point_id=p.pickup_point_id, pickup_point_name=point_name,
        student_id=p.student_id, customer_name=p.customer_name, description=p.description,
        reference=p.reference, status=p.status, collected_at=p.collected_at,
        collected_by=p.collected_by, notes=p.notes, created_at=p.created_at, org_id=p.org_id,
    )


@router.get("/pickup-points", response_model=list[PickupPointResponse], dependencies=[_fin_write])
async def list_pickup_points(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(
        select(PickupPoint).where(PickupPoint.org_id == current_user.org_id, PickupPoint.is_deleted == False)  # noqa: E712
        .order_by(PickupPoint.name)
    )).scalars().all()
    return [await _pickup_point_response(db, p) for p in rows]


@router.post("/pickup-points", response_model=PickupPointResponse, status_code=201, dependencies=[_fin_write])
async def create_pickup_point(payload: PickupPointCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = PickupPoint(name=payload.name, location=payload.location, notes=payload.notes, is_active=True, org_id=current_user.org_id)
    db.add(p)
    await db.flush()
    return await _pickup_point_response(db, p)


@router.patch("/pickup-points/{point_id}", response_model=PickupPointResponse, dependencies=[_fin_write])
async def update_pickup_point(point_id: str, payload: PickupPointUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = await _load_pickup_point(db, point_id, current_user.org_id)
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, f, v)
    await db.flush()
    return await _pickup_point_response(db, p)


@router.delete("/pickup-points/{point_id}", status_code=204, dependencies=[_fin_write])
async def delete_pickup_point(point_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = await _load_pickup_point(db, point_id, current_user.org_id)
    if await _pending_at_point(db, p.id) > 0:
        raise HTTPException(status_code=409, detail="Pickup point still has pending collections — collect or cancel them first.")
    p.is_deleted = True
    p.deleted_at = datetime.now(timezone.utc)
    await db.flush()


@router.get("/pickups", response_model=list[PickupResponse], dependencies=[_fin_write])
async def list_pickups(
    status: str | None = Query(None),
    pickup_point_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(Pickup, PickupPoint.name).where(
        Pickup.org_id == current_user.org_id, Pickup.is_deleted == False)  # noqa: E712
    q = q.outerjoin(PickupPoint, PickupPoint.id == Pickup.pickup_point_id)
    if status:
        q = q.where(Pickup.status == status)
    if pickup_point_id:
        q = q.where(Pickup.pickup_point_id == pickup_point_id)
    q = q.order_by(Pickup.created_at.desc())
    rows = (await db.execute(q)).all()
    return [_pickup_response(p, name) for p, name in rows]


@router.post("/pickups", response_model=PickupResponse, status_code=201, dependencies=[_fin_write])
async def create_pickup(payload: PickupCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    point_name: str | None = None
    if payload.pickup_point_id:
        point = await _load_pickup_point(db, payload.pickup_point_id, current_user.org_id)
        point_name = point.name
    customer_name = payload.customer_name
    if payload.student_id:
        student = (await db.execute(
            select(Student).where(
                Student.id == payload.student_id, Student.org_id == current_user.org_id, Student.is_deleted == False)  # noqa: E712
        )).scalar_one_or_none()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found in your organisation.")
        if not customer_name:
            customer_name = f"{student.first_name} {student.last_name}".strip()
    p = Pickup(
        pickup_point_id=payload.pickup_point_id, student_id=payload.student_id,
        customer_name=customer_name, description=payload.description, reference=payload.reference,
        status="pending", notes=payload.notes, org_id=current_user.org_id,
    )
    db.add(p)
    await db.flush()
    return _pickup_response(p, point_name)


@router.post("/pickups/{pickup_id}/collect", response_model=PickupResponse, dependencies=[_pickup_collect])
async def collect_pickup(pickup_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = await _load_pickup(db, pickup_id, current_user.org_id)
    if p.status != "pending":
        raise HTTPException(status_code=409, detail=f"Pickup is already {p.status}.")
    p.status = "collected"
    p.collected_at = datetime.now(timezone.utc)
    p.collected_by = current_user.id
    await db.flush()
    name = None
    if p.pickup_point_id:
        name = (await db.execute(select(PickupPoint.name).where(PickupPoint.id == p.pickup_point_id))).scalar_one_or_none()
    return _pickup_response(p, name)


@router.post("/pickups/{pickup_id}/cancel", response_model=PickupResponse, dependencies=[_fin_write])
async def cancel_pickup(pickup_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = await _load_pickup(db, pickup_id, current_user.org_id)
    if p.status != "pending":
        raise HTTPException(status_code=409, detail=f"Pickup is already {p.status}.")
    p.status = "cancelled"
    await db.flush()
    name = None
    if p.pickup_point_id:
        name = (await db.execute(select(PickupPoint.name).where(PickupPoint.id == p.pickup_point_id))).scalar_one_or_none()
    return _pickup_response(p, name)


@router.delete("/pickups/{pickup_id}", status_code=204, dependencies=[_fin_write])
async def delete_pickup(pickup_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = await _load_pickup(db, pickup_id, current_user.org_id)
    p.is_deleted = True
    p.deleted_at = datetime.now(timezone.utc)
    await db.flush()
