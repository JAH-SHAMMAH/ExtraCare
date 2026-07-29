"""Pastoral Batch C: Point System Setup + Award System Setup

Revision ID: 102_pastoral_point_award_types
Revises: 101_pastoral_houses
Create Date: 2026-07-28 16:00:00.000000

Config tables for pastoral point types + award bands. Conduct points and awards
themselves stay on the existing Recognition ledger. Additive.
"""
from alembic import op
import sqlalchemy as sa


revision = "102_pastoral_point_award_types"
down_revision = "101_pastoral_houses"
branch_labels = None
depends_on = None


def _config_table(name, *extra_cols):
    op.create_table(
        name,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        *extra_cols,
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(f"ix_{name}_org_id", name, ["org_id"])


def upgrade() -> None:
    _config_table(
        "point_types",
        sa.Column("scope", sa.String(length=20), nullable=False, server_default="weekly"),
        sa.Column("max_point", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
    )
    _config_table(
        "award_types",
        sa.Column("min_point", sa.Integer(), nullable=True),
        sa.Column("max_point", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("award_types")
    op.drop_table("point_types")
