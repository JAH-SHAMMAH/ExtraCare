"""Schemas for Finance & Accounting (Batch 5).

Money is accepted as ``Decimal`` (parsed exactly from "100.00" or 100) and
returned as ``float`` for the frontend. org_id pinned server-side; responses are
built by the router so they can carry resolved account/student names.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


ACCOUNT_TYPES = {"asset", "liability", "equity", "income", "expense"}


# ── Chart of Accounts ──────────────────────────────────────────────────────────

class LedgerAccountCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=150)
    type: str
    parent_id: Optional[str] = None
    description: Optional[str] = None


class LedgerAccountUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1, max_length=40)
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    parent_id: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class LedgerAccountResponse(BaseModel):
    id: str
    code: str
    name: str
    type: str
    parent_id: Optional[str]
    description: Optional[str]
    is_active: bool
    created_at: datetime
    org_id: str


# ── Accounting Periods ─────────────────────────────────────────────────────────

class PeriodCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    start_date: date
    end_date: date


class PeriodResponse(BaseModel):
    id: str
    name: str
    start_date: date
    end_date: date
    status: str
    locked_at: Optional[datetime]
    locked_by: Optional[str]
    created_at: datetime
    org_id: str


# ── Journal (general ledger) ───────────────────────────────────────────────────

class JournalLineInput(BaseModel):
    account_id: str
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    description: Optional[str] = None


class ManualJournalCreate(BaseModel):
    entry_date: date
    memo: Optional[str] = None
    lines: list[JournalLineInput] = Field(min_length=2)


class JournalLineResponse(BaseModel):
    id: str
    account_id: str
    account_code: Optional[str]
    account_name: Optional[str]
    debit: float
    credit: float
    description: Optional[str]


class JournalEntryResponse(BaseModel):
    id: str
    entry_date: date
    memo: Optional[str]
    source: str
    source_id: Optional[str]
    status: str
    period_id: Optional[str]
    posted_by: Optional[str]
    posted_at: Optional[datetime]
    reversal_of_id: Optional[str]
    reversed_by_id: Optional[str]
    reversed_at: Optional[datetime]
    total: float
    lines: list[JournalLineResponse]
    created_at: datetime
    org_id: str


class JournalListResponse(BaseModel):
    items: list[JournalEntryResponse]
    total: int
    page: int
    page_size: int


# ── Invoices ───────────────────────────────────────────────────────────────────

class InvoiceLineInput(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = Decimal("0")
    income_account_id: str


class InvoiceCreate(BaseModel):
    number: Optional[str] = None  # auto-generated if omitted
    customer_name: str = Field(min_length=1, max_length=200)
    student_id: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    memo: Optional[str] = None
    receivable_account_id: str
    lines: list[InvoiceLineInput] = Field(min_length=1)


class InvoiceUpdate(BaseModel):
    customer_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    student_id: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    memo: Optional[str] = None
    receivable_account_id: Optional[str] = None
    lines: Optional[list[InvoiceLineInput]] = None  # replaces all lines when present


class InvoiceLineResponse(BaseModel):
    id: str
    description: str
    quantity: float
    unit_price: float
    amount: float
    income_account_id: str
    income_account_name: Optional[str]


class InvoiceResponse(BaseModel):
    id: str
    number: str
    customer_name: str
    student_id: Optional[str]
    invoice_date: Optional[date]
    due_date: Optional[date]
    status: str
    total: float
    memo: Optional[str]
    receivable_account_id: Optional[str]
    journal_entry_id: Optional[str]
    payment_entry_id: Optional[str]
    created_by: Optional[str]
    posted_by: Optional[str]
    posted_at: Optional[datetime]
    lines: list[InvoiceLineResponse]
    created_at: datetime
    org_id: str


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int
    page: int
    page_size: int


class PaymentRequest(BaseModel):
    cash_account_id: str
    amount: Optional[Decimal] = None  # defaults to invoice total
    payment_date: Optional[date] = None


# ── Payroll ────────────────────────────────────────────────────────────────────

class PayslipInput(BaseModel):
    staff_user_id: Optional[str] = None
    staff_name: Optional[str] = None
    gross: Decimal = Decimal("0")
    deductions: Decimal = Decimal("0")
    notes: Optional[str] = None


class PayrollRunCreate(BaseModel):
    period_label: str = Field(min_length=1, max_length=80)
    run_date: Optional[date] = None
    expense_account_id: str
    net_account_id: str
    deductions_account_id: Optional[str] = None
    payslips: list[PayslipInput] = Field(min_length=1)


class PayslipResponse(BaseModel):
    id: str
    staff_user_id: Optional[str]
    staff_name: Optional[str]
    gross: float
    deductions: float
    net: float
    notes: Optional[str]


class PayrollRunResponse(BaseModel):
    id: str
    period_label: str
    run_date: Optional[date]
    status: str
    total_gross: float
    total_deductions: float
    total_net: float
    expense_account_id: Optional[str]
    net_account_id: Optional[str]
    deductions_account_id: Optional[str]
    journal_entry_id: Optional[str]
    created_by: Optional[str]
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    payslips: list[PayslipResponse]
    created_at: datetime
    org_id: str


class PayrollListResponse(BaseModel):
    items: list[PayrollRunResponse]
    total: int
    page: int
    page_size: int


# ── Financial Statements (read-only, derived from the ledger) ─────────────────────

class TrialBalanceRow(BaseModel):
    account_id: str
    code: str
    name: str
    type: str
    debit: float
    credit: float
    balance: float   # normal-balance signed (debit-normal: dr−cr; credit-normal: cr−dr)


class FinancialStatements(BaseModel):
    as_of: Optional[date]
    trial_balance: list[TrialBalanceRow]
    total_debit: float
    total_credit: float
    balanced: bool                 # trial balance: Σdebit == Σcredit
    # Income statement
    income: float
    expense: float
    net_income: float
    # Balance sheet
    assets: float
    liabilities: float
    equity: float
    balance_sheet_balanced: bool   # assets == liabilities + equity + net_income


# ── Salary Advance ────────────────────────────────────────────────────────────────

class SalaryAdvanceCreate(BaseModel):
    staff_user_id: str
    amount: Decimal = Field(gt=0)
    reason: Optional[str] = None
    notes: Optional[str] = None


class SalaryAdvanceApprove(BaseModel):
    # Cash/bank account to disburse FROM. Optional — server auto-picks a cash asset
    # account (first asset that isn't the Staff Advances account) when omitted.
    cash_account_id: Optional[str] = None


class SalaryAdvanceRepay(BaseModel):
    amount: Decimal = Field(gt=0)
    method: str = "payroll"              # payroll | cash
    cash_account_id: Optional[str] = None
    payroll_run_id: Optional[str] = None


class SalaryAdvanceResponse(BaseModel):
    id: str
    staff_user_id: str
    staff_name: Optional[str]
    amount: float
    reason: Optional[str]
    status: str
    amount_repaid: float
    outstanding: float                   # DERIVED: amount − amount_repaid
    requested_by: Optional[str]
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    disburse_entry_id: Optional[str]
    notes: Optional[str]
    created_at: datetime
    org_id: str


# ── Bonus / Reduction Pack (pay adjustments) ──────────────────────────────────────

PAY_ADJUSTMENT_KINDS = {"bonus", "reduction"}


class PayAdjustmentItemInput(BaseModel):
    staff_user_id: Optional[str] = None
    staff_name: Optional[str] = None
    amount: Decimal = Field(gt=0)
    note: Optional[str] = None


class PayAdjustmentCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    kind: str = "bonus"                   # bonus | reduction
    reason: Optional[str] = None
    # bonus:     Dr expense_account / Cr settle_account
    # reduction: Dr settle_account  / Cr expense_account
    expense_account_id: str               # P&L side (bonus expense OR reduction income/offset)
    settle_account_id: str                # cash / payable side
    items: list[PayAdjustmentItemInput] = Field(min_length=1)


class PayAdjustmentItemResponse(BaseModel):
    id: str
    staff_user_id: Optional[str]
    staff_name: Optional[str]
    amount: float
    note: Optional[str]


class PayAdjustmentResponse(BaseModel):
    id: str
    label: str
    kind: str
    status: str
    total_amount: float
    reason: Optional[str]
    expense_account_id: Optional[str]
    settle_account_id: Optional[str]
    journal_entry_id: Optional[str]
    created_by: Optional[str]
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    items: list[PayAdjustmentItemResponse]
    created_at: datetime
    org_id: str


# ── Requisitions / Request Form ───────────────────────────────────────────────────

class RequisitionItemInput(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0)
    note: Optional[str] = None


class RequisitionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    department: Optional[str] = None
    category: Optional[str] = None
    justification: Optional[str] = None
    notes: Optional[str] = None
    expense_account_id: str               # what expense bucket
    settle_account_id: str                # cash / payable funding source
    items: list[RequisitionItemInput] = Field(min_length=1)


class RequisitionItemResponse(BaseModel):
    id: str
    description: str
    quantity: float
    unit_cost: float
    amount: float
    note: Optional[str]


class RequisitionResponse(BaseModel):
    id: str
    title: str
    department: Optional[str]
    category: Optional[str]
    status: str
    total_amount: float
    justification: Optional[str]
    notes: Optional[str]
    expense_account_id: Optional[str]
    settle_account_id: Optional[str]
    journal_entry_id: Optional[str]
    requested_by: Optional[str]
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    items: list[RequisitionItemResponse]
    created_at: datetime
    org_id: str


# ── Finance Reports (read-only, period-scoped from the ledger) ────────────────────

class ReportAccountRow(BaseModel):
    account_id: str
    code: str
    name: str
    type: str            # income | expense
    amount: float        # income: credit−debit · expense: debit−credit (period)


class ReportSourceRow(BaseModel):
    source: str          # payroll | requisition | pay_adjustment | petty_cash | invoice | …
    income: float
    expense: float


class IncomeExpenseReport(BaseModel):
    start: Optional[date]
    end: Optional[date]
    income: float
    expense: float
    net: float           # income − expense (for the period)
    by_account: list[ReportAccountRow]
    by_source: list[ReportSourceRow]


# ── Fee Discounts (Manage Discounts) ──────────────────────────────────────────────

DISCOUNT_TYPES = {"fixed", "percent"}


class DiscountCreate(BaseModel):
    student_id: str
    discount_type: str = "fixed"          # fixed | percent
    value: Decimal = Field(gt=0)          # ₦ for fixed, % for percent (of total fee)
    reason: Optional[str] = None
    notes: Optional[str] = None


class DiscountResponse(BaseModel):
    id: str
    student_id: str
    student_name: Optional[str]
    fee_record_id: Optional[str]
    discount_type: str
    value: float
    amount: float                         # computed ₦ discount
    reason: Optional[str]
    status: str
    proposed_by: Optional[str]
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    journal_entry_id: Optional[str]
    created_at: datetime
    org_id: str


# ── Fee Assignment (populate StudentFeeRecord) ────────────────────────────────────

class _FeeBreakdown(BaseModel):
    tuition_fee: Decimal = Decimal("0")
    exam_fee: Decimal = Decimal("0")
    activity_fee: Decimal = Decimal("0")
    transport_fee: Decimal = Decimal("0")
    hostel_fee: Decimal = Decimal("0")
    other_fees: Decimal = Decimal("0")


class FeeRecordCreate(_FeeBreakdown):
    student_id: str
    term: str = Field(min_length=1, max_length=50)
    session_year: str = Field(min_length=1, max_length=10)
    due_date: Optional[date] = None


class FeeRecordUpdate(_FeeBreakdown):
    # All breakdown fields default to 0; the update REPLACES the breakdown and
    # recomputes total/outstanding (paid + discount preserved).
    due_date: Optional[date] = None


class ClassFeeAssign(_FeeBreakdown):
    class_id: str
    term: str = Field(min_length=1, max_length=50)
    session_year: str = Field(min_length=1, max_length=10)
    due_date: Optional[date] = None


class FeeRecordResponse(BaseModel):
    id: str
    student_id: str
    student_name: Optional[str]
    term: str
    session_year: str
    tuition_fee: float
    exam_fee: float
    activity_fee: float
    transport_fee: float
    hostel_fee: float
    other_fees: float
    total_fee: float
    paid_amount: float
    discount_amount: float
    outstanding_balance: float
    is_paid: bool
    payment_status: str
    due_date: Optional[date]
    created_at: datetime
    org_id: str


class ClassFeeAssignResult(BaseModel):
    created: int
    skipped: int              # students who already had a record for this term/session
    total_students: int
    records: list[FeeRecordResponse]


class ClassOption(BaseModel):
    """Lightweight class option for finance dropdowns (Fee Assignment)."""
    id: str
    name: str
    student_count: int


# ── Bank Accounts (Account Numbers) ───────────────────────────────────────────────

class BankAccountCreate(BaseModel):
    bank_name: str = Field(min_length=1, max_length=120)
    account_name: str = Field(min_length=1, max_length=150)
    account_number: str = Field(min_length=1, max_length=40)
    bank_code: Optional[str] = None
    account_type: Optional[str] = None      # current | savings | domiciliary
    purpose: Optional[str] = None
    is_primary: bool = False
    is_active: bool = True
    notes: Optional[str] = None
    ledger_account_id: Optional[str] = None


class BankAccountUpdate(BaseModel):
    bank_name: Optional[str] = None
    account_name: Optional[str] = None
    account_number: Optional[str] = None
    bank_code: Optional[str] = None
    account_type: Optional[str] = None
    purpose: Optional[str] = None
    is_primary: Optional[bool] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None
    ledger_account_id: Optional[str] = None


class BankAccountResponse(BaseModel):
    id: str
    bank_name: str
    account_name: str
    account_number: str
    bank_code: Optional[str]
    account_type: Optional[str]
    purpose: Optional[str]
    is_primary: bool
    is_active: bool
    notes: Optional[str]
    ledger_account_id: Optional[str] = None
    balance: Optional[float] = None       # current balance (derived from the cash ledger account)
    created_at: datetime
    org_id: str


class BankAccountPublic(BaseModel):
    """The 'pay to' subset shown to fee-payers (parents) — no internal fields
    (no notes / is_active / org_id)."""
    bank_name: str
    account_name: str
    account_number: str
    bank_code: Optional[str]
    account_type: Optional[str]
    purpose: Optional[str]


# ── Accounts Setup (default posting accounts) ─────────────────────────────────────

class FinanceSettingsUpdate(BaseModel):
    # Present-and-null clears a default; omitted leaves it unchanged.
    default_cash_account_id: Optional[str] = None
    default_income_account_id: Optional[str] = None
    default_receivable_account_id: Optional[str] = None
    default_expense_account_id: Optional[str] = None


class FinanceSettingsResponse(BaseModel):
    default_cash_account_id: Optional[str]
    default_cash_account_name: Optional[str]
    default_income_account_id: Optional[str]
    default_income_account_name: Optional[str]
    default_receivable_account_id: Optional[str]
    default_receivable_account_name: Optional[str]
    default_expense_account_id: Optional[str]
    default_expense_account_name: Optional[str]
    org_id: str


# ── Payment Gateways (per-org gateway credentials; secrets encrypted at rest) ──────
# Backed by TenantPaymentSettings (the model the billing resolver consumes). The
# UI exposes this subset of PaymentProvider; only Paystack is wired into live
# consumption today (resolver) — Remita/Flutterwave are stored, not yet consumed.

GATEWAY_MODES = {"test", "live"}
GATEWAY_PROVIDERS = ("paystack", "remita", "flutterwave")


class PaymentGatewayCreate(BaseModel):
    provider: str                                   # paystack | remita | flutterwave
    label: Optional[str] = Field(default=None, max_length=120)
    mode: str = "test"                              # test | live
    public_key: Optional[str] = Field(default=None, max_length=255)
    secret_key: Optional[str] = None               # write-only; stored encrypted (Remita: the API key)
    webhook_secret: Optional[str] = None           # write-only; stored encrypted
    # Remita-only, non-secret identifiers (stored in metadata, shown in the UI).
    merchant_id: Optional[str] = Field(default=None, max_length=120)
    service_type_id: Optional[str] = Field(default=None, max_length=120)
    is_active: bool = True


class PaymentGatewayUpdate(BaseModel):
    label: Optional[str] = None
    mode: Optional[str] = None
    public_key: Optional[str] = None
    # Present + non-empty ROTATES the secret; omitted leaves it untouched. Sending
    # an empty string CLEARS it. Secrets are never echoed back.
    secret_key: Optional[str] = None
    webhook_secret: Optional[str] = None
    merchant_id: Optional[str] = None
    service_type_id: Optional[str] = None
    is_active: Optional[bool] = None


class PaymentGatewayResponse(BaseModel):
    """Safe projection — NEVER carries plaintext secrets. The UI only learns
    whether a secret is set (booleans) + the public, non-sensitive fields.
    Secrets are decrypted only at the actual point of use (a gateway call),
    never to render this page."""
    id: str
    provider: str
    label: Optional[str]
    mode: str
    public_key: Optional[str]
    secret_key_set: bool
    webhook_secret_set: bool
    merchant_id: Optional[str] = None        # Remita (non-secret)
    service_type_id: Optional[str] = None    # Remita (non-secret)
    is_active: bool
    created_at: datetime
    org_id: str


# ── Broad View (finance reporting hub) ────────────────────────────────────────

class BroadViewDistItem(BaseModel):
    head: str
    amount: float


class BroadViewBank(BaseModel):
    id: str
    bank_name: str
    account_name: str
    account_number: str
    balance: float


class BroadViewDashboard(BaseModel):
    invoices: int
    full_payments: int
    part_payments: int
    bank_accounts: int
    total_revenue: float
    total_full_payment: float
    total_part_payment: float
    total_debt: float
    distribution: list[BroadViewDistItem]
    banks: list[BroadViewBank]
    session: Optional[str] = None
    term: Optional[str] = None


# ── Broad View: report tabs ───────────────────────────────────────────────────

class AccountHeadRow(BaseModel):
    account_name: str
    total_invoice: int
    total_receipt: int
    invoice_charge: float
    amount_paid: float


class AccountHeadSummary(BaseModel):
    items: list[AccountHeadRow]


class TermlyFeeRow(BaseModel):
    fee: str
    amount: float


class TermlySummary(BaseModel):
    items: list[TermlyFeeRow]
    total: float
    session: Optional[str] = None
    term: Optional[str] = None


class DiscountLogRow(BaseModel):
    id: str
    student_name: Optional[str]
    discount_type: str
    value: float
    amount: float
    reason: Optional[str]
    status: str
    created_at: datetime


class DiscountLog(BaseModel):
    items: list[DiscountLogRow]
    total_discount: float


class WalletLogRow(BaseModel):
    id: str
    wallet_name: Optional[str]
    memo: Optional[str]
    credit: float
    debit: float
    created_at: datetime


class WalletLog(BaseModel):
    items: list[WalletLogRow]
    total_credit: float
    total_debit: float
