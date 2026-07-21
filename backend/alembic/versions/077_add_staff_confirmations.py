"""Staff Confirmation: staff_confirmations

Revision ID: 077_staff_confirmations
Revises: 076_staff_transfers
Create Date: 2026-07-21 10:00:00.000000

Additive + reversible. The probation → confirmed workflow. Matches TenantMixin —
org_id is an indexed String, no FK.
"""
from alembic import op
import sqlalchemy as sa


revision = "077_staff_confirmations"
down_revision = "076_staff_transfers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_confirmations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("staff_user_id", sa.String(length=36), nullable=False),
        sa.Column("probation_start", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.String(length=36), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["staff_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_staff_confirmations_staff_user_id", "staff_confirmations", ["staff_user_id"])
    op.create_index("ix_staff_confirmations_org_id", "staff_confirmations", ["org_id"])
    op.create_index("ix_staff_confirmations_org_status", "staff_confirmations", ["org_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_staff_confirmations_org_status", table_name="staff_confirmations")
    op.drop_index("ix_staff_confirmations_org_id", table_name="staff_confirmations")
    op.drop_index("ix_staff_confirmations_staff_user_id", table_name="staff_confirmations")
    op.drop_table("staff_confirmations")
