"""Secondary Report parity S-1a: Comment types + Result Default Comments

Revision ID: 109_report_comments
Revises: 108_report_terms_periods
Create Date: 2026-07-29 17:00:00.000000

Report Setup config: named comment slots (short/long) + score-band auto-comment
bank keyed by teacher type + grading scale + year group. Additive.
"""
from alembic import op
import sqlalchemy as sa


revision = "109_report_comments"
down_revision = "108_report_terms_periods"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_comment_types",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("comment_type", sa.String(length=20), nullable=False, server_default="short"),
        sa.Column("max_length", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "name", name="uq_report_comment_types_org_name"),
    )
    op.create_index("ix_report_comment_types_org", "report_comment_types", ["org_id"])

    op.create_table(
        "result_default_comments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("teacher_type", sa.String(length=20), nullable=False, server_default="class"),
        sa.Column("grading_scale_id", sa.String(length=36), nullable=True),
        sa.Column("year_group", sa.String(length=60), nullable=True),
        sa.Column("min_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("max_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["grading_scale_id"], ["grading_scales.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_result_default_comments_grading_scale_id", "result_default_comments", ["grading_scale_id"])
    op.create_index("ix_result_default_comments_org", "result_default_comments", ["org_id", "teacher_type"])


def downgrade() -> None:
    op.drop_table("result_default_comments")
    op.drop_table("report_comment_types")
