"""Staff Transfer Log: staff_transfers

Revision ID: 076_staff_transfers
Revises: 075_hr_documents
Create Date: 2026-07-21 09:00:00.000000

Additive + reversible. Append-only staff department/unit transfer log. Matches
TenantMixin — org_id is an indexed String, no FK.
"""
from alembic import op
import sqlalchemy as sa


revision = "076_staff_transfers"
down_revision = "075_hr_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_transfers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("staff_user_id", sa.String(length=36), nullable=False),
        sa.Column("from_department", sa.String(length=255), nullable=True),
        sa.Column("to_department", sa.String(length=255), nullable=False),
        sa.Column("to_unit", sa.String(length=150), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["staff_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_staff_transfers_staff_user_id", "staff_transfers", ["staff_user_id"])
    op.create_index("ix_staff_transfers_org_id", "staff_transfers", ["org_id"])
    op.create_index("ix_staff_transfers_org_staff", "staff_transfers", ["org_id", "staff_user_id"])


def downgrade() -> None:
    op.drop_index("ix_staff_transfers_org_staff", table_name="staff_transfers")
    op.drop_index("ix_staff_transfers_org_id", table_name="staff_transfers")
    op.drop_index("ix_staff_transfers_staff_user_id", table_name="staff_transfers")
    op.drop_table("staff_transfers")
