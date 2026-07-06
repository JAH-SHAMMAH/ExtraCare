"""Add fee_discounts (Finance: Manage Discounts)

Revision ID: 020_add_fee_discounts
Revises: 019_add_budget_dates
Create Date: 2026-07-04 09:30:00.000000

Additive + reversible.
"""

from alembic import op
import sqlalchemy as sa


revision = "020_add_fee_discounts"
down_revision = "019_add_budget_dates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fee_discounts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("student_name", sa.String(200), nullable=True),
        sa.Column("fee_record_id", sa.String(36), nullable=True),
        sa.Column("discount_type", sa.String(20), nullable=False, server_default="fixed"),
        sa.Column("value", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("proposed_by", sa.String(36), nullable=True),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("discount_account_id", sa.String(36), nullable=True),
        sa.Column("receivable_account_id", sa.String(36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_fee_discounts"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE", name="fk_fee_discounts_student_id_students"),
        sa.ForeignKeyConstraint(["fee_record_id"], ["student_fee_records.id"], ondelete="SET NULL", name="fk_fee_discounts_fee_record_id"),
        sa.ForeignKeyConstraint(["proposed_by"], ["users.id"], ondelete="SET NULL", name="fk_fee_discounts_proposed_by_users"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL", name="fk_fee_discounts_approved_by_users"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="SET NULL", name="fk_fee_discounts_journal_entry_id"),
        sa.ForeignKeyConstraint(["discount_account_id"], ["ledger_accounts.id"], ondelete="SET NULL", name="fk_fee_discounts_discount_account_id"),
        sa.ForeignKeyConstraint(["receivable_account_id"], ["ledger_accounts.id"], ondelete="SET NULL", name="fk_fee_discounts_receivable_account_id"),
        sa.CheckConstraint("value > 0", name="ck_fee_discounts_value_pos"),
    )
    op.create_index("ix_fee_discounts_id", "fee_discounts", ["id"])
    op.create_index("ix_fee_discounts_org_id", "fee_discounts", ["org_id"])
    op.create_index("ix_fee_discounts_student_id", "fee_discounts", ["student_id"])
    op.create_index("ix_fee_discounts_org_status", "fee_discounts", ["org_id", "status"])


def downgrade() -> None:
    op.drop_table("fee_discounts")
