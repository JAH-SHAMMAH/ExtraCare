"""CBT: cbt_exams.max_attempts + cbt_attempts.submitted_late

Revision ID: 044_cbt_attempt_limits
Revises: 043_attendance_config
Create Date: 2026-07-09 12:00:00.000000

Additive + reversible. Per-exam attempt cap (default 1; 0 = unlimited) and a
late-submission flag on attempts. Existing rows backfill via server_default.
"""
from alembic import op
import sqlalchemy as sa


revision = "044_cbt_attempt_limits"
down_revision = "043_attendance_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cbt_exams", schema=None) as b:
        b.add_column(sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="1"))
    with op.batch_alter_table("cbt_attempts", schema=None) as b:
        b.add_column(sa.Column("submitted_late", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("cbt_attempts", schema=None) as b:
        b.drop_column("submitted_late")
    with op.batch_alter_table("cbt_exams", schema=None) as b:
        b.drop_column("max_attempts")
