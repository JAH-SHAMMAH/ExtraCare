"""Add remita_transactions (parent fee payments via Remita)

Revision ID: 014_add_remita
Revises: 013_add_support
Create Date: 2026-06-23 17:30:00.000000

Additive + reversible.
"""

from alembic import op
import sqlalchemy as sa


revision = "014_add_remita"
down_revision = "013_add_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "remita_transactions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("invoice_id", sa.String(36), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=True),
        sa.Column("order_id", sa.String(64), nullable=False),
        sa.Column("rrr", sa.String(64), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("payer_name", sa.String(200), nullable=True),
        sa.Column("payer_email", sa.String(255), nullable=True),
        sa.Column("payer_phone", sa.String(50), nullable=True),
        sa.Column("raw_init", sa.JSON(), nullable=True),
        sa.Column("raw_status", sa.JSON(), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("initiated_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_remita_transactions"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE", name="fk_remita_tx_invoice_id_invoices"),
        sa.ForeignKeyConstraint(["initiated_by"], ["users.id"], ondelete="SET NULL", name="fk_remita_tx_initiated_by_users"),
        sa.UniqueConstraint("org_id", "order_id", name="uq_remita_tx_org_order"),
    )
    op.create_index("ix_remita_transactions_id", "remita_transactions", ["id"])
    op.create_index("ix_remita_transactions_org_id", "remita_transactions", ["org_id"])
    op.create_index("ix_remita_transactions_invoice_id", "remita_transactions", ["invoice_id"])
    op.create_index("ix_remita_transactions_rrr", "remita_transactions", ["rrr"])
    op.create_index("ix_remita_tx_org_status", "remita_transactions", ["org_id", "status"])


def downgrade() -> None:
    op.drop_table("remita_transactions")
