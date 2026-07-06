"""Add academic records & recognition tables (Batch 3)

Revision ID: 006_add_academic_records
Revises: 005_promotion_batch_safety
Create Date: 2026-06-21 02:00:00.000000

Additive + reversible. Creates: subject_selections, transcripts,
transcript_entries, report_approvals, recognitions. Touches no existing table.
"""

from alembic import op
import sqlalchemy as sa


revision = "006_add_academic_records"
down_revision = "005_promotion_batch_safety"
branch_labels = None
depends_on = None


def _base():
    return (
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "subject_selections",
        *_base(),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("academic_year", sa.String(20), nullable=True),
        sa.Column("term", sa.String(40), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="requested"),
        sa.Column("selected_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_subject_selections"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE", name="fk_subject_selections_student_id_students"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE", name="fk_subject_selections_subject_id_subjects"),
        sa.ForeignKeyConstraint(["selected_by"], ["users.id"], ondelete="SET NULL", name="fk_subject_selections_selected_by_users"),
        sa.UniqueConstraint("student_id", "subject_id", "academic_year", name="uq_subject_selection"),
    )
    op.create_index("ix_subject_selections_id", "subject_selections", ["id"])
    op.create_index("ix_subject_selections_org_id", "subject_selections", ["org_id"])
    op.create_index("ix_subject_selections_student_id", "subject_selections", ["student_id"])
    op.create_index("ix_subject_selections_subject_id", "subject_selections", ["subject_id"])
    op.create_index("ix_subject_selections_org_status", "subject_selections", ["org_id", "status"])

    op.create_table(
        "transcripts",
        *_base(),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("academic_year", sa.String(20), nullable=True),
        sa.Column("term", sa.String(40), nullable=True),
        sa.Column("average", sa.Float(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("issued_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_transcripts"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE", name="fk_transcripts_student_id_students"),
        sa.ForeignKeyConstraint(["issued_by"], ["users.id"], ondelete="SET NULL", name="fk_transcripts_issued_by_users"),
    )
    op.create_index("ix_transcripts_id", "transcripts", ["id"])
    op.create_index("ix_transcripts_org_id", "transcripts", ["org_id"])
    op.create_index("ix_transcripts_student_id", "transcripts", ["student_id"])
    op.create_index("ix_transcripts_student_org", "transcripts", ["student_id", "org_id"])

    op.create_table(
        "transcript_entries",
        *_base(),
        sa.Column("transcript_id", sa.String(36), nullable=False),
        sa.Column("subject_name", sa.String(150), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("grade", sa.String(10), nullable=True),
        sa.Column("remark", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_transcript_entries"),
        sa.ForeignKeyConstraint(["transcript_id"], ["transcripts.id"], ondelete="CASCADE", name="fk_transcript_entries_transcript_id_transcripts"),
    )
    op.create_index("ix_transcript_entries_id", "transcript_entries", ["id"])
    op.create_index("ix_transcript_entries_org_id", "transcript_entries", ["org_id"])
    op.create_index("ix_transcript_entries_transcript_id", "transcript_entries", ["transcript_id"])
    op.create_index("ix_transcript_entries_transcript", "transcript_entries", ["transcript_id", "org_id"])

    op.create_table(
        "report_approvals",
        *_base(),
        sa.Column("class_id", sa.String(36), nullable=True),
        sa.Column("academic_year", sa.String(20), nullable=True),
        sa.Column("term", sa.String(40), nullable=True),
        sa.Column("stage", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("submitted_by", sa.String(36), nullable=True),
        sa.Column("reviewed_by", sa.String(36), nullable=True),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_report_approvals"),
        sa.ForeignKeyConstraint(["class_id"], ["school_classes.id"], ondelete="CASCADE", name="fk_report_approvals_class_id_school_classes"),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"], ondelete="SET NULL", name="fk_report_approvals_submitted_by_users"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL", name="fk_report_approvals_reviewed_by_users"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL", name="fk_report_approvals_approved_by_users"),
    )
    op.create_index("ix_report_approvals_id", "report_approvals", ["id"])
    op.create_index("ix_report_approvals_org_id", "report_approvals", ["org_id"])
    op.create_index("ix_report_approvals_class_id", "report_approvals", ["class_id"])
    op.create_index("ix_report_approvals_org_stage", "report_approvals", ["org_id", "stage"])

    op.create_table(
        "recognitions",
        *_base(),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("points", sa.Integer(), nullable=True),
        sa.Column("house", sa.String(80), nullable=True),
        sa.Column("category", sa.String(80), nullable=True),
        sa.Column("award_type", sa.String(40), nullable=True),
        sa.Column("term", sa.String(40), nullable=True),
        sa.Column("awarded_on", sa.Date(), nullable=True),
        sa.Column("recorded_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_recognitions"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE", name="fk_recognitions_student_id_students"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL", name="fk_recognitions_recorded_by_users"),
    )
    op.create_index("ix_recognitions_id", "recognitions", ["id"])
    op.create_index("ix_recognitions_org_id", "recognitions", ["org_id"])
    op.create_index("ix_recognitions_type", "recognitions", ["type"])
    op.create_index("ix_recognitions_student_id", "recognitions", ["student_id"])
    op.create_index("ix_recognitions_org_type", "recognitions", ["org_id", "type"])
    op.create_index("ix_recognitions_student_org", "recognitions", ["student_id", "org_id"])
    op.create_index("ix_recognitions_house_org", "recognitions", ["house", "org_id"])


def downgrade() -> None:
    for ix in ["ix_recognitions_house_org", "ix_recognitions_student_org", "ix_recognitions_org_type",
               "ix_recognitions_student_id", "ix_recognitions_type", "ix_recognitions_org_id", "ix_recognitions_id"]:
        op.drop_index(ix, table_name="recognitions")
    op.drop_table("recognitions")

    for ix in ["ix_report_approvals_org_stage", "ix_report_approvals_class_id",
               "ix_report_approvals_org_id", "ix_report_approvals_id"]:
        op.drop_index(ix, table_name="report_approvals")
    op.drop_table("report_approvals")

    for ix in ["ix_transcript_entries_transcript", "ix_transcript_entries_transcript_id",
               "ix_transcript_entries_org_id", "ix_transcript_entries_id"]:
        op.drop_index(ix, table_name="transcript_entries")
    op.drop_table("transcript_entries")

    for ix in ["ix_transcripts_student_org", "ix_transcripts_student_id",
               "ix_transcripts_org_id", "ix_transcripts_id"]:
        op.drop_index(ix, table_name="transcripts")
    op.drop_table("transcripts")

    for ix in ["ix_subject_selections_org_status", "ix_subject_selections_subject_id",
               "ix_subject_selections_student_id", "ix_subject_selections_org_id", "ix_subject_selections_id"]:
        op.drop_index(ix, table_name="subject_selections")
    op.drop_table("subject_selections")
