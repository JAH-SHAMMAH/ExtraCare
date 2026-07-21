"""Leave configuration: leave_policies

Revision ID: 073_leave_policies
Revises: 072_org_units
Create Date: 2026-07-20 14:00:00.000000

Additive + reversible. Per-org policy per leave type (default days / approval /
active). Matches TenantMixin — org_id is an indexed String, no FK.
"""
from alembic import op
import sqlalchemy as sa


revision = "073_leave_policies"
down_revision = "072_org_units"
branch_labels = None
depends_on = None

_LEAVE_TYPE = sa.Enum("ANNUAL", "CASUAL", "SICK", "MATERNITY", "PATERNITY",
                      "BEREAVEMENT", "UNPAID", "OTHER", name="leavetype")


def upgrade() -> None:
    op.create_table(
        "leave_policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        # Reuse the existing leavetype enum (already created by leave_applications);
        # create_type=False avoids re-declaring it on Postgres.
        sa.Column("leave_type", sa.Enum("ANNUAL", "CASUAL", "SICK", "MATERNITY", "PATERNITY",
                                        "BEREAVEMENT", "UNPAID", "OTHER", name="leavetype", create_type=False), nullable=False),
        sa.Column("default_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "leave_type", name="uq_leave_policy_org_type"),
    )
    op.create_index("ix_leave_policies_org_id", "leave_policies", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_leave_policies_org_id", table_name="leave_policies")
    op.drop_table("leave_policies")
