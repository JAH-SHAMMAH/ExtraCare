"""PocketMoney Manager: item catalogue

Revision ID: 086_pocket_money_items
Revises: 085_parent_wallet
Create Date: 2026-07-22 16:30:00.000000

Additive + reversible. Adds pocket_money_items — the purchasable canteen/tuck-shop
catalogue used to compose a New Transaction (which records a SPEND against the
student's existing StudentWallet). No new money ledger.
"""
from alembic import op
import sqlalchemy as sa


revision = "086_pocket_money_items"
down_revision = "085_parent_wallet"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pocket_money_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pocket_money_items_org", "pocket_money_items", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_pocket_money_items_org", table_name="pocket_money_items")
    op.drop_table("pocket_money_items")
