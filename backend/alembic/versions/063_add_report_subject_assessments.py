"""School Reports R2b: per-subject Cambridge overlay switch

Revision ID: 063_subject_assessments
Revises: 062_cbt_remark_note
Create Date: 2026-07-13 11:00:00.000000

Additive + reversible. One table (section, subject) → carries_cambridge: which
subjects carry a Cambridge assessment overlay in a section's hybrid report. The
Nigerian numeric marks always show; the Cambridge attainment (descriptor, fed by
R3 strand domains) is layered on when the flag is set.
"""
from alembic import op
import sqlalchemy as sa


revision = "063_subject_assessments"
down_revision = "062_cbt_remark_note"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_subject_assessments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("section_id", sa.String(length=36), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("carries_cambridge", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cambridge_scale_id", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["section_id"], ["school_sections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cambridge_scale_id"], ["grading_scales.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "section_id", "subject_id", name="uq_report_subject_assessment"),
    )
    op.create_index("ix_report_subject_assess_section", "report_subject_assessments", ["section_id"])
    op.create_index("ix_report_subject_assessments_subject_id", "report_subject_assessments", ["subject_id"])


def downgrade() -> None:
    op.drop_index("ix_report_subject_assessments_subject_id", table_name="report_subject_assessments")
    op.drop_index("ix_report_subject_assess_section", table_name="report_subject_assessments")
    op.drop_table("report_subject_assessments")
