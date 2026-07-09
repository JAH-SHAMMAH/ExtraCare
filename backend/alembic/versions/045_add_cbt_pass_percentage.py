"""CBT: cbt_exams.pass_percentage (per-exam pass mark)

Revision ID: 045_cbt_pass_percentage
Revises: 044_cbt_attempt_limits
Create Date: 2026-07-09 14:00:00.000000

Additive + reversible. Nullable per-exam pass mark; NULL falls back to the org
CBT default at read time (Result Manager). No backfill needed.
"""
from alembic import op
import sqlalchemy as sa


revision = "045_cbt_pass_percentage"
down_revision = "044_cbt_attempt_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cbt_exams", schema=None) as b:
        b.add_column(sa.Column("pass_percentage", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("cbt_exams", schema=None) as b:
        b.drop_column("pass_percentage")
