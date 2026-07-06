"""Schemas for Finance ops (Batch 5, second half): Petty Cash & Budget, Cash
Transactions, Store & Inventory. Amounts: Decimal in / float out. All postings
route through the shared ledger engine.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


CASH_TYPES = {"receipt", "payment"}
STOCK_MOVE_TYPES = {"out", "adjust"}


# ── Budget ──────────────────────────────────────────────────────────────────────

class BudgetCreate(BaseModel):
    account_id: str
    period_label: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    amount: Decimal = Decimal("0")
    notes: Optional[str] = None


class BudgetUpdate(BaseModel):
    period_label: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    amount: Optional[Decimal] = None
    notes: Optional[str] = None


class BudgetResponse(BaseModel):
    id: str
    account_id: str
    account_name: Optional[str]
    period_label: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    amount: float
    spent: float = 0.0
    remaining: float = 0.0          # amount − spent (can be negative = over budget)
    notes: Optional[str]
    created_at: datetime
    org_id: str


# ── Petty Cash ──────────────────────────────────────────────────────────────────

class PettyCashCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    expense_account_id: str
    cash_account_id: str
    txn_date: Optional[date] = None
    description: Optional[str] = None
    category: Optional[str] = None


class PettyCashResponse(BaseModel):
    id: str
    txn_date: Optional[date]
    description: Optional[str]
    amount: float
    expense_account_id: str
    expense_account_name: Optional[str]
    cash_account_id: str
    category: Optional[str]
    status: str
    journal_entry_id: Optional[str]
    # Soft over-budget signal (non-blocking); None when within budget / no budget set.
    warning: Optional[str] = None
    created_at: datetime
    org_id: str


class PettyCashListResponse(BaseModel):
    items: list[PettyCashResponse]
    total: int
    page: int
    page_size: int


# ── Cash Transactions ───────────────────────────────────────────────────────────

class CashTxnCreate(BaseModel):
    type: str  # receipt | payment
    amount: Decimal = Field(gt=0)
    cash_account_id: str
    counter_account_id: str
    txn_date: Optional[date] = None
    counterparty: Optional[str] = None
    description: Optional[str] = None


class CashTxnResponse(BaseModel):
    id: str
    txn_date: Optional[date]
    type: str
    amount: float
    cash_account_id: str
    cash_account_name: Optional[str]
    counter_account_id: str
    counter_account_name: Optional[str]
    counterparty: Optional[str]
    description: Optional[str]
    status: str
    journal_entry_id: Optional[str]
    created_at: datetime
    org_id: str


class CashTxnListResponse(BaseModel):
    items: list[CashTxnResponse]
    total: int
    page: int
    page_size: int


# ── Store & Inventory ───────────────────────────────────────────────────────────

class StoreItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sku: Optional[str] = None
    unit_price: Decimal = Decimal("0")
    cost_price: Decimal = Decimal("0")
    reorder_level: Decimal = Decimal("0")


class StoreItemUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    sku: Optional[str] = None
    unit_price: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    reorder_level: Optional[Decimal] = None
    is_active: Optional[bool] = None


class StoreItemResponse(BaseModel):
    id: str
    name: str
    sku: Optional[str]
    unit_price: float
    cost_price: float
    quantity: float
    reorder_level: float
    is_active: bool
    low_stock: bool
    created_at: datetime
    org_id: str


class StoreItemListResponse(BaseModel):
    items: list[StoreItemResponse]
    total: int
    page: int
    page_size: int


class PurchaseCreate(BaseModel):
    """A stock purchase (stock-in). Posts Dr Inventory / Cr funding."""
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(gt=0)
    inventory_account_id: str
    funding_account_id: str
    purchase_date: Optional[date] = None
    note: Optional[str] = None


class StockAdjustCreate(BaseModel):
    """A non-financial stock change (issue out / adjustment) — quantity only."""
    type: str  # out | adjust
    quantity: Decimal = Field(gt=0)
    note: Optional[str] = None


class StockMovementResponse(BaseModel):
    id: str
    item_id: str
    type: str
    quantity: float
    unit_cost: float
    note: Optional[str]
    journal_entry_id: Optional[str]
    created_at: datetime
    org_id: str


# ── Store Front Desk (POS sales) ──────────────────────────────────────────────────

class StoreSaleLineInput(BaseModel):
    item_id: str
    quantity: Decimal = Field(gt=0)


class StoreSaleCreate(BaseModel):
    customer_name: Optional[str] = None
    student_id: Optional[str] = None
    discount: Decimal = Decimal("0")           # overall discount off the subtotal
    payment_method: str = "cash"               # cash | transfer | pos
    cash_account_id: Optional[str] = None      # where the money lands (defaults resolved server-side)
    income_account_id: Optional[str] = None    # sales income (defaults resolved server-side)
    reference: Optional[str] = None
    notes: Optional[str] = None
    lines: list[StoreSaleLineInput] = Field(min_length=1)


class StoreSaleLineResponse(BaseModel):
    id: str
    item_id: Optional[str]
    item_name: Optional[str]
    quantity: float
    unit_price: float
    amount: float


class StoreSaleResponse(BaseModel):
    id: str
    reference: Optional[str]
    customer_name: Optional[str]
    student_id: Optional[str]
    subtotal: float
    discount: float
    total: float
    payment_method: str
    status: str
    journal_entry_id: Optional[str]
    cashier_id: Optional[str]
    notes: Optional[str]
    lines: list[StoreSaleLineResponse]
    created_at: datetime
    org_id: str


# ── Sales Monitor (read-only analytics over completed store sales) ────────────────

class SalesTopItem(BaseModel):
    item_name: str
    quantity: float
    revenue: float


class SalesGroup(BaseModel):
    key: str
    label: str
    count: int
    revenue: float


class StoreSalesSummary(BaseModel):
    start: Optional[date]
    end: Optional[date]
    total_sales: int
    total_revenue: float
    average_sale: float
    top_items: list[SalesTopItem]
    by_payment: list[SalesGroup]
    by_cashier: list[SalesGroup]


# ── Warehouse (multi-location stock) ──────────────────────────────────────────────

class WarehouseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    location: Optional[str] = None
    notes: Optional[str] = None


class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class WarehouseResponse(BaseModel):
    id: str
    name: str
    location: Optional[str]
    is_active: bool
    notes: Optional[str]
    item_count: int          # distinct items on hand (quantity > 0)
    total_units: float       # sum of quantities held
    created_at: datetime
    org_id: str


class WarehouseStockRow(BaseModel):
    item_id: str
    item_name: str
    sku: Optional[str]
    quantity: float
    reorder_level: float
    low_stock: bool


class StockReceive(BaseModel):
    warehouse_id: str
    item_id: str
    quantity: Decimal = Field(gt=0)
    note: Optional[str] = None


class StockTransfer(BaseModel):
    from_warehouse_id: str
    to_warehouse_id: str
    item_id: str
    quantity: Decimal = Field(gt=0)
    note: Optional[str] = None


class StockIssue(BaseModel):
    warehouse_id: str
    item_id: str
    quantity: Decimal = Field(gt=0)
    note: Optional[str] = None


# ── Store Pickup Unit ─────────────────────────────────────────────────────────────

class PickupPointCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    location: Optional[str] = None
    notes: Optional[str] = None


class PickupPointUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class PickupPointResponse(BaseModel):
    id: str
    name: str
    location: Optional[str]
    is_active: bool
    notes: Optional[str]
    pending_count: int
    created_at: datetime
    org_id: str


class PickupCreate(BaseModel):
    pickup_point_id: Optional[str] = None
    student_id: Optional[str] = None
    customer_name: Optional[str] = None
    description: str = Field(min_length=1, max_length=255)
    reference: Optional[str] = None
    notes: Optional[str] = None


class PickupResponse(BaseModel):
    id: str
    pickup_point_id: Optional[str]
    pickup_point_name: Optional[str]
    student_id: Optional[str]
    customer_name: Optional[str]
    description: str
    reference: Optional[str]
    status: str
    collected_at: Optional[datetime]
    collected_by: Optional[str]
    notes: Optional[str]
    created_at: datetime
    org_id: str
