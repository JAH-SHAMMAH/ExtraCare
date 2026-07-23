"""TimeTable module: periods + period schedules (Manage Periods / Schedules)

Revision ID: 091_timetable_periods
Revises: 090_timetable_setup
Create Date: 2026-07-23 06:00:00.000000

Additive + reversible. Adds periods (a period group's day/time rows) and
period_schedules (subject+teacher placed in a period for a class).
"""
from alembic import op
import sqlalchemy as sa


revision = "091_timetable_periods"
down_revision = "090_timetable_setup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "periods",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("period_group_id", sa.String(length=36), nullable=False),
        sa.Column("academic_year", sa.String(length=20), nullable=True),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(length=10), nullable=False),
        sa.Column("end_time", sa.String(length=10), nullable=False),
        sa.Column("period_type", sa.String(length=40), nullable=False, server_default="LESSON"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["period_group_id"], ["period_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_periods_group_org", "periods", ["period_group_id", "org_id"])
    op.create_index("ix_periods_period_group_id", "periods", ["period_group_id"])
    op.create_index("ix_periods_org_id", "periods", ["org_id"])

    op.create_table(
        "period_schedules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("period_id", sa.String(length=36), nullable=False),
        sa.Column("class_id", sa.String(length=36), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("teacher_id", sa.String(length=36), nullable=True),
        sa.Column("academic_year", sa.String(length=20), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["period_id"], ["periods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_id"], ["school_classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "period_id", "class_id", name="uq_period_schedule"),
    )
    op.create_index("ix_period_schedules_class_org", "period_schedules", ["class_id", "org_id"])
    op.create_index("ix_period_schedules_period_id", "period_schedules", ["period_id"])
    op.create_index("ix_period_schedules_class_id", "period_schedules", ["class_id"])
    op.create_index("ix_period_schedules_org_id", "period_schedules", ["org_id"])


def downgrade() -> None:
    op.drop_table("period_schedules")
    op.drop_index("ix_periods_group_org", table_name="periods")
    op.drop_table("periods")
