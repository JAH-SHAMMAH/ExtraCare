"""School Reports R2a: sections, grading scales, report templates

Revision ID: 060_report_templates
Revises: 059_student_reports
Create Date: 2026-07-12 18:00:00.000000

Additive + reversible. Foundation for per-level (EYFS Nursery / Nigerian-Cambridge
hybrid Junior-Secondary) reports:
  • school_sections — the managed Nursery/Junior/Secondary list.
  • school_classes.section_id — nullable FK; NO data backfill here (messy free-text
    `level` can't break the migration). Classes start unassigned and are linked
    explicitly (normalized match, never guessed).
  • grading_scales + reconciled grading_bands (scale_id, position; min/max now
    nullable for descriptor scales; grade widened) — retires the hardcoded scale
    to a fallback.
  • report_templates — per-section format (assessment_mode, CA/exam weights,
    grading scale, print toggles). All numbers are editable data, not constants.
"""
from alembic import op
import sqlalchemy as sa


revision = "060_report_templates"
down_revision = "059_student_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "school_sections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("curriculum", sa.String(length=20), nullable=False, server_default="nigerian"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "name", name="uq_school_sections_org_name"),
    )
    op.create_index("ix_school_sections_org", "school_sections", ["org_id"])

    op.create_table(
        "grading_scales",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("scale_type", sa.String(length=20), nullable=False, server_default="numeric"),
        sa.Column("is_provisional", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "name", name="uq_grading_scales_org_name"),
    )
    op.create_index("ix_grading_scales_org", "grading_scales", ["org_id"])

    # Reconcile grading_bands into scales (previously a flat, unwired list).
    with op.batch_alter_table("grading_bands") as batch:
        batch.add_column(sa.Column("scale_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("position", sa.Integer(), nullable=False, server_default="0"))
        batch.alter_column("grade", existing_type=sa.String(length=10), type_=sa.String(length=20))
        batch.alter_column("min_score", existing_type=sa.Numeric(6, 2), nullable=True)
        batch.alter_column("max_score", existing_type=sa.Numeric(6, 2), nullable=True)
        batch.create_foreign_key("fk_grading_bands_scale", "grading_scales", ["scale_id"], ["id"], ondelete="CASCADE")
        batch.create_index("ix_grading_bands_scale_id", ["scale_id"])

    op.create_table(
        "report_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("section_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("assessment_mode", sa.String(length=20), nullable=False, server_default="hybrid"),
        sa.Column("ca_weight", sa.Numeric(5, 2), nullable=True),
        sa.Column("exam_weight", sa.Numeric(5, 2), nullable=True),
        sa.Column("grading_scale_id", sa.String(length=36), nullable=True),
        sa.Column("show_cognitive_table", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_position", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_attendance", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_affective", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("show_psychomotor", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_provisional", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["section_id"], ["school_sections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["grading_scale_id"], ["grading_scales.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "section_id", name="uq_report_templates_org_section"),
    )
    op.create_index("ix_report_templates_org", "report_templates", ["org_id"])

    # Nullable FK, NO backfill — unassigned classes fall back to the legacy report.
    with op.batch_alter_table("school_classes") as batch:
        batch.add_column(sa.Column("section_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_school_classes_section", "school_sections", ["section_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_school_classes_section_id", ["section_id"])


def downgrade() -> None:
    with op.batch_alter_table("school_classes") as batch:
        batch.drop_index("ix_school_classes_section_id")
        batch.drop_constraint("fk_school_classes_section", type_="foreignkey")
        batch.drop_column("section_id")

    op.drop_index("ix_report_templates_org", table_name="report_templates")
    op.drop_table("report_templates")

    with op.batch_alter_table("grading_bands") as batch:
        batch.drop_index("ix_grading_bands_scale_id")
        batch.drop_constraint("fk_grading_bands_scale", type_="foreignkey")
        batch.alter_column("max_score", existing_type=sa.Numeric(6, 2), nullable=False)
        batch.alter_column("min_score", existing_type=sa.Numeric(6, 2), nullable=False)
        batch.alter_column("grade", existing_type=sa.String(length=20), type_=sa.String(length=10))
        batch.drop_column("position")
        batch.drop_column("scale_id")

    op.drop_index("ix_grading_scales_org", table_name="grading_scales")
    op.drop_table("grading_scales")
    op.drop_index("ix_school_sections_org", table_name="school_sections")
    op.drop_table("school_sections")
