"""CBT: cbt_attempts.superseded_at + superseded_by (reset-for-retake soft delete)

Revision ID: 046_cbt_attempt_superseded
Revises: 045_cbt_pass_percentage
Create Date: 2026-07-09 16:00:00.000000

Additive + reversible. Reset now supersedes an attempt (soft delete) instead of
hard-deleting it + its answers. NULL superseded_at = active; existing rows are
active by default.
"""
from alembic import op
import sqlalchemy as sa


revision = "046_cbt_attempt_superseded"
down_revision = "045_cbt_pass_percentage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cbt_attempts", schema=None) as b:
        b.add_column(sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True))
        b.add_column(sa.Column("superseded_by", sa.String(length=36), nullable=True))
        b.create_foreign_key(
            op.f("fk_cbt_attempts_superseded_by_users"), "users", ["superseded_by"], ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("cbt_attempts", schema=None) as b:
        b.drop_constraint(op.f("fk_cbt_attempts_superseded_by_users"), type_="foreignkey")
        b.drop_column("superseded_by")
        b.drop_column("superseded_at")
