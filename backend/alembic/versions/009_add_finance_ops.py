"""Add petty cash, budgets, cash transactions, store & inventory (Batch 5, 2nd half)

Revision ID: 009_add_finance_ops
Revises: 008_add_finance_ledger
Create Date: 2026-06-21 05:00:00.000000

Additive + reversible. All money-moving rows here post through the shared ledger
engine (no new posting path), so they inherit the balance + period-lock guards.
"""

from alembic import op
import sqlalchemy as sa


revision = "009_add_finance_ops"
down_revision = "008_add_finance_ledger"
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
        "budgets",
        *_base(),
        sa.Column("account_id", sa.String(36), nullable=False),
        sa.Column("period_label", sa.String(80), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_budgets"),
        sa.ForeignKeyConstraint(["account_id"], ["ledger_accounts.id"], ondelete="CASCADE", name="fk_budgets_account_id_ledger_accounts"),
    )
    op.create_index("ix_budgets_id", "budgets", ["id"])
    op.create_index("ix_budgets_org_id", "budgets", ["org_id"])
    op.create_index("ix_budgets_account_org", "budgets", ["account_id", "org_id"])

    op.create_table(
        "petty_cash_transactions",
        *_base(),
        sa.Column("txn_date", sa.Date(), nullable=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("expense_account_id", sa.String(36), nullable=False),
        sa.Column("cash_account_id", sa.String(36), nullable=False),
        sa.Column("category", sa.String(80), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="posted"),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("posted_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_petty_cash_transactions"),
        sa.ForeignKeyConstraint(["expense_account_id"], ["ledger_accounts.id"], ondelete="RESTRICT", name="fk_petty_cash_transactions_expense_account_id_ledger_accounts"),
        sa.ForeignKeyConstraint(["cash_account_id"], ["ledger_accounts.id"], ondelete="RESTRICT", name="fk_petty_cash_transactions_cash_account_id_ledger_accounts"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="SET NULL", name="fk_petty_cash_transactions_journal_entry_id_journal_entries"),
        sa.ForeignKeyConstraint(["posted_by"], ["users.id"], ondelete="SET NULL", name="fk_petty_cash_transactions_posted_by_users"),
    )
    op.create_index("ix_petty_cash_transactions_id", "petty_cash_transactions", ["id"])
    op.create_index("ix_petty_cash_transactions_org_id", "petty_cash_transactions", ["org_id"])
    op.create_index("ix_petty_cash_org_date", "petty_cash_transactions", ["org_id", "txn_date"])

    op.create_table(
        "cash_transactions",
        *_base(),
        sa.Column("txn_date", sa.Date(), nullable=True),
        sa.Column("type", sa.String(20), nullable=False, server_default="receipt"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("cash_account_id", sa.String(36), nullable=False),
        sa.Column("counter_account_id", sa.String(36), nullable=False),
        sa.Column("counterparty", sa.String(200), nullable=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="posted"),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("posted_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_cash_transactions"),
        sa.ForeignKeyConstraint(["cash_account_id"], ["ledger_accounts.id"], ondelete="RESTRICT", name="fk_cash_transactions_cash_account_id_ledger_accounts"),
        sa.ForeignKeyConstraint(["counter_account_id"], ["ledger_accounts.id"], ondelete="RESTRICT", name="fk_cash_transactions_counter_account_id_ledger_accounts"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="SET NULL", name="fk_cash_transactions_journal_entry_id_journal_entries"),
        sa.ForeignKeyConstraint(["posted_by"], ["users.id"], ondelete="SET NULL", name="fk_cash_transactions_posted_by_users"),
    )
    op.create_index("ix_cash_transactions_id", "cash_transactions", ["id"])
    op.create_index("ix_cash_transactions_org_id", "cash_transactions", ["org_id"])
    op.create_index("ix_cash_txns_org_date", "cash_transactions", ["org_id", "txn_date"])
    op.create_index("ix_cash_txns_org_type", "cash_transactions", ["org_id", "type"])

    op.create_table(
        "store_items",
        *_base(),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("sku", sa.String(80), nullable=True),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("cost_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("reorder_level", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id", name="pk_store_items"),
    )
    op.create_index("ix_store_items_id", "store_items", ["id"])
    op.create_index("ix_store_items_org_id", "store_items", ["org_id"])
    op.create_index("ix_store_items_org", "store_items", ["org_id"])

    op.create_table(
        "stock_movements",
        *_base(),
        sa.Column("item_id", sa.String(36), nullable=False),
        sa.Column("type", sa.String(20), nullable=False, server_default="in"),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("posted_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_stock_movements"),
        sa.ForeignKeyConstraint(["item_id"], ["store_items.id"], ondelete="CASCADE", name="fk_stock_movements_item_id_store_items"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="SET NULL", name="fk_stock_movements_journal_entry_id_journal_entries"),
        sa.ForeignKeyConstraint(["posted_by"], ["users.id"], ondelete="SET NULL", name="fk_stock_movements_posted_by_users"),
    )
    op.create_index("ix_stock_movements_id", "stock_movements", ["id"])
    op.create_index("ix_stock_movements_org_id", "stock_movements", ["org_id"])
    op.create_index("ix_stock_movements_item_id", "stock_movements", ["item_id"])
    op.create_index("ix_stock_movements_item_org", "stock_movements", ["item_id", "org_id"])


def downgrade() -> None:
    for ix in ["ix_stock_movements_item_org", "ix_stock_movements_item_id", "ix_stock_movements_org_id", "ix_stock_movements_id"]:
        op.drop_index(ix, table_name="stock_movements")
    op.drop_table("stock_movements")
    for ix in ["ix_store_items_org", "ix_store_items_org_id", "ix_store_items_id"]:
        op.drop_index(ix, table_name="store_items")
    op.drop_table("store_items")
    for ix in ["ix_cash_txns_org_type", "ix_cash_txns_org_date", "ix_cash_transactions_org_id", "ix_cash_transactions_id"]:
        op.drop_index(ix, table_name="cash_transactions")
    op.drop_table("cash_transactions")
    for ix in ["ix_petty_cash_org_date", "ix_petty_cash_transactions_org_id", "ix_petty_cash_transactions_id"]:
        op.drop_index(ix, table_name="petty_cash_transactions")
    op.drop_table("petty_cash_transactions")
    for ix in ["ix_budgets_account_org", "ix_budgets_org_id", "ix_budgets_id"]:
        op.drop_index(ix, table_name="budgets")
    op.drop_table("budgets")
