"""Add start_date/end_date to budgets (Finance: period-scoped Budget Management)

Revision ID: 019_add_budget_dates
Revises: 018_add_requisitions
Create Date: 2026-07-03 23:30:00.000000

Additive + reversible. Both columns nullable — existing budgets keep working
(null dates → all-time spend basis).
"""

from alembic import op
import sqlalchemy as sa


revision = "019_add_budget_dates"
down_revision = "018_add_requisitions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("budgets", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column("budgets", sa.Column("end_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("budgets", "end_date")
    op.drop_column("budgets", "start_date")
