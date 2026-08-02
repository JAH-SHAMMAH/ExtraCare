"""Secondary Report parity S-4a: Student assessment scores (Report Entry)

Revision ID: 114_report_scores
Revises: 113_report_cumulatives
Create Date: 2026-07-29 23:30:00.000000

Per-pupil raw scores for assessment components (the Report Entry store the
cumulative evaluator reads). Additive.
"""
from alembic import op
import sqlalchemy as sa


revision = "114_report_scores"
down_revision = "113_report_cumulatives"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_assessment_scores",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("assessment_id", sa.String(length=36), nullable=False),
        sa.Column("score", sa.Numeric(6, 2), nullable=True),
        sa.Column("recorded_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "student_id", "subject_id", "assessment_id", name="uq_student_assessment_score"),
    )
    op.create_index("ix_student_assessment_scores_student_id", "student_assessment_scores", ["student_id"])
    op.create_index("ix_student_assessment_scores_subject_id", "student_assessment_scores", ["subject_id"])
    op.create_index("ix_student_assessment_scores_assessment_id", "student_assessment_scores", ["assessment_id"])
    op.create_index("ix_student_assessment_scores_subj", "student_assessment_scores", ["subject_id", "assessment_id"])


def downgrade() -> None:
    op.drop_table("student_assessment_scores")
