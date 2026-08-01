"""Secondary Report parity S-1b: Grading System flags + School branding

Revision ID: 110_report_grading_branding
Revises: 109_report_comments
Create Date: 2026-07-29 19:00:00.000000

Adds show_in_table + purpose to grading scales, and a per-org report branding
row (motto / titles / passmarks / images). Additive.
"""
from alembic import op
import sqlalchemy as sa


revision = "110_report_grading_branding"
down_revision = "109_report_comments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("grading_scales", sa.Column("show_in_table", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("grading_scales", sa.Column("purpose", sa.String(length=20), nullable=False, server_default="grade"))

    op.create_table(
        "report_branding",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("school_motto", sa.String(length=200), nullable=True),
        sa.Column("school_name_alias", sa.String(length=150), nullable=True),
        sa.Column("school_address", sa.Text(), nullable=True),
        sa.Column("school_website", sa.String(length=200), nullable=True),
        sa.Column("school_email", sa.String(length=200), nullable=True),
        sa.Column("school_phone", sa.String(length=60), nullable=True),
        sa.Column("class_teacher_title", sa.String(length=80), nullable=True),
        sa.Column("school_head_title", sa.String(length=80), nullable=True),
        sa.Column("school_head_name", sa.String(length=150), nullable=True),
        sa.Column("full_term_passmark", sa.Numeric(6, 2), nullable=True),
        sa.Column("mid_term_passmark", sa.Numeric(6, 2), nullable=True),
        sa.Column("min_average_honours", sa.Numeric(6, 2), nullable=True),
        sa.Column("promotion_comment", sa.String(length=120), nullable=True),
        sa.Column("demotion_comment", sa.String(length=120), nullable=True),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("head_signature_url", sa.String(length=500), nullable=True),
        sa.Column("logo_background_url", sa.String(length=500), nullable=True),
        sa.Column("sponsor_url", sa.String(length=500), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_report_branding_org"),
    )
    op.create_index("ix_report_branding_org", "report_branding", ["org_id"])


def downgrade() -> None:
    op.drop_table("report_branding")
    op.drop_column("grading_scales", "purpose")
    op.drop_column("grading_scales", "show_in_table")
