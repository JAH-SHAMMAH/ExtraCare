"""TimeTable module: setup (settings, period groups, subject groups, activities)

Revision ID: 090_timetable_setup
Revises: 089_club_assessment
Create Date: 2026-07-23 05:00:00.000000

Additive + reversible. Backs the TimeTable Setup tabs + Manage Activities:
timetable_settings (singleton), period_groups, subject_groups, school_activities.
"""
from alembic import op
import sqlalchemy as sa


revision = "090_timetable_setup"
down_revision = "089_club_assessment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "period_groups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("year_group", sa.String(length=60), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_period_groups_org_id", "period_groups", ["org_id"])

    op.create_table(
        "subject_groups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("year_group", sa.String(length=60), nullable=True),
        sa.Column("subject_ids", sa.JSON(), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subject_groups_org_id", "subject_groups", ["org_id"])

    op.create_table(
        "school_activities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_school_activities_org_id", "school_activities", ["org_id"])

    op.create_table(
        "timetable_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("enable_even_odd_week", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enable_subject_grouping", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_period_group_id", sa.String(length=36), nullable=True),
        sa.Column("subject_group_type", sa.String(length=60), nullable=True),
        sa.Column("week_start_day", sa.String(length=12), nullable=False, server_default="Monday"),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["default_period_group_id"], ["period_groups.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_timetable_settings_org"),
    )
    op.create_index("ix_timetable_settings_org_id", "timetable_settings", ["org_id"])


def downgrade() -> None:
    op.drop_table("timetable_settings")
    op.drop_index("ix_school_activities_org_id", table_name="school_activities")
    op.drop_table("school_activities")
    op.drop_index("ix_subject_groups_org_id", table_name="subject_groups")
    op.drop_table("subject_groups")
    op.drop_index("ix_period_groups_org_id", table_name="period_groups")
    op.drop_table("period_groups")
