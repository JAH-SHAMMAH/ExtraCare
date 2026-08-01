"""Secondary Report parity S-1c: Result Type/Photo + Subjects For Score Exclusion

Revision ID: 111_report_level_exclusion
Revises: 110_report_grading_branding
Create Date: 2026-07-29 20:30:00.000000

Per-year-group report options (Junior/Senior + position + photo) and per-year-group
subject score exclusions. Additive.
"""
from alembic import op
import sqlalchemy as sa


revision = "111_report_level_exclusion"
down_revision = "110_report_grading_branding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_level_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("year_group", sa.String(length=60), nullable=False),
        sa.Column("result_type", sa.String(length=20), nullable=False, server_default="junior"),
        sa.Column("show_position", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_photo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "year_group", name="uq_report_level_setting"),
    )
    op.create_index("ix_report_level_settings_org", "report_level_settings", ["org_id"])

    op.create_table(
        "report_subject_exclusions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("year_group", sa.String(length=60), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "year_group", "subject_id", name="uq_report_subject_exclusion"),
    )
    op.create_index("ix_report_subject_exclusions_subject_id", "report_subject_exclusions", ["subject_id"])
    op.create_index("ix_report_subject_exclusions_org", "report_subject_exclusions", ["org_id", "year_group"])


def downgrade() -> None:
    op.drop_table("report_subject_exclusions")
    op.drop_table("report_level_settings")
