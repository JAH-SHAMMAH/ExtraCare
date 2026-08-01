"""Secondary Report parity S-2: Assessment Group + Assessment leaf components

Revision ID: 112_report_assessments
Revises: 111_report_level_exclusion
Create Date: 2026-07-29 21:30:00.000000

Named assessment groups + leaf mark components (CBT/Theory/PRJ/PBT/EXAM) scoped by
(term, sub-term, level) with a max score and display decimals. Additive.
"""
from alembic import op
import sqlalchemy as sa


revision = "112_report_assessments"
down_revision = "111_report_level_exclusion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessment_groups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "name", name="uq_assessment_groups_org_name"),
    )
    op.create_index("ix_assessment_groups_org", "assessment_groups", ["org_id"])

    op.create_table(
        "assessments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=True),
        sa.Column("max_score", sa.Numeric(6, 2), nullable=False, server_default="100"),
        sa.Column("term_id", sa.String(length=36), nullable=False),
        sa.Column("sub_term_id", sa.String(length=36), nullable=False),
        sa.Column("year_group", sa.String(length=60), nullable=True),
        sa.Column("decimal_places", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("group_id", sa.String(length=36), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["term_id"], ["academic_terms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sub_term_id"], ["academic_sub_terms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["assessment_groups.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assessments_term_id", "assessments", ["term_id"])
    op.create_index("ix_assessments_sub_term_id", "assessments", ["sub_term_id"])
    op.create_index("ix_assessments_org_term", "assessments", ["org_id", "term_id"])


def downgrade() -> None:
    op.drop_table("assessments")
    op.drop_table("assessment_groups")
