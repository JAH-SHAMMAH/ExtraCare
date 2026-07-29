"""Pastoral Batch D-2: Hostel life comments + reports

Revision ID: 104_pastoral_hostel_life
Revises: 103_pastoral_hostel_setup
Create Date: 2026-07-28 18:30:00.000000

Operational layer over the Hostel Setup config: per-boarder life comments (with a
grade off the HostelLifeGrade scale, aggregated by the Result View) and hostel
reports (daily / manager). Additive.
"""
from alembic import op
import sqlalchemy as sa


revision = "104_pastoral_hostel_life"
down_revision = "103_pastoral_hostel_setup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hostel_life_comments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("hostel_id", sa.String(length=36), nullable=True),
        sa.Column("term", sa.String(length=60), nullable=True),
        sa.Column("grade", sa.String(length=80), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("recorded_on", sa.Date(), nullable=True),
        sa.Column("recorded_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hostel_id"], ["hostels.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hostel_life_comments_student_id", "hostel_life_comments", ["student_id"])
    op.create_index("ix_hostel_life_comments_hostel_id", "hostel_life_comments", ["hostel_id"])
    op.create_index("ix_hostel_life_comments_student_org", "hostel_life_comments", ["student_id", "org_id"])

    op.create_table(
        "hostel_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("report_type", sa.String(length=20), nullable=False, server_default="daily"),
        sa.Column("hostel_id", sa.String(length=36), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hostel_id"], ["hostels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hostel_reports_hostel_id", "hostel_reports", ["hostel_id"])
    op.create_index("ix_hostel_reports_type_org", "hostel_reports", ["report_type", "org_id"])


def downgrade() -> None:
    op.drop_table("hostel_reports")
    op.drop_table("hostel_life_comments")
