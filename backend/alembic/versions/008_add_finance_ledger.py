"""Add finance ledger, periods, invoices, payroll (Batch 5, first half)

Revision ID: 008_add_finance_ledger
Revises: 007_add_pastoral_health
Create Date: 2026-06-21 04:00:00.000000

Additive + reversible. Creates the double-entry ledger + accounting periods +
invoices + payroll. Petty cash / cash / store tables land in a later migration.

The `accounting_periods` table + `journal_entries.period_id` are reserved here
(not retrofitted later) so the period-lock guard protects the ledger from day one.
"""

from alembic import op
import sqlalchemy as sa


revision = "008_add_finance_ledger"
down_revision = "007_add_pastoral_health"
branch_labels = None
depends_on = None


def _base():
    return (
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "ledger_accounts",
        *_base(),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("parent_id", sa.String(36), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id", name="pk_ledger_accounts"),
        sa.ForeignKeyConstraint(["parent_id"], ["ledger_accounts.id"], ondelete="SET NULL", name="fk_ledger_accounts_parent_id_ledger_accounts"),
        sa.UniqueConstraint("org_id", "code", name="uq_ledger_accounts_org_code"),
    )
    op.create_index("ix_ledger_accounts_id", "ledger_accounts", ["id"])
    op.create_index("ix_ledger_accounts_org_id", "ledger_accounts", ["org_id"])
    op.create_index("ix_ledger_accounts_org_type", "ledger_accounts", ["org_id", "type"])

    op.create_table(
        "accounting_periods",
        *_base(),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_accounting_periods"),
        sa.ForeignKeyConstraint(["locked_by"], ["users.id"], ondelete="SET NULL", name="fk_accounting_periods_locked_by_users"),
    )
    op.create_index("ix_accounting_periods_id", "accounting_periods", ["id"])
    op.create_index("ix_accounting_periods_org_id", "accounting_periods", ["org_id"])
    op.create_index("ix_accounting_periods_org_dates", "accounting_periods", ["org_id", "start_date", "end_date"])

    op.create_table(
        "journal_entries",
        *_base(),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("source_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="posted"),
        sa.Column("period_id", sa.String(36), nullable=True),
        sa.Column("posted_by", sa.String(36), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversal_of_id", sa.String(36), nullable=True),
        sa.Column("reversed_by_id", sa.String(36), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_journal_entries"),
        sa.ForeignKeyConstraint(["period_id"], ["accounting_periods.id"], ondelete="SET NULL", name="fk_journal_entries_period_id_accounting_periods"),
        sa.ForeignKeyConstraint(["posted_by"], ["users.id"], ondelete="SET NULL", name="fk_journal_entries_posted_by_users"),
        sa.ForeignKeyConstraint(["reversal_of_id"], ["journal_entries.id"], ondelete="SET NULL", name="fk_journal_entries_reversal_of_id_journal_entries"),
        sa.ForeignKeyConstraint(["reversed_by_id"], ["journal_entries.id"], ondelete="SET NULL", name="fk_journal_entries_reversed_by_id_journal_entries"),
    )
    op.create_index("ix_journal_entries_id", "journal_entries", ["id"])
    op.create_index("ix_journal_entries_org_id", "journal_entries", ["org_id"])
    op.create_index("ix_journal_entries_entry_date", "journal_entries", ["entry_date"])
    op.create_index("ix_journal_entries_org_date", "journal_entries", ["org_id", "entry_date"])
    op.create_index("ix_journal_entries_source", "journal_entries", ["source", "source_id"])

    op.create_table(
        "journal_lines",
        *_base(),
        sa.Column("entry_id", sa.String(36), nullable=False),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("debit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("description", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_journal_lines"),
        sa.ForeignKeyConstraint(["entry_id"], ["journal_entries.id"], ondelete="CASCADE", name="fk_journal_lines_entry_id_journal_entries"),
        sa.ForeignKeyConstraint(["account_id"], ["ledger_accounts.id"], ondelete="RESTRICT", name="fk_journal_lines_account_id_ledger_accounts"),
        sa.CheckConstraint("debit >= 0 AND credit >= 0", name="ck_journal_lines_nonneg"),
        sa.CheckConstraint("NOT (debit > 0 AND credit > 0)", name="ck_journal_lines_one_sided"),
        sa.CheckConstraint("(debit > 0) OR (credit > 0)", name="ck_journal_lines_has_amount"),
    )
    op.create_index("ix_journal_lines_id", "journal_lines", ["id"])
    op.create_index("ix_journal_lines_org_id", "journal_lines", ["org_id"])
    op.create_index("ix_journal_lines_entry_id", "journal_lines", ["entry_id"])
    op.create_index("ix_journal_lines_account_id", "journal_lines", ["account_id"])
    op.create_index("ix_journal_lines_entry_org", "journal_lines", ["entry_id", "org_id"])
    op.create_index("ix_journal_lines_account_org", "journal_lines", ["account_id", "org_id"])

    op.create_table(
        "invoices",
        *_base(),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("receivable_account_id", sa.String(36), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("payment_entry_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("posted_by", sa.String(36), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_invoices"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="SET NULL", name="fk_invoices_student_id_students"),
        sa.ForeignKeyConstraint(["receivable_account_id"], ["ledger_accounts.id"], ondelete="SET NULL", name="fk_invoices_receivable_account_id_ledger_accounts"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="SET NULL", name="fk_invoices_journal_entry_id_journal_entries"),
        sa.ForeignKeyConstraint(["payment_entry_id"], ["journal_entries.id"], ondelete="SET NULL", name="fk_invoices_payment_entry_id_journal_entries"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL", name="fk_invoices_created_by_users"),
        sa.ForeignKeyConstraint(["posted_by"], ["users.id"], ondelete="SET NULL", name="fk_invoices_posted_by_users"),
        sa.UniqueConstraint("org_id", "number", name="uq_invoices_org_number"),
    )
    op.create_index("ix_invoices_id", "invoices", ["id"])
    op.create_index("ix_invoices_org_id", "invoices", ["org_id"])
    op.create_index("ix_invoices_org_status", "invoices", ["org_id", "status"])

    op.create_table(
        "invoice_lines",
        *_base(),
        sa.Column("invoice_id", sa.String(36), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("income_account_id", sa.String(36), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_invoice_lines"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE", name="fk_invoice_lines_invoice_id_invoices"),
        sa.ForeignKeyConstraint(["income_account_id"], ["ledger_accounts.id"], ondelete="RESTRICT", name="fk_invoice_lines_income_account_id_ledger_accounts"),
    )
    op.create_index("ix_invoice_lines_id", "invoice_lines", ["id"])
    op.create_index("ix_invoice_lines_org_id", "invoice_lines", ["org_id"])
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])
    op.create_index("ix_invoice_lines_invoice_org", "invoice_lines", ["invoice_id", "org_id"])

    op.create_table(
        "payroll_runs",
        *_base(),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_label", sa.String(80), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("total_gross", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_deductions", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_net", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("expense_account_id", sa.String(36), nullable=True),
        sa.Column("net_account_id", sa.String(36), nullable=True),
        sa.Column("deductions_account_id", sa.String(36), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_payroll_runs"),
        sa.ForeignKeyConstraint(["expense_account_id"], ["ledger_accounts.id"], ondelete="SET NULL", name="fk_payroll_runs_expense_account_id_ledger_accounts"),
        sa.ForeignKeyConstraint(["net_account_id"], ["ledger_accounts.id"], ondelete="SET NULL", name="fk_payroll_runs_net_account_id_ledger_accounts"),
        sa.ForeignKeyConstraint(["deductions_account_id"], ["ledger_accounts.id"], ondelete="SET NULL", name="fk_payroll_runs_deductions_account_id_ledger_accounts"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="SET NULL", name="fk_payroll_runs_journal_entry_id_journal_entries"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL", name="fk_payroll_runs_created_by_users"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL", name="fk_payroll_runs_approved_by_users"),
    )
    op.create_index("ix_payroll_runs_id", "payroll_runs", ["id"])
    op.create_index("ix_payroll_runs_org_id", "payroll_runs", ["org_id"])
    op.create_index("ix_payroll_runs_org_status", "payroll_runs", ["org_id", "status"])

    op.create_table(
        "school_payslips",
        *_base(),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("staff_user_id", sa.String(36), nullable=True),
        sa.Column("staff_name", sa.String(200), nullable=True),
        sa.Column("gross", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("deductions", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("net", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_school_payslips"),
        sa.ForeignKeyConstraint(["run_id"], ["payroll_runs.id"], ondelete="CASCADE", name="fk_school_payslips_run_id_payroll_runs"),
        sa.ForeignKeyConstraint(["staff_user_id"], ["users.id"], ondelete="SET NULL", name="fk_school_payslips_staff_user_id_users"),
    )
    op.create_index("ix_school_payslips_id", "school_payslips", ["id"])
    op.create_index("ix_school_payslips_org_id", "school_payslips", ["org_id"])
    op.create_index("ix_school_payslips_run_id", "school_payslips", ["run_id"])
    op.create_index("ix_school_payslips_run_org", "school_payslips", ["run_id", "org_id"])


def downgrade() -> None:
    for ix in ["ix_school_payslips_run_org", "ix_school_payslips_run_id", "ix_school_payslips_org_id", "ix_school_payslips_id"]:
        op.drop_index(ix, table_name="school_payslips")
    op.drop_table("school_payslips")
    for ix in ["ix_payroll_runs_org_status", "ix_payroll_runs_org_id", "ix_payroll_runs_id"]:
        op.drop_index(ix, table_name="payroll_runs")
    op.drop_table("payroll_runs")
    for ix in ["ix_invoice_lines_invoice_org", "ix_invoice_lines_invoice_id", "ix_invoice_lines_org_id", "ix_invoice_lines_id"]:
        op.drop_index(ix, table_name="invoice_lines")
    op.drop_table("invoice_lines")
    for ix in ["ix_invoices_org_status", "ix_invoices_org_id", "ix_invoices_id"]:
        op.drop_index(ix, table_name="invoices")
    op.drop_table("invoices")
    for ix in ["ix_journal_lines_account_org", "ix_journal_lines_entry_org", "ix_journal_lines_account_id",
               "ix_journal_lines_entry_id", "ix_journal_lines_org_id", "ix_journal_lines_id"]:
        op.drop_index(ix, table_name="journal_lines")
    op.drop_table("journal_lines")
    for ix in ["ix_journal_entries_source", "ix_journal_entries_org_date", "ix_journal_entries_entry_date",
               "ix_journal_entries_org_id", "ix_journal_entries_id"]:
        op.drop_index(ix, table_name="journal_entries")
    op.drop_table("journal_entries")
    for ix in ["ix_accounting_periods_org_dates", "ix_accounting_periods_org_id", "ix_accounting_periods_id"]:
        op.drop_index(ix, table_name="accounting_periods")
    op.drop_table("accounting_periods")
    for ix in ["ix_ledger_accounts_org_type", "ix_ledger_accounts_org_id", "ix_ledger_accounts_id"]:
        op.drop_index(ix, table_name="ledger_accounts")
    op.drop_table("ledger_accounts")
