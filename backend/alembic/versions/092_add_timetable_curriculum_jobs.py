"""TimeTable module: curriculum + timetabler jobs

Revision ID: 092_timetable_curriculum
Revises: 091_timetable_periods
Create Date: 2026-07-23 07:00:00.000000

Additive + reversible. Adds curriculums (class+subject documents) and
timetable_jobs (the simplified Time Tabler generation jobs).
"""
from alembic import op
import sqlalchemy as sa


revision = "092_timetable_curriculum"
down_revision = "091_timetable_periods"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "curriculums",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("class_id", sa.String(length=36), nullable=True),
        sa.Column("subject_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("file_url", sa.String(length=500), nullable=True),
        sa.Column("academic_year", sa.String(length=20), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["class_id"], ["school_classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_curriculums_class_id", "curriculums", ["class_id"])
    op.create_index("ix_curriculums_org_id", "curriculums", ["org_id"])

    op.create_table(
        "timetable_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("period_group_id", sa.String(length=36), nullable=True),
        sa.Column("academic_year", sa.String(length=20), nullable=True),
        sa.Column("period_type", sa.String(length=60), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["period_group_id"], ["period_groups.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_timetable_jobs_org_id", "timetable_jobs", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_timetable_jobs_org_id", table_name="timetable_jobs")
    op.drop_table("timetable_jobs")
    op.drop_index("ix_curriculums_org_id", table_name="curriculums")
    op.drop_index("ix_curriculums_class_id", table_name="curriculums")
    op.drop_table("curriculums")
