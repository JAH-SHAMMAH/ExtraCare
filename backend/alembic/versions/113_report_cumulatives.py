"""Secondary Report parity S-3: Cumulative curated engine

Revision ID: 113_report_cumulatives
Revises: 112_report_assessments
Create Date: 2026-07-29 22:30:00.000000

Named report columns (cumulatives) composed from assessments and/or other
cumulatives, with a combine type (score / percentage / custom_percentage).
Additive.
"""
from alembic import op
import sqlalchemy as sa


revision = "113_report_cumulatives"
down_revision = "112_report_assessments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cumulatives",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=True),
        sa.Column("term_id", sa.String(length=36), nullable=False),
        sa.Column("sub_term_id", sa.String(length=36), nullable=False),
        sa.Column("year_group", sa.String(length=60), nullable=True),
        sa.Column("cumul_type", sa.String(length=20), nullable=False, server_default="score"),
        sa.Column("max_percent", sa.Numeric(6, 2), nullable=True),
        sa.Column("decimal_places", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["term_id"], ["academic_terms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sub_term_id"], ["academic_sub_terms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cumulatives_term_id", "cumulatives", ["term_id"])
    op.create_index("ix_cumulatives_sub_term_id", "cumulatives", ["sub_term_id"])
    op.create_index("ix_cumulatives_org_term", "cumulatives", ["org_id", "term_id"])

    op.create_table(
        "cumulative_components",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("cumulative_id", sa.String(length=36), nullable=False),
        sa.Column("ref_type", sa.String(length=20), nullable=False),
        sa.Column("ref_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["cumulative_id"], ["cumulatives.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cumulative_components_cumulative", "cumulative_components", ["cumulative_id"])


def downgrade() -> None:
    op.drop_table("cumulative_components")
    op.drop_table("cumulatives")
