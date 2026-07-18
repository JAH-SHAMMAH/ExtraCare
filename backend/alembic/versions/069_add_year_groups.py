"""Classes/YearGroups: managed year-group taxonomy

Revision ID: 069_year_groups
Revises: 068_attendance_setup
Create Date: 2026-07-17 09:00:00.000000

Additive + reversible. One table backing Manage YearGroups — the ordered level
taxonomy above classes (YEAR 7 … plus Alumni / Entrance groups via category).
SchoolClass is untouched (its free-text `level` still works; year groups feed the
form's picklist).
"""
from alembic import op
import sqlalchemy as sa


revision = "069_year_groups"
down_revision = "068_attendance_setup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "year_groups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("short_code", sa.String(length=20), nullable=True),
        sa.Column("category", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_mock", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "name", name="uq_year_group_org_name"),
    )
    op.create_index("ix_year_groups_org", "year_groups", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_year_groups_org", table_name="year_groups")
    op.drop_table("year_groups")
