"""Pastoral Batch F-1: Leadership Roles + Pastoral Heads

Revision ID: 106_pastoral_leadership_heads
Revises: 105_pastoral_discipline
Create Date: 2026-07-29 12:00:00.000000

Lightweight pastoral lists (NOT RBAC roles): student leadership roles and staff
pastoral head positions. Additive.
"""
from alembic import op
import sqlalchemy as sa


revision = "106_pastoral_leadership_heads"
down_revision = "105_pastoral_discipline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pastoral_leadership_roles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pastoral_leadership_roles_org_id", "pastoral_leadership_roles", ["org_id"])

    op.create_table(
        "pastoral_heads",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("scope", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pastoral_heads_org_id", "pastoral_heads", ["org_id"])
    op.create_index("ix_pastoral_heads_user_id", "pastoral_heads", ["user_id"])


def downgrade() -> None:
    op.drop_table("pastoral_heads")
    op.drop_table("pastoral_leadership_roles")
