"""Pastoral Batch D-1: Hostel Setup (managers + life grades + comment bank)

Revision ID: 103_pastoral_hostel_setup
Revises: 102_pastoral_point_award_types
Create Date: 2026-07-28 17:30:00.000000

Config tables deepening the Hostel Setup hub tab. Hostel Students roster rides
the existing boarding_allocations table (no new table). Additive.
"""
from alembic import op
import sqlalchemy as sa


revision = "103_pastoral_hostel_setup"
down_revision = "102_pastoral_point_award_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hostel_managers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("hostel_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hostel_id"], ["hostels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "hostel_id", "user_id", name="uq_hostel_manager"),
    )
    op.create_index("ix_hostel_managers_hostel_id", "hostel_managers", ["hostel_id"])
    op.create_index("ix_hostel_managers_user_id", "hostel_managers", ["user_id"])

    op.create_table(
        "hostel_life_grades",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hostel_life_grades_org_id", "hostel_life_grades", ["org_id"])

    op.create_table(
        "hostel_comment_bank",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hostel_comment_bank_org_id", "hostel_comment_bank", ["org_id"])


def downgrade() -> None:
    op.drop_table("hostel_comment_bank")
    op.drop_table("hostel_life_grades")
    op.drop_table("hostel_managers")
