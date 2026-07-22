"""Wallet Manager: parent (family) wallet

Revision ID: 085_parent_wallet
Revises: 084_wallet_settings
Create Date: 2026-07-22 15:30:00.000000

Additive + reversible. Adds the parent funding wallet backing the Educare-style
Wallet Manager: parent_wallets (one per parent User), parent_wallet_entries
(credit/debit subledger, ledger-backed), and parent_wallet_settings (non-gateway
config). DVA / virtual-account funding is deferred to Payment Gateways.
"""
from alembic import op
import sqlalchemy as sa


revision = "085_parent_wallet"
down_revision = "084_wallet_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parent_wallets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "user_id", name="uq_parent_wallets_org_user"),
    )
    op.create_index("ix_parent_wallets_user_org", "parent_wallets", ["user_id", "org_id"])
    op.create_index(op.f("ix_parent_wallets_user_id"), "parent_wallets", ["user_id"])
    op.create_index(op.f("ix_parent_wallets_org_id"), "parent_wallets", ["org_id"])

    op.create_table(
        "parent_wallet_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("wallet_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("signed_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("journal_entry_id", sa.String(length=36), nullable=True),
        sa.Column("memo", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["wallet_id"], ["parent_wallets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parent_wallet_entries_wallet_org", "parent_wallet_entries", ["wallet_id", "org_id"])
    op.create_index("ix_parent_wallet_entries_user_org", "parent_wallet_entries", ["user_id", "org_id"])
    op.create_index(op.f("ix_parent_wallet_entries_wallet_id"), "parent_wallet_entries", ["wallet_id"])
    op.create_index(op.f("ix_parent_wallet_entries_user_id"), "parent_wallet_entries", ["user_id"])

    op.create_table(
        "parent_wallet_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("auto_invoice_pay", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("correspondent_email", sa.String(length=320), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_parent_wallet_settings_org"),
    )
    op.create_index("ix_parent_wallet_settings_org_id", "parent_wallet_settings", ["org_id"])


def downgrade() -> None:
    op.drop_table("parent_wallet_settings")
    op.drop_index("ix_parent_wallet_entries_user_org", table_name="parent_wallet_entries")
    op.drop_index("ix_parent_wallet_entries_wallet_org", table_name="parent_wallet_entries")
    op.drop_table("parent_wallet_entries")
    op.drop_index("ix_parent_wallets_user_org", table_name="parent_wallets")
    op.drop_table("parent_wallets")
