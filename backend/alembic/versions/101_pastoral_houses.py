"""Pastoral Batch B: house scoping/status + House Masters/Weeks + student assignments

Revision ID: 101_pastoral_houses
Revises: 100_pastoral_settings
Create Date: 2026-07-28 12:00:00.000000

Enriches school_houses (school section + active flag) and adds the pastoral house
masters / house weeks / per-student pastoral assignment (mentor/house/leader).
Additive.
"""
from alembic import op
import sqlalchemy as sa


revision = "101_pastoral_houses"
down_revision = "100_pastoral_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # school_houses: optional section scope + active flag.
    op.add_column("school_houses", sa.Column("section_id", sa.String(length=36), nullable=True))
    op.add_column("school_houses", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index("ix_school_houses_section_id", "school_houses", ["section_id"])

    op.create_table(
        "house_masters",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("house_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["house_id"], ["school_houses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_house_masters_house_id", "house_masters", ["house_id"])
    op.create_index("ix_house_masters_user_id", "house_masters", ["user_id"])
    op.create_index("ix_house_masters_house", "house_masters", ["house_id", "org_id"])
    op.create_index("ix_house_masters_org_id", "house_masters", ["org_id"])

    op.create_table(
        "house_weeks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_house_weeks_org_id", "house_weeks", ["org_id"])

    op.create_table(
        "student_pastoral_assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("house_id", sa.String(length=36), nullable=True),
        sa.Column("mentor_id", sa.String(length=36), nullable=True),
        sa.Column("is_leader", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["house_id"], ["school_houses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["mentor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "student_id", name="uq_student_pastoral_org_student"),
    )
    op.create_index("ix_student_pastoral_assignments_student_id", "student_pastoral_assignments", ["student_id"])
    op.create_index("ix_student_pastoral_assignments_house_id", "student_pastoral_assignments", ["house_id"])
    op.create_index("ix_student_pastoral_assignments_mentor_id", "student_pastoral_assignments", ["mentor_id"])
    op.create_index("ix_student_pastoral_assignments_org_id", "student_pastoral_assignments", ["org_id"])


def downgrade() -> None:
    op.drop_table("student_pastoral_assignments")
    op.drop_table("house_weeks")
    op.drop_table("house_masters")
    op.drop_index("ix_school_houses_section_id", table_name="school_houses")
    op.drop_column("school_houses", "is_active")
    op.drop_column("school_houses", "section_id")
