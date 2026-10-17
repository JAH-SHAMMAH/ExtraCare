"""Per-section report branding (Nursery / Primary / Secondary letterheads)

Revision ID: 140_report_branding_per_section
Revises: 139_parent_report_scope
Create Date: 2026-10-17 12:00:00.000000

report_branding had one row per org (uq_report_branding_org). Fairview's sections
print different logos, heads and passmarks, so a row may now belong to a section.
section_id NULL stays the school-wide default, so every existing row keeps
working unchanged and nothing needs backfilling.

The old unique constraint is replaced by two PARTIAL unique indexes (default row
per org; one row per org+section), since a plain unique on (org_id, section_id)
treats NULLs as distinct.
"""
from alembic import op
import sqlalchemy as sa


revision = "140_report_branding_per_section"
down_revision = "139_parent_report_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("report_branding") as b:
        b.add_column(sa.Column("section_id", sa.String(length=36), nullable=True))
        b.create_foreign_key("fk_report_branding_section", "school_sections",
                             ["section_id"], ["id"], ondelete="CASCADE")
        b.drop_constraint("uq_report_branding_org", type_="unique")
    op.create_index("ix_report_branding_section", "report_branding", ["section_id"])
    op.create_index("uq_report_branding_org_default", "report_branding", ["org_id"], unique=True,
                    postgresql_where=sa.text("section_id IS NULL"),
                    sqlite_where=sa.text("section_id IS NULL"))
    op.create_index("uq_report_branding_org_section", "report_branding", ["org_id", "section_id"], unique=True,
                    postgresql_where=sa.text("section_id IS NOT NULL"),
                    sqlite_where=sa.text("section_id IS NOT NULL"))


def downgrade() -> None:
    # Section rows cannot survive a return to one-row-per-org.
    op.execute("DELETE FROM report_branding WHERE section_id IS NOT NULL")
    op.drop_index("uq_report_branding_org_section", table_name="report_branding")
    op.drop_index("uq_report_branding_org_default", table_name="report_branding")
    op.drop_index("ix_report_branding_section", table_name="report_branding")
    with op.batch_alter_table("report_branding") as b:
        b.drop_constraint("fk_report_branding_section", type_="foreignkey")
        b.drop_column("section_id")
        b.create_unique_constraint("uq_report_branding_org", ["org_id"])
