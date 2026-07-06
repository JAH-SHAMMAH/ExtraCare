"""Add store_sales + store_sale_lines (Store: Front Desk POS)

Revision ID: 024_add_store_sales
Revises: 023_add_org_finance_settings
Create Date: 2026-07-04 14:00:00.000000

Additive + reversible.
"""

from alembic import op
import sqlalchemy as sa


revision = "024_add_store_sales"
down_revision = "023_add_org_finance_settings"
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
        "store_sales", *_base(),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reference", sa.String(40), nullable=True),
        sa.Column("customer_name", sa.String(200), nullable=True),
        sa.Column("student_id", sa.String(36), nullable=True),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("payment_method", sa.String(20), nullable=False, server_default="cash"),
        sa.Column("cash_account_id", sa.String(36), nullable=True),
        sa.Column("income_account_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("cashier_id", sa.String(36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_store_sales"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="SET NULL", name="fk_store_sales_student_id_students"),
        sa.ForeignKeyConstraint(["cash_account_id"], ["ledger_accounts.id"], ondelete="SET NULL", name="fk_store_sales_cash_ledger_accounts"),
        sa.ForeignKeyConstraint(["income_account_id"], ["ledger_accounts.id"], ondelete="SET NULL", name="fk_store_sales_income_ledger_accounts"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="SET NULL", name="fk_store_sales_journal_entries"),
        sa.ForeignKeyConstraint(["cashier_id"], ["users.id"], ondelete="SET NULL", name="fk_store_sales_cashier_users"),
    )
    op.create_index("ix_store_sales_id", "store_sales", ["id"])
    op.create_index("ix_store_sales_org_id", "store_sales", ["org_id"])
    op.create_index("ix_store_sales_org_status", "store_sales", ["org_id", "status"])

    op.create_table(
        "store_sale_lines", *_base(),
        sa.Column("sale_id", sa.String(36), nullable=False),
        sa.Column("item_id", sa.String(36), nullable=True),
        sa.Column("item_name", sa.String(200), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id", name="pk_store_sale_lines"),
        sa.ForeignKeyConstraint(["sale_id"], ["store_sales.id"], ondelete="CASCADE", name="fk_store_sale_lines_sale_id"),
        sa.ForeignKeyConstraint(["item_id"], ["store_items.id"], ondelete="SET NULL", name="fk_store_sale_lines_item_id"),
    )
    op.create_index("ix_store_sale_lines_id", "store_sale_lines", ["id"])
    op.create_index("ix_store_sale_lines_org_id", "store_sale_lines", ["org_id"])
    op.create_index("ix_store_sale_lines_sale_id", "store_sale_lines", ["sale_id"])
    op.create_index("ix_store_sale_lines_sale", "store_sale_lines", ["sale_id", "org_id"])


def downgrade() -> None:
    op.drop_table("store_sale_lines")
    op.drop_table("store_sales")
