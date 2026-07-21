"""Leave configuration: leave_policies

Revision ID: 073_leave_policies
Revises: 072_org_units
Create Date: 2026-07-20 14:00:00.000000

Additive + reversible. Per-org policy per leave type (default days / approval /
active). Matches TenantMixin — org_id is an indexed String, no FK.

Idempotent-enum note: leave_policies reuses the ``leavetype`` PG enum that already
exists (created with ``leave_applications`` during first provisioning). We build
the table on a throwaway MetaData and call ``create_all(checkfirst=True)`` so the
enum's ``CREATE TYPE`` is skipped when the type is already present — the same
mechanism ``metadata.create_all`` uses to avoid enum collisions. (``create_type=
False`` on the column proved unreliable across Alembic/SQLAlchemy versions.) On
SQLite the enum is plain VARCHAR, so this is a no-op difference there.
"""
from alembic import op
import sqlalchemy as sa


revision = "073_leave_policies"
down_revision = "072_org_units"
branch_labels = None
depends_on = None

_LEAVE_VALUES = ("ANNUAL", "CASUAL", "SICK", "MATERNITY", "PATERNITY",
                 "BEREAVEMENT", "UNPAID", "OTHER")


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    sa.Table(
        "leave_policies", metadata,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("leave_type", sa.Enum(*_LEAVE_VALUES, name="leavetype"), nullable=False),
        sa.Column("default_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "leave_type", name="uq_leave_policy_org_type"),
        sa.Index("ix_leave_policies_org_id", "org_id"),
    )
    # checkfirst=True → skip CREATE TYPE leavetype if it already exists (it does),
    # and skip the table/index if they somehow already exist. Fully idempotent.
    metadata.create_all(bind, checkfirst=True)


def downgrade() -> None:
    # Drop only the table (its indexes go with it). NEVER drop the leavetype enum —
    # it is shared with leave_applications.
    op.drop_table("leave_policies")
