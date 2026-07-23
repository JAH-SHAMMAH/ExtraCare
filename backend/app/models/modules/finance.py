"""Finance & Accounting models (Batch 5).

Centred on a double-entry ledger. The invariants live in the ledger SERVICE
(`app/services/ledger.py`) which is the ONLY path that writes JournalEntry rows;
the models add structural backstops (CHECK constraints on lines).

  • LedgerAccount    — Chart of Accounts (asset/liability/equity/income/expense)
  • AccountingPeriod — a financial period that can be LOCKED to block (back-)posting
  • JournalEntry     — an immutable, posted, balanced transaction header
  • JournalLine      — one debit OR credit line referencing a LedgerAccount
  • Invoice/InvoiceLine, PayrollRun/Payslip — feature drafts that POST to the ledger

All tenant-scoped. Money is Numeric(14,2); never float in the DB.
"""
from __future__ import annotations

from sqlalchemy import (
    Column, String, Text, Date, DateTime, Integer, Numeric, Boolean, ForeignKey,
    Index, UniqueConstraint, CheckConstraint,
)

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin

ACCOUNT_TYPES = ("asset", "liability", "equity", "income", "expense")


class LedgerAccount(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A Chart-of-Accounts node. ``code`` is unique per org."""
    __tablename__ = "ledger_accounts"

    code = Column(String(40), nullable=False)
    name = Column(String(150), nullable=False)
    type = Column(String(20), nullable=False)            # asset|liability|equity|income|expense
    parent_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "code", name="uq_ledger_accounts_org_code"),
        Index("ix_ledger_accounts_org_type", "org_id", "type"),
    )


class AccountingPeriod(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A financial period. When ``status == 'locked'`` the ledger service refuses
    to post (or back-date) any entry whose date falls inside it — protecting
    already-reported books from after-the-fact changes."""
    __tablename__ = "accounting_periods"

    name = Column(String(80), nullable=False)            # e.g. "2025/2026 Term 1"
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String(20), default="open", nullable=False)  # open | locked
    locked_at = Column(DateTime(timezone=True), nullable=True)
    locked_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_accounting_periods_org_dates", "org_id", "start_date", "end_date"),
    )


class JournalEntry(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """An immutable, balanced, POSTED transaction. Never edited/deleted in place;
    corrections are made by a reversing entry (``reversal_of_id`` / ``reversed_by_id``)."""
    __tablename__ = "journal_entries"

    entry_date = Column(Date, nullable=False, index=True)
    memo = Column(Text, nullable=True)
    source = Column(String(20), default="manual", nullable=False)  # manual|invoice|payroll|petty_cash|cash|store|reversal
    source_id = Column(String(36), nullable=True)
    status = Column(String(20), default="posted", nullable=False)  # posted (immutable)
    period_id = Column(String(36), ForeignKey("accounting_periods.id", ondelete="SET NULL"), nullable=True)
    posted_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    # Reversal linkage — immutability via correction, not mutation.
    reversal_of_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    reversed_by_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    reversed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_journal_entries_org_date", "org_id", "entry_date"),
        Index("ix_journal_entries_source", "source", "source_id"),
    )


class JournalLine(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """One side of a posting. Exactly one of debit/credit is > 0 (CHECK-enforced)."""
    __tablename__ = "journal_lines"

    entry_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    debit = Column(Numeric(14, 2), default=0, nullable=False)
    credit = Column(Numeric(14, 2), default=0, nullable=False)
    description = Column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0", name="ck_journal_lines_nonneg"),
        CheckConstraint("NOT (debit > 0 AND credit > 0)", name="ck_journal_lines_one_sided"),
        CheckConstraint("(debit > 0) OR (credit > 0)", name="ck_journal_lines_has_amount"),
        Index("ix_journal_lines_entry_org", "entry_id", "org_id"),
        Index("ix_journal_lines_account_org", "account_id", "org_id"),
    )


# ── Invoice Center ─────────────────────────────────────────────────────────────

class Invoice(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A sales invoice. A draft is editable; once POSTED it is immutable and is
    backed by a balanced JournalEntry (Dr Receivable / Cr Income)."""
    __tablename__ = "invoices"

    number = Column(String(40), nullable=False)
    customer_name = Column(String(200), nullable=False)
    student_id = Column(String(36), ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    invoice_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    status = Column(String(20), default="draft", nullable=False)  # draft|posted|paid|void
    total = Column(Numeric(14, 2), default=0, nullable=False)
    memo = Column(Text, nullable=True)
    receivable_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    payment_entry_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    posted_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "number", name="uq_invoices_org_number"),
        Index("ix_invoices_org_status", "org_id", "status"),
    )


class InvoiceLine(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "invoice_lines"

    invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(String(255), nullable=False)
    quantity = Column(Numeric(14, 2), default=1, nullable=False)
    unit_price = Column(Numeric(14, 2), default=0, nullable=False)
    amount = Column(Numeric(14, 2), default=0, nullable=False)
    income_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="RESTRICT"), nullable=False)

    __table_args__ = (
        Index("ix_invoice_lines_invoice_org", "invoice_id", "org_id"),
    )


# ── Payroll ────────────────────────────────────────────────────────────────────

class PayrollRun(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A payroll run. Two-person control: ``created_by`` drafts it; a DIFFERENT
    user with payments:post approves → posts a balanced JournalEntry."""
    __tablename__ = "payroll_runs"

    period_label = Column(String(80), nullable=False)
    run_date = Column(Date, nullable=True)
    status = Column(String(20), default="draft", nullable=False)  # draft|posted|void
    total_gross = Column(Numeric(14, 2), default=0, nullable=False)
    total_deductions = Column(Numeric(14, 2), default=0, nullable=False)
    total_net = Column(Numeric(14, 2), default=0, nullable=False)
    expense_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)
    net_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)
    deductions_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_payroll_runs_org_status", "org_id", "status"),
    )


class SchoolPayslip(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A line on a payroll run. Named SchoolPayslip / table school_payslips to
    avoid colliding with the retained business-module `Payslip`."""
    __tablename__ = "school_payslips"

    run_id = Column(String(36), ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    staff_name = Column(String(200), nullable=True)
    gross = Column(Numeric(14, 2), default=0, nullable=False)
    deductions = Column(Numeric(14, 2), default=0, nullable=False)
    net = Column(Numeric(14, 2), default=0, nullable=False)
    notes = Column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_school_payslips_run_org", "run_id", "org_id"),
    )


# ── Petty Cash & Budget (Batch 5, second half) ──────────────────────────────────

class Budget(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A per-account spending budget for a period. Enforcement is a SOFT warning
    (the books record reality); overspend is controlled by approval, not a lock.

    ``start_date``/``end_date`` bound the period so 'spent' can be measured within
    the window (true per-period variance). Both nullable — a budget with no dates
    falls back to all-time account spend (backward-compatible with pre-dates rows)."""
    __tablename__ = "budgets"

    account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    period_label = Column(String(80), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    amount = Column(Numeric(14, 2), default=0, nullable=False)
    notes = Column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_budgets_account_org", "account_id", "org_id"),
    )


class PettyCashTxn(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A petty-cash disbursement. Posts Dr Expense / Cr Petty-Cash via the ledger
    engine (so it inherits the balance + period-lock guards)."""
    __tablename__ = "petty_cash_transactions"

    txn_date = Column(Date, nullable=True)
    description = Column(String(255), nullable=True)
    amount = Column(Numeric(14, 2), default=0, nullable=False)
    expense_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="RESTRICT"), nullable=False)
    cash_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="RESTRICT"), nullable=False)
    category = Column(String(80), nullable=True)
    status = Column(String(20), default="posted", nullable=False)  # posted | void
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    posted_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_petty_cash_org_date", "org_id", "txn_date"),
    )


# ── Cash Transactions ───────────────────────────────────────────────────────────

class CashTransaction(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A cash receipt or payment. Posts via the ledger engine:
      receipt → Dr Cash / Cr counter ;  payment → Dr counter / Cr Cash."""
    __tablename__ = "cash_transactions"

    txn_date = Column(Date, nullable=True)
    type = Column(String(20), default="receipt", nullable=False)  # receipt | payment
    amount = Column(Numeric(14, 2), default=0, nullable=False)
    cash_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="RESTRICT"), nullable=False)
    counter_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="RESTRICT"), nullable=False)
    counterparty = Column(String(200), nullable=True)
    description = Column(String(255), nullable=True)
    status = Column(String(20), default="posted", nullable=False)  # posted | void
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    posted_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_cash_txns_org_date", "org_id", "txn_date"),
        Index("ix_cash_txns_org_type", "org_id", "type"),
    )


# ── Store & Inventory ───────────────────────────────────────────────────────────

class StoreItem(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A school-shop / store stock item. Distinct from the business InventoryItem."""
    __tablename__ = "store_items"

    name = Column(String(200), nullable=False)
    sku = Column(String(80), nullable=True)
    unit_price = Column(Numeric(14, 2), default=0, nullable=False)   # sale price
    cost_price = Column(Numeric(14, 2), default=0, nullable=False)
    quantity = Column(Numeric(14, 2), default=0, nullable=False)
    reorder_level = Column(Numeric(14, 2), default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("ix_store_items_org", "org_id"),
    )


class StockMovement(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A stock change. A purchase (``in``) posts Dr Inventory / Cr funding via the
    ledger (purchase-side accounting only — no COGS-on-sale this batch). ``out`` /
    ``adjust`` only change quantity."""
    __tablename__ = "stock_movements"

    item_id = Column(String(36), ForeignKey("store_items.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(20), default="in", nullable=False)  # in | out | adjust
    quantity = Column(Numeric(14, 2), default=0, nullable=False)
    unit_cost = Column(Numeric(14, 2), default=0, nullable=False)
    note = Column(String(255), nullable=True)
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    posted_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_stock_movements_item_org", "item_id", "org_id"),
    )


class SalaryAdvance(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A staff salary advance (a short-term loan to an employee, recovered later).

    Lifecycle: ``pending`` → approve DISBURSES (Dr Staff Advances / Cr Cash through
    the SAME ledger engine payroll uses, so it inherits balance/period-lock/audit),
    → ``repaid`` once repayments clear the balance. ``amount_repaid`` accumulates;
    outstanding is DERIVED (amount − amount_repaid), never stored. Approval enforces
    approver ≠ requester (segregation of duties), exactly like payroll approval."""
    __tablename__ = "salary_advances"

    staff_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_name = Column(String(200), nullable=True)
    amount = Column(Numeric(14, 2), nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(String(20), default="pending", nullable=False)  # pending|approved|rejected|repaid
    amount_repaid = Column(Numeric(14, 2), default=0, nullable=False)
    requested_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    # Ledger linkage — the disbursement posting (immutable, via the ledger service).
    disburse_entry_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    advance_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_salary_advances_amount_pos"),
        Index("ix_salary_advances_org_status", "org_id", "status"),
    )


class SalaryAdvanceRepayment(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """One repayment against a SalaryAdvance — posts Dr Cash / Cr Staff Advances
    through the ledger. Immutable record of how the advance was recovered."""
    __tablename__ = "salary_advance_repayments"

    advance_id = Column(String(36), ForeignKey("salary_advances.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=False)
    method = Column(String(20), default="payroll", nullable=False)  # payroll | cash
    payroll_run_id = Column(String(36), ForeignKey("payroll_runs.id", ondelete="SET NULL"), nullable=True)
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    recorded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_salary_advance_repay_amount_pos"),
        Index("ix_salary_advance_repay_advance", "advance_id", "org_id"),
    )


class PayAdjustmentPack(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A batch ('pack') of one-off pay adjustments applied across staff — either
    BONUSES (extra pay, an expense) or REDUCTIONS (amounts withheld/recovered).

    Lifecycle: ``draft`` → approve POSTS to the ledger → ``void`` reverses it. Uses
    the SAME ledger engine + two-person control (approver ≠ creator) as payroll, so
    it inherits balance/period-lock/immutability/audit. It does NOT modify the
    payroll approval flow — adjustments are recorded independently and reconciled
    into pay manually (auto-payroll integration is a deliberate follow-up).

    Ledger direction flips on ``kind``:
      bonus     → Dr expense_account (P&L)      / Cr settle_account (cash/payable)
      reduction → Dr settle_account (cash/payable) / Cr expense_account (income/offset)
    """
    __tablename__ = "pay_adjustment_packs"

    label = Column(String(120), nullable=False)
    kind = Column(String(20), default="bonus", nullable=False)   # bonus | reduction
    status = Column(String(20), default="draft", nullable=False)  # draft | approved | void
    total_amount = Column(Numeric(14, 2), default=0, nullable=False)
    reason = Column(Text, nullable=True)
    # P&L side (bonus expense, or reduction income/offset) + settlement side (cash/payable).
    expense_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)
    settle_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("kind in ('bonus','reduction')", name="ck_pay_adjustment_packs_kind"),
        Index("ix_pay_adjustment_packs_org_status", "org_id", "status"),
    )


class PayAdjustmentItem(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """One staff line within a PayAdjustmentPack (mirrors a payroll payslip line)."""
    __tablename__ = "pay_adjustment_items"

    pack_id = Column(String(36), ForeignKey("pay_adjustment_packs.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    staff_name = Column(String(200), nullable=True)
    amount = Column(Numeric(14, 2), nullable=False)
    note = Column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_pay_adjustment_items_amount_pos"),
        Index("ix_pay_adjustment_items_pack", "pack_id", "org_id"),
    )


class Requisition(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A purchase/expense requisition — a staff request to spend, routed through
    approval. Lifecycle: ``draft`` (raised via the Request Form) → approve POSTS the
    spend to the ledger (Dr Expense / Cr Cash|Payable) → ``void`` reverses it;
    ``rejected`` closes it without spending. Uses the SAME ledger engine + two-person
    control (approver ≠ requester) as payroll/petty-cash, so it inherits
    balance/period-lock/immutability/audit. Approval books the spend immediately —
    there is no separate goods-receipt/PO step in this version."""
    __tablename__ = "requisitions"

    title = Column(String(200), nullable=False)
    department = Column(String(120), nullable=True)
    category = Column(String(80), nullable=True)      # supplies | maintenance | travel | …
    status = Column(String(20), default="draft", nullable=False)  # draft|approved|rejected|void
    total_amount = Column(Numeric(14, 2), default=0, nullable=False)
    justification = Column(Text, nullable=True)
    # P&L side (expense) + settlement side (cash/payable), chosen at raise time.
    expense_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)
    settle_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    requested_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_requisitions_org_status", "org_id", "status"),
    )


class RequisitionItem(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """One line on a Requisition (a good/service being requested)."""
    __tablename__ = "requisition_items"

    requisition_id = Column(String(36), ForeignKey("requisitions.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(String(255), nullable=False)
    quantity = Column(Numeric(14, 2), default=1, nullable=False)
    unit_cost = Column(Numeric(14, 2), default=0, nullable=False)
    amount = Column(Numeric(14, 2), default=0, nullable=False)   # quantity × unit_cost (server-computed)
    note = Column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_requisition_items_req", "requisition_id", "org_id"),
    )


class FeeDiscount(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A fee discount / scholarship / waiver granted to a student.

    Lifecycle: ``draft`` (proposed) → approve APPLIES it → ``void`` reverses it;
    ``rejected`` closes it unused. Approval does BOTH (per the design choice):
      1. reduces the student's fee record — ``discount_amount`` accumulates and
         ``outstanding_balance``/status are recomputed, so parents see it in Fee
         Management; and
      2. posts a ledger contra Dr Fee Discounts (expense) / Cr Accounts Receivable
         through the shared engine (so it shows in Finance Reports/Statements).
    Two-person control: approver ≠ proposer (same rule as the other postings)."""
    __tablename__ = "fee_discounts"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    student_name = Column(String(200), nullable=True)
    fee_record_id = Column(String(36), ForeignKey("student_fee_records.id", ondelete="SET NULL"), nullable=True)
    discount_type = Column(String(20), default="fixed", nullable=False)  # fixed | percent
    value = Column(Numeric(14, 2), nullable=False)   # the input (₦ for fixed, % for percent)
    amount = Column(Numeric(14, 2), nullable=False)  # computed ₦ discount (server-side)
    reason = Column(String(255), nullable=True)      # scholarship | sibling | staff-child | waiver | …
    status = Column(String(20), default="draft", nullable=False)  # draft|approved|rejected|void
    proposed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    discount_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)
    receivable_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("value > 0", name="ck_fee_discounts_value_pos"),
        Index("ix_fee_discounts_org_status", "org_id", "status"),
    )


class BankAccount(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """One of the school's own bank accounts (where fees are received / settlements
    land). Reference data shown on invoices, receipts and statements — NOT a staff
    salary account (those live on HRProfile) and NOT a payment-gateway credential.
    Exactly one account per org is ``is_primary`` (the default 'pay to' account)."""
    __tablename__ = "bank_accounts"

    bank_name = Column(String(120), nullable=False)
    account_name = Column(String(150), nullable=False)
    account_number = Column(String(40), nullable=False)
    bank_code = Column(String(20), nullable=True)        # sort code / bank / NUBAN bank code
    account_type = Column(String(20), nullable=True)      # current | savings | domiciliary
    purpose = Column(String(80), nullable=True)           # e.g. Fees | Salaries | General
    is_primary = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)
    # The cash ledger account this bank maps to — its CURRENT balance is derived
    # from this account (Σ debit − Σ credit). Optional; the primary bank falls back
    # to OrgFinanceSettings.default_cash_account_id.
    ledger_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (Index("ix_bank_accounts_org", "org_id"),)


class OrgFinanceSettings(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Per-org default posting accounts the finance forms pre-fill from — one row
    per org. Purely a convenience default; every feature still lets you override.
    (Chart-of-Accounts numbering lives on LedgerAccount; this is only the mapping
    of which existing account is the default for cash / fees-income / receivable /
    expense.)"""
    __tablename__ = "org_finance_settings"

    default_cash_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)
    default_income_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)
    default_receivable_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)
    default_expense_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (UniqueConstraint("org_id", name="uq_org_finance_settings_org"),)


class StoreSale(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """An over-the-counter store sale (front-desk POS). Recording a sale reduces
    stock (a StockMovement 'out' per line) AND posts revenue to the ledger via the
    shared engine (Dr Cash / Cr Store Sales income). ``void`` reverses both."""
    __tablename__ = "store_sales"

    reference = Column(String(40), nullable=True)          # receipt no
    customer_name = Column(String(200), nullable=True)
    student_id = Column(String(36), ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    subtotal = Column(Numeric(14, 2), default=0, nullable=False)
    discount = Column(Numeric(14, 2), default=0, nullable=False)
    total = Column(Numeric(14, 2), default=0, nullable=False)   # subtotal − discount
    payment_method = Column(String(20), default="cash", nullable=False)  # cash | transfer | pos
    cash_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)
    income_account_id = Column(String(36), ForeignKey("ledger_accounts.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), default="completed", nullable=False)  # completed | void
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    cashier_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (Index("ix_store_sales_org_status", "org_id", "status"),)


class PickupPoint(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A collection point where students pick up items bought from the school store."""
    __tablename__ = "pickup_points"

    name = Column(String(150), nullable=False)
    location = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)

    __table_args__ = (Index("ix_pickup_points_org", "org_id"),)


class Pickup(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A collection ticket — what a student is to collect, from which point, and
    whether it's been handed over. ``pending`` → ``collected`` (or ``cancelled``)."""
    __tablename__ = "pickups"

    pickup_point_id = Column(String(36), ForeignKey("pickup_points.id", ondelete="SET NULL"), nullable=True, index=True)
    student_id = Column(String(36), ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    customer_name = Column(String(200), nullable=True)
    description = Column(String(255), nullable=False)     # what to collect
    reference = Column(String(60), nullable=True)         # sale / receipt ref
    status = Column(String(20), default="pending", nullable=False)  # pending|collected|cancelled
    collected_at = Column(DateTime(timezone=True), nullable=True)
    collected_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (Index("ix_pickups_org_status", "org_id", "status"),)


class Warehouse(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A storage location (warehouse / store room). Its own module — tracks WHERE
    bulk stock sits, separate from the sellable StoreItem.quantity the POS/store use.
    Stock is received into a warehouse, transferred between warehouses, and issued
    out (consumption/damage). No ledger impact — physical stock movements only."""
    __tablename__ = "warehouses"

    name = Column(String(150), nullable=False)
    location = Column(String(200), nullable=True)     # building / room / address
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)

    __table_args__ = (Index("ix_warehouses_org", "org_id"),)


class WarehouseStock(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """On-hand quantity of a StoreItem in one Warehouse. One row per (warehouse, item)."""
    __tablename__ = "warehouse_stock"

    warehouse_id = Column(String(36), ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(String(36), ForeignKey("store_items.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = Column(Numeric(14, 2), default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("warehouse_id", "item_id", name="uq_warehouse_stock_wh_item"),
        Index("ix_warehouse_stock_org", "org_id"),
    )


class StoreSaleLine(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """One line on a StoreSale."""
    __tablename__ = "store_sale_lines"

    sale_id = Column(String(36), ForeignKey("store_sales.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(String(36), ForeignKey("store_items.id", ondelete="SET NULL"), nullable=True)
    item_name = Column(String(200), nullable=True)
    quantity = Column(Numeric(14, 2), default=0, nullable=False)
    unit_price = Column(Numeric(14, 2), default=0, nullable=False)
    amount = Column(Numeric(14, 2), default=0, nullable=False)   # quantity × unit_price

    __table_args__ = (Index("ix_store_sale_lines_sale", "sale_id", "org_id"),)
