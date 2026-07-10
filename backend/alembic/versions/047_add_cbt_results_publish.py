"""CBT results distribution Phase 1: hold_results + publish snapshot on cbt_exams

Revision ID: 047_cbt_results_publish
Revises: 046_cbt_attempt_superseded
Create Date: 2026-07-10 09:00:00.000000

Additive + reversible. Per-exam results gating (hold_results, default False =
current immediate behavior) + publish state (results_published_at / _by) + a
frozen pass-mark snapshot (published_pass_percentage) so the released view is
stable when the live pass mark changes.
"""
from alembic import op
import sqlalchemy as sa


revision = "047_cbt_results_publish"
down_revision = "046_cbt_attempt_superseded"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cbt_exams", schema=None) as b:
        b.add_column(sa.Column("hold_results", sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("results_published_at", sa.DateTime(timezone=True), nullable=True))
        b.add_column(sa.Column("results_published_by", sa.String(length=36), nullable=True))
        b.add_column(sa.Column("published_pass_percentage", sa.Integer(), nullable=True))
        b.create_foreign_key(
            op.f("fk_cbt_exams_results_published_by_users"), "users", ["results_published_by"], ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("cbt_exams", schema=None) as b:
        b.drop_constraint(op.f("fk_cbt_exams_results_published_by_users"), type_="foreignkey")
        b.drop_column("published_pass_percentage")
        b.drop_column("results_published_by")
        b.drop_column("results_published_at")
        b.drop_column("hold_results")
