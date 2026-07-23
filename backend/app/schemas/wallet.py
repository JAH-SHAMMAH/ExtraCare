"""Schemas for Student Wallet / PocketMoney + Cooperative (Batch 6).

Balances are returned but DERIVED server-side from the subledger (never stored).
Amounts Decimal in / float out. org_id pinned server-side.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


WALLET_ENTRY_KINDS = {"top_up", "spend", "withdrawal"}
COOP_ENTRY_KINDS = {"contribution", "payout"}


# ── Wallet ──────────────────────────────────────────────────────────────────────

class WalletCreate(BaseModel):
    student_id: str
    spend_limit_daily: Optional[Decimal] = None


class WalletUpdate(BaseModel):
    spend_limit_daily: Optional[Decimal] = None
    is_active: Optional[bool] = None


class WalletResponse(BaseModel):
    id: str
    student_id: str
    student_name: Optional[str]
    # Parent-centric surface (Wallet Manager): the funding guardian shown per wallet.
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    class_name: Optional[str] = None
    spend_limit_daily: Optional[float]
    is_active: bool
    balance: float          # derived
    created_at: datetime
    org_id: str


class WalletListResponse(BaseModel):
    items: list[WalletResponse]
    total: int
    page: int
    page_size: int


class WalletEntryResponse(BaseModel):
    id: str
    kind: str
    signed_amount: float
    memo: Optional[str]
    journal_entry_id: Optional[str]
    reversed: bool
    created_at: datetime


class WalletDetailResponse(WalletResponse):
    entries: list[WalletEntryResponse]


class WalletSummaryResponse(BaseModel):
    """Wallet Manager dashboard cards — org-wide roll-up over non-reversed entries."""
    total_wallets: int
    active_wallets: int
    inactive_wallets: int
    total_balance: float
    total_topped_up: float
    total_spent: float


class WalletSettingsResponse(BaseModel):
    default_daily_limit: Optional[float] = None
    low_balance_threshold: Optional[float] = None
    notify_low_balance: bool = False
    allow_topup: bool = True
    org_id: str


class WalletSettingsUpdate(BaseModel):
    default_daily_limit: Optional[Decimal] = None
    low_balance_threshold: Optional[Decimal] = None
    notify_low_balance: Optional[bool] = None
    allow_topup: Optional[bool] = None


# ── Parent Wallet (Wallet Manager) ────────────────────────────────────────────

class ParentWalletChild(BaseModel):
    id: str
    name: str
    class_name: Optional[str] = None


class ParentWalletResponse(BaseModel):
    id: str
    user_id: str
    parent_name: Optional[str]
    parent_email: Optional[str]
    parent_phone: Optional[str]
    is_active: bool
    credit_total: float          # Σ credits (derived)
    debit_total: float           # Σ debits, positive (derived)
    balance: float               # credit − debit (derived)
    children: list[ParentWalletChild]
    created_at: datetime
    org_id: str


class ParentWalletListResponse(BaseModel):
    items: list[ParentWalletResponse]
    total: int
    page: int
    page_size: int


class ParentWalletEntryResponse(BaseModel):
    id: str
    kind: str                    # credit | debit
    signed_amount: float
    memo: Optional[str]
    journal_entry_id: Optional[str]
    reversed: bool
    created_at: datetime


class ParentWalletDetailResponse(ParentWalletResponse):
    entries: list[ParentWalletEntryResponse]


class ParentWalletSummaryResponse(BaseModel):
    """Wallet Manager dashboard cards."""
    total_credits: float
    today_credits: float
    total_debits: float
    today_debits: float
    cumulative_balance: float
    total_active_wallets: int


class ParentWalletSettingsResponse(BaseModel):
    auto_invoice_pay: bool = False
    correspondent_email: Optional[str] = None
    org_id: str


class ParentWalletSettingsUpdate(BaseModel):
    auto_invoice_pay: Optional[bool] = None
    correspondent_email: Optional[str] = None


class ParentCreditRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    cash_account_id: str
    txn_date: Optional[date] = None
    memo: Optional[str] = None


class ParentDebitRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    cash_account_id: str
    txn_date: Optional[date] = None
    memo: Optional[str] = None


class ParentWalletInitializeResponse(BaseModel):
    created: int                 # how many new wallets were initialized
    total_parents: int


# ── PocketMoney Manager ───────────────────────────────────────────────────────

class PocketMoneyItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    unit_price: Decimal = Field(ge=0)
    is_active: bool = True


class PocketMoneyItemUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    unit_price: Optional[Decimal] = Field(default=None, ge=0)
    is_active: Optional[bool] = None


class PocketMoneyItemResponse(BaseModel):
    id: str
    name: str
    unit_price: float
    is_active: bool
    org_id: str


class PocketMoneyTxnLine(BaseModel):
    item_id: str
    qty: int = Field(gt=0)


class PocketMoneyTxnCreate(BaseModel):
    # Target the student directly (wallet auto-created if missing) or an existing wallet.
    student_id: Optional[str] = None
    wallet_id: Optional[str] = None
    income_account_id: str
    lines: list[PocketMoneyTxnLine] = []     # itemised purchase
    amount: Optional[Decimal] = None         # or a direct amount (when no items)
    memo: Optional[str] = None
    txn_date: Optional[date] = None


class PocketMoneyStudentRow(BaseModel):
    student_id: str
    student_name: str
    parent_name: Optional[str]
    class_name: Optional[str]
    balance: float
    wallet_id: Optional[str]      # null = no wallet yet (created on first transaction)
    is_active: bool


class PocketMoneyStudentListResponse(BaseModel):
    items: list[PocketMoneyStudentRow]
    total: int
    page: int
    page_size: int
    today_total: float            # Σ pocket-money spends posted today (org-wide)


class PocketMoneyTxnResponse(BaseModel):
    id: str                      # the wallet entry id
    student_name: Optional[str]
    amount: float                # positive spend amount
    memo: Optional[str]
    journal_entry_id: Optional[str]
    reversed: bool
    created_at: datetime


class PocketMoneyTxnListResponse(BaseModel):
    items: list[PocketMoneyTxnResponse]
    total: int
    page: int
    page_size: int


class TopUpRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    cash_account_id: str
    txn_date: Optional[date] = None
    memo: Optional[str] = None


class WithdrawRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    cash_account_id: str
    txn_date: Optional[date] = None
    memo: Optional[str] = None


class SpendRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    income_account_id: str
    txn_date: Optional[date] = None
    memo: Optional[str] = None


# ── Cooperative ─────────────────────────────────────────────────────────────────

class CoopMemberCreate(BaseModel):
    member_name: str = Field(min_length=1, max_length=200)
    member_user_id: Optional[str] = None
    joined_on: Optional[date] = None


class CoopMemberResponse(BaseModel):
    id: str
    member_name: str
    member_user_id: Optional[str]
    is_active: bool
    joined_on: Optional[date]
    balance: float          # derived
    created_at: datetime
    org_id: str


class CoopMemberListResponse(BaseModel):
    items: list[CoopMemberResponse]
    total: int
    page: int
    page_size: int


class CoopEntryResponse(BaseModel):
    id: str
    kind: str
    signed_amount: float
    memo: Optional[str]
    journal_entry_id: Optional[str]
    reversed: bool
    created_at: datetime


class CoopMemberDetailResponse(CoopMemberResponse):
    entries: list[CoopEntryResponse]


class CoopMoveRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    cash_account_id: str
    txn_date: Optional[date] = None
    memo: Optional[str] = None


# ── Reconciliation ──────────────────────────────────────────────────────────────

class ReconciliationResponse(BaseModel):
    control_account: str          # the liability GL account
    gl_balance: float             # aggregate liability balance from the ledger
    subledger_total: float        # Σ derived per-holder balances
    balanced: bool
