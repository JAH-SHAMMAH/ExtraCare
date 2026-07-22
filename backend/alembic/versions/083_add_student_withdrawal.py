"""Students: withdrawal fields

Revision ID: 083_student_withdrawal
Revises: 082_lesson_planner_settings
Create Date: 2026-07-22 09:00:00.000000

Additive + reversible. Adds withdrawal_date + withdrawal_reason to students,
backing Manage Withdrawal / Withdrawal List / Manage Inactive Students.
"""
from alembic import op
import sqlalchemy as sa


revision = "083_student_withdrawal"
down_revision = "082_lesson_planner_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("students", sa.Column("withdrawal_date", sa.Date(), nullable=True))
    op.add_column("students", sa.Column("withdrawal_reason", sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column("students", "withdrawal_reason")
    op.drop_column("students", "withdrawal_date")
