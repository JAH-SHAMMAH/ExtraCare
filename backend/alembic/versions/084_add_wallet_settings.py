"""Wallet Manager: per-org settings singleton

Revision ID: 084_wallet_settings
Revises: 083_student_withdrawal
Create Date: 2026-07-22 11:00:00.000000

Additive + reversible. Adds the wallet_settings table (one row per org) backing
the Wallet Manager → Settings tab: default daily limit, low-balance threshold,
and notify/allow-topup toggles.
"""
from alembic import op
import sqlalchemy as sa


revision = "084_wallet_settings"
down_revision = "083_student_withdrawal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wallet_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("default_daily_limit", sa.Numeric(14, 2), nullable=True),
        sa.Column("low_balance_threshold", sa.Numeric(14, 2), nullable=True),
        sa.Column("notify_low_balance", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_topup", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_wallet_settings_org"),
    )
    op.create_index("ix_wallet_settings_org_id", "wallet_settings", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_wallet_settings_org_id", table_name="wallet_settings")
    op.drop_table("wallet_settings")
