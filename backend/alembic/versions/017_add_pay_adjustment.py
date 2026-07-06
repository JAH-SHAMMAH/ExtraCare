"""Add pay_adjustment_packs + pay_adjustment_items (Finance: Bonus/Reduction Pack)

Revision ID: 017_add_pay_adjustment
Revises: 016_add_salary_advance
Create Date: 2026-06-23 20:30:00.000000

Additive + reversible.
"""

from alembic import op
import sqlalchemy as sa


revision = "017_add_pay_adjustment"
down_revision = "016_add_salary_advance"
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
        "pay_adjustment_packs", *_base(),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False, server_default="bonus"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("expense_account_id", sa.String(36), nullable=True),
        sa.Column("settle_account_id", sa.String(36), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_pay_adjustment_packs"),
        sa.ForeignKeyConstraint(["expense_account_id"], ["ledger_accounts.id"], ondelete="SET NULL", name="fk_pay_adj_expense_account_id_ledger_accounts"),
        sa.ForeignKeyConstraint(["settle_account_id"], ["ledger_accounts.id"], ondelete="SET NULL", name="fk_pay_adj_settle_account_id_ledger_accounts"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="SET NULL", name="fk_pay_adj_journal_entry_id_journal_entries"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL", name="fk_pay_adj_created_by_users"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL", name="fk_pay_adj_approved_by_users"),
        sa.CheckConstraint("kind in ('bonus','reduction')", name="ck_pay_adjustment_packs_kind"),
    )
    op.create_index("ix_pay_adjustment_packs_id", "pay_adjustment_packs", ["id"])
    op.create_index("ix_pay_adjustment_packs_org_id", "pay_adjustment_packs", ["org_id"])
    op.create_index("ix_pay_adjustment_packs_org_status", "pay_adjustment_packs", ["org_id", "status"])

    op.create_table(
        "pay_adjustment_items", *_base(),
        sa.Column("pack_id", sa.String(36), nullable=False),
        sa.Column("staff_user_id", sa.String(36), nullable=True),
        sa.Column("staff_name", sa.String(200), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_pay_adjustment_items"),
        sa.ForeignKeyConstraint(["pack_id"], ["pay_adjustment_packs.id"], ondelete="CASCADE", name="fk_pay_adj_item_pack_id_packs"),
        sa.ForeignKeyConstraint(["staff_user_id"], ["users.id"], ondelete="SET NULL", name="fk_pay_adj_item_staff_user_id_users"),
        sa.CheckConstraint("amount > 0", name="ck_pay_adjustment_items_amount_pos"),
    )
    op.create_index("ix_pay_adjustment_items_id", "pay_adjustment_items", ["id"])
    op.create_index("ix_pay_adjustment_items_org_id", "pay_adjustment_items", ["org_id"])
    op.create_index("ix_pay_adjustment_items_pack_id", "pay_adjustment_items", ["pack_id"])
    op.create_index("ix_pay_adjustment_items_pack", "pay_adjustment_items", ["pack_id", "org_id"])


def downgrade() -> None:
    op.drop_table("pay_adjustment_items")
    op.drop_table("pay_adjustment_packs")
