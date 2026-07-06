"""Add bank_accounts (Finance: Account Numbers)

Revision ID: 022_add_bank_accounts
Revises: 021_add_staff_appointments
Create Date: 2026-07-04 12:00:00.000000

Additive + reversible.
"""

from alembic import op
import sqlalchemy as sa


revision = "022_add_bank_accounts"
down_revision = "021_add_staff_appointments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bank_name", sa.String(120), nullable=False),
        sa.Column("account_name", sa.String(150), nullable=False),
        sa.Column("account_number", sa.String(40), nullable=False),
        sa.Column("bank_code", sa.String(20), nullable=True),
        sa.Column("account_type", sa.String(20), nullable=True),
        sa.Column("purpose", sa.String(80), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_bank_accounts"),
    )
    op.create_index("ix_bank_accounts_id", "bank_accounts", ["id"])
    op.create_index("ix_bank_accounts_org_id", "bank_accounts", ["org_id"])
    op.create_index("ix_bank_accounts_org", "bank_accounts", ["org_id"])


def downgrade() -> None:
    op.drop_table("bank_accounts")
