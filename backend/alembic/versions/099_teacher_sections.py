"""Teachers module: teacher_sections (Select-School filter + Assign-To-School)

Revision ID: 099_teacher_sections
Revises: 098_feed_post_audiences
Create Date: 2026-07-27 18:00:00.000000

One current school section per teacher (teacher = User, job_title ~ teacher).
Additive — one new table, no data migration.
"""
from alembic import op
import sqlalchemy as sa


revision = "099_teacher_sections"
down_revision = "098_feed_post_audiences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teacher_sections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("teacher_id", sa.String(length=36), nullable=False),
        sa.Column("section_id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["school_sections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "teacher_id", name="uq_teacher_section_org_teacher"),
    )
    op.create_index("ix_teacher_sections_teacher_id", "teacher_sections", ["teacher_id"])
    op.create_index("ix_teacher_sections_section_id", "teacher_sections", ["section_id"])
    op.create_index("ix_teacher_sections_section", "teacher_sections", ["section_id", "org_id"])
    op.create_index("ix_teacher_sections_org_id", "teacher_sections", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_teacher_sections_org_id", table_name="teacher_sections")
    op.drop_index("ix_teacher_sections_section", table_name="teacher_sections")
    op.drop_index("ix_teacher_sections_section_id", table_name="teacher_sections")
    op.drop_index("ix_teacher_sections_teacher_id", table_name="teacher_sections")
    op.drop_table("teacher_sections")
