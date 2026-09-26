"""SubjectReportComment: a subject teacher's per-pupil remark

Revision ID: 127_subject_report_comment
Revises: 126_subject_report_submission
Create Date: 2026-09-26

A new table only. Nothing existing is altered, and there is no backfill --
nobody has written a per-subject remark yet, and there is nothing to derive one
from.

DELIBERATELY NOT a third `kind` on student_report_comments. That table is unique
on (org_id, student_id, term_id, sub_term_id, kind). Adding a nullable
subject_id to that constraint would make the existing head/pc rows -- which
would carry NULL -- no longer unique, because Postgres treats NULLs as distinct
in a unique index. A pupil could then collect two School Head comments with
nothing to stop it. The uniqueness of the card's existing comment slots is worth
more than reusing a table.

Every column of the unique constraint here is NOT NULL, so the constraint
actually binds -- unlike 126, where a nullable sub_term_id left the endpoint's
pre-check doing the real work.
"""
from alembic import op
import sqlalchemy as sa

revision = "127_subject_report_comment"
down_revision = "126_subject_report_submission"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subject_report_comments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("student_id", sa.String(length=36),
                  sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", sa.String(length=36),
                  sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term_id", sa.String(length=36),
                  sa.ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sub_term_id", sa.String(length=36),
                  sa.ForeignKey("academic_sub_terms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.String(length=36),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("org_id", "student_id", "subject_id", "term_id", "sub_term_id",
                            name="uq_subject_report_comment"),
    )
    op.create_index("ix_subject_report_comments_student_id", "subject_report_comments", ["student_id"])
    op.create_index("ix_subject_report_comments_subject_id", "subject_report_comments", ["subject_id"])
    op.create_index("ix_subject_report_comments_term_id", "subject_report_comments", ["term_id"])
    op.create_index("ix_subject_report_comments_sub_term_id", "subject_report_comments", ["sub_term_id"])
    op.create_index("ix_subject_report_comments_term", "subject_report_comments",
                    ["org_id", "term_id", "sub_term_id"])


def downgrade() -> None:
    op.drop_index("ix_subject_report_comments_term", table_name="subject_report_comments")
    op.drop_index("ix_subject_report_comments_sub_term_id", table_name="subject_report_comments")
    op.drop_index("ix_subject_report_comments_term_id", table_name="subject_report_comments")
    op.drop_index("ix_subject_report_comments_subject_id", table_name="subject_report_comments")
    op.drop_index("ix_subject_report_comments_student_id", table_name="subject_report_comments")
    op.drop_table("subject_report_comments")
