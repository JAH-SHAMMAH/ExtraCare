"""Add requisitions + requisition_items (Finance: Requisitions / Request Form)

Revision ID: 018_add_requisitions
Revises: 017_add_pay_adjustment
Create Date: 2026-07-03 22:45:00.000000

Additive + reversible.
"""

from alembic import op
import sqlalchemy as sa


revision = "018_add_requisitions"
down_revision = "017_add_pay_adjustment"
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
        "requisitions", *_base(),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("department", sa.String(120), nullable=True),
        sa.Column("category", sa.String(80), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("expense_account_id", sa.String(36), nullable=True),
        sa.Column("settle_account_id", sa.String(36), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("requested_by", sa.String(36), nullable=True),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_requisitions"),
        sa.ForeignKeyConstraint(["expense_account_id"], ["ledger_accounts.id"], ondelete="SET NULL", name="fk_requisitions_expense_account_id_ledger_accounts"),
        sa.ForeignKeyConstraint(["settle_account_id"], ["ledger_accounts.id"], ondelete="SET NULL", name="fk_requisitions_settle_account_id_ledger_accounts"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="SET NULL", name="fk_requisitions_journal_entry_id_journal_entries"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL", name="fk_requisitions_requested_by_users"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL", name="fk_requisitions_approved_by_users"),
    )
    op.create_index("ix_requisitions_id", "requisitions", ["id"])
    op.create_index("ix_requisitions_org_id", "requisitions", ["org_id"])
    op.create_index("ix_requisitions_org_status", "requisitions", ["org_id", "status"])

    op.create_table(
        "requisition_items", *_base(),
        sa.Column("requisition_id", sa.String(36), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False, server_default="1"),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("note", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_requisition_items"),
        sa.ForeignKeyConstraint(["requisition_id"], ["requisitions.id"], ondelete="CASCADE", name="fk_requisition_items_requisition_id_requisitions"),
    )
    op.create_index("ix_requisition_items_id", "requisition_items", ["id"])
    op.create_index("ix_requisition_items_org_id", "requisition_items", ["org_id"])
    op.create_index("ix_requisition_items_requisition_id", "requisition_items", ["requisition_id"])
    op.create_index("ix_requisition_items_req", "requisition_items", ["requisition_id", "org_id"])


def downgrade() -> None:
    op.drop_table("requisition_items")
    op.drop_table("requisitions")
