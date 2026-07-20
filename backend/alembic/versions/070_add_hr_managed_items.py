"""HR Admin managed lists: hr_managed_items

Revision ID: 070_hr_managed_items
Revises: 069_year_groups
Create Date: 2026-07-20 10:00:00.000000

Additive + reversible. One generic table backing the Educare 'Admin › Job'
cluster — seven managed lists (Job Titles, Job Categories, Pay Grades, Salary
Components, Work Shifts, Employment Status, Working Tools) discriminated by
`list_type`. Matches TenantMixin (org_id is an indexed String, no FK).
"""
from alembic import op
import sqlalchemy as sa


revision = "070_hr_managed_items"
down_revision = "069_year_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hr_managed_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("list_type", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hr_managed_items_list_type", "hr_managed_items", ["list_type"])
    op.create_index("ix_hr_managed_items_org_id", "hr_managed_items", ["org_id"])
    op.create_index("ix_hr_managed_items_org_type", "hr_managed_items", ["org_id", "list_type"])


def downgrade() -> None:
    op.drop_index("ix_hr_managed_items_org_type", table_name="hr_managed_items")
    op.drop_index("ix_hr_managed_items_org_id", table_name="hr_managed_items")
    op.drop_index("ix_hr_managed_items_list_type", table_name="hr_managed_items")
    op.drop_table("hr_managed_items")
