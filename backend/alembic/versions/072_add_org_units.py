"""Organization Structure: org_units

Revision ID: 072_org_units
Revises: 071_staff_attendance
Create Date: 2026-07-20 13:00:00.000000

Additive + reversible. A self-referential org hierarchy (parent_id → org_units,
optional head → users). Matches TenantMixin — org_id is an indexed String, no FK.
"""
from alembic import op
import sqlalchemy as sa


revision = "072_org_units"
down_revision = "071_staff_attendance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "org_units",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("unit_type", sa.String(length=40), nullable=True),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("head_user_id", sa.String(length=36), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["org_units.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["head_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_org_units_parent_id", "org_units", ["parent_id"])
    op.create_index("ix_org_units_org_id", "org_units", ["org_id"])
    op.create_index("ix_org_units_org_parent", "org_units", ["org_id", "parent_id"])


def downgrade() -> None:
    op.drop_index("ix_org_units_org_parent", table_name="org_units")
    op.drop_index("ix_org_units_org_id", table_name="org_units")
    op.drop_index("ix_org_units_parent_id", table_name="org_units")
    op.drop_table("org_units")
