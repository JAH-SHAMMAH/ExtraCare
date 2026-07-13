"""School Reports R1: per-student per-term report metadata

Revision ID: 059_student_reports
Revises: 058_biometric_tokens
Create Date: 2026-07-12 16:00:00.000000

Additive + reversible. One table holding the human-authored parts of a report
card that aren't derivable from grades — class-teacher / head-teacher comments,
attendance summary, and next-term-begins. Subjects, totals, average and class
position are computed live from Grade rows. One row per (student, term).
"""
from alembic import op
import sqlalchemy as sa


revision = "059_student_reports"
down_revision = "058_biometric_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("term", sa.String(length=50), nullable=False),
        sa.Column("academic_year", sa.String(length=20), nullable=True),
        sa.Column("class_teacher_comment", sa.Text(), nullable=True),
        sa.Column("head_teacher_comment", sa.Text(), nullable=True),
        sa.Column("attendance_present", sa.Integer(), nullable=True),
        sa.Column("attendance_total", sa.Integer(), nullable=True),
        sa.Column("next_term_begins", sa.Date(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "term", "org_id", name="uq_student_report_student_term"),
    )
    op.create_index("ix_student_reports_student_id", "student_reports", ["student_id"])
    op.create_index("ix_student_reports_org_term", "student_reports", ["org_id", "term"])


def downgrade() -> None:
    op.drop_index("ix_student_reports_org_term", table_name="student_reports")
    op.drop_index("ix_student_reports_student_id", table_name="student_reports")
    op.drop_table("student_reports")
