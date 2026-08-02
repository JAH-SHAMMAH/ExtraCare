"""Secondary Report parity S-4d: report-card comment store (Head / PC Teacher)

Revision ID: 115_report_comments_store
Revises: 114_report_scores
Create Date: 2026-07-30 09:00:00.000000

Per-pupil School Head / PC Teacher comments for a (term, sub-term). Additive.
"""
from alembic import op
import sqlalchemy as sa


revision = "115_report_comments_store"
down_revision = "114_report_scores"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_report_comments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("term_id", sa.String(length=36), nullable=False),
        sa.Column("sub_term_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["term_id"], ["academic_terms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sub_term_id"], ["academic_sub_terms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "student_id", "term_id", "sub_term_id", "kind", name="uq_student_report_comment"),
    )
    op.create_index("ix_student_report_comments_student_id", "student_report_comments", ["student_id"])
    op.create_index("ix_student_report_comments_term", "student_report_comments", ["org_id", "term_id", "sub_term_id"])


def downgrade() -> None:
    op.drop_table("student_report_comments")
