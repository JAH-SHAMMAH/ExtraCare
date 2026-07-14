"""Lesson Planner Setup: reminder schedules

Revision ID: 066_lesson_plan_schedules
Revises: 065_lesson_planner_setup
Create Date: 2026-07-14 16:00:00.000000

Additive + reversible. Backs the "Create Lesson Plan Schedules" tab: recurring
reminders that deliver a subject/body to teaching staff (in-app Mailbox + email
when configured) on a daily/weekly cadence, idempotent per day via last_run_on.
"""
from alembic import op
import sqlalchemy as sa


revision = "066_lesson_plan_schedules"
down_revision = "065_lesson_planner_setup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lesson_plan_schedules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("audience", sa.String(length=20), nullable=False, server_default="teachers"),
        sa.Column("frequency", sa.String(length=20), nullable=False, server_default="weekly"),
        sa.Column("days", sa.JSON(), nullable=True),
        sa.Column("run_time", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_run_on", sa.Date(), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lesson_plan_schedules_org_id", "lesson_plan_schedules", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_lesson_plan_schedules_org_id", table_name="lesson_plan_schedules")
    op.drop_table("lesson_plan_schedules")
