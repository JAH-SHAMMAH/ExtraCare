"""Add org_finance_settings (Finance: Accounts Setup — default posting accounts)

Revision ID: 023_add_org_finance_settings
Revises: 022_add_bank_accounts
Create Date: 2026-07-04 13:00:00.000000

Additive + reversible.
"""

from alembic import op
import sqlalchemy as sa


revision = "023_add_org_finance_settings"
down_revision = "022_add_bank_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "org_finance_settings",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("default_cash_account_id", sa.String(36), nullable=True),
        sa.Column("default_income_account_id", sa.String(36), nullable=True),
        sa.Column("default_receivable_account_id", sa.String(36), nullable=True),
        sa.Column("default_expense_account_id", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_org_finance_settings"),
        sa.UniqueConstraint("org_id", name="uq_org_finance_settings_org"),
        sa.ForeignKeyConstraint(["default_cash_account_id"], ["ledger_accounts.id"], ondelete="SET NULL", name="fk_ofs_cash_ledger_accounts"),
        sa.ForeignKeyConstraint(["default_income_account_id"], ["ledger_accounts.id"], ondelete="SET NULL", name="fk_ofs_income_ledger_accounts"),
        sa.ForeignKeyConstraint(["default_receivable_account_id"], ["ledger_accounts.id"], ondelete="SET NULL", name="fk_ofs_receivable_ledger_accounts"),
        sa.ForeignKeyConstraint(["default_expense_account_id"], ["ledger_accounts.id"], ondelete="SET NULL", name="fk_ofs_expense_ledger_accounts"),
    )
    op.create_index("ix_org_finance_settings_id", "org_finance_settings", ["id"])
    op.create_index("ix_org_finance_settings_org_id", "org_finance_settings", ["org_id"])


def downgrade() -> None:
    op.drop_table("org_finance_settings")
