"""SubjectReportSubmission: per-subject report sign-off

Revision ID: 126_subject_report_submission
Revises: 125_report_approval_publish
Create Date: 2026-09-25

A new table only — nothing existing is altered, and no backfill.

WHY NO BACKFILL. A row here means "a named teacher attested their marks were
finished, at this moment". There is no way to invent that retrospectively: the
12 classes whose reports are already published were submitted at the CLASS grain
by their PC teacher, and fabricating per-subject rows would put sign-offs in
teachers' names that they never gave. An empty table correctly says no subject
has been individually signed off yet.

That also means the readiness grid shows every subject as outstanding for those
12 classes. It is accurate, and it does NOT block anything: the class-level
submit reports outstanding subjects but does not gate on them (see
submit_class_report), precisely so this table starting empty cannot wedge a
workflow that works today.

`sub_term_id` is nullable, so the unique constraint does not bind when it is
NULL — Postgres treats NULLs as distinct. The endpoint's pre-insert check is
what enforces one sign-off per grain; the constraint is the backstop for the
non-NULL case and for concurrent inserts.
"""
from alembic import op
import sqlalchemy as sa

revision = "126_subject_report_submission"
down_revision = "125_report_approval_publish"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subject_report_submissions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("class_id", sa.String(length=36),
                  sa.ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", sa.String(length=36),
                  sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term_id", sa.String(length=36),
                  sa.ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sub_term_id", sa.String(length=36),
                  sa.ForeignKey("academic_sub_terms.id", ondelete="CASCADE"), nullable=True),
        sa.Column("submitted_by", sa.String(length=36),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score_count", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("class_id", "subject_id", "term_id", "sub_term_id",
                            name="uq_subject_report_submission"),
    )
    op.create_index("ix_subject_report_submissions_class_id", "subject_report_submissions", ["class_id"])
    op.create_index("ix_subject_report_submissions_subject_id", "subject_report_submissions", ["subject_id"])
    op.create_index("ix_subject_report_submissions_term_id", "subject_report_submissions", ["term_id"])
    op.create_index("ix_subject_report_submissions_sub_term_id", "subject_report_submissions", ["sub_term_id"])
    op.create_index("ix_subject_report_submissions_class_term", "subject_report_submissions",
                    ["class_id", "term_id"])


def downgrade() -> None:
    op.drop_index("ix_subject_report_submissions_class_term", table_name="subject_report_submissions")
    op.drop_index("ix_subject_report_submissions_sub_term_id", table_name="subject_report_submissions")
    op.drop_index("ix_subject_report_submissions_term_id", table_name="subject_report_submissions")
    op.drop_index("ix_subject_report_submissions_subject_id", table_name="subject_report_submissions")
    op.drop_index("ix_subject_report_submissions_class_id", table_name="subject_report_submissions")
    op.drop_table("subject_report_submissions")
