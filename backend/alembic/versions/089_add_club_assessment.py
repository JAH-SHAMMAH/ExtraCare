"""Clubs: club assessment (grade students per term)

Revision ID: 089_club_assessment
Revises: 088_club_membership_status
Create Date: 2026-07-22 21:15:00.000000

Additive + reversible. Adds club_assessments — a student's club grade (against a
ClubGrade band) + remarks for a session/term. One row per club+student+term.
"""
from alembic import op
import sqlalchemy as sa


revision = "089_club_assessment"
down_revision = "088_club_membership_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "club_assessments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("club_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("academic_year", sa.String(length=20), nullable=True),
        sa.Column("term", sa.String(length=40), nullable=True),
        sa.Column("grade_id", sa.String(length=36), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("assessed_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["grade_id"], ["club_grades.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assessed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "club_id", "student_id", "academic_year", "term", name="uq_club_assessment"),
    )
    op.create_index("ix_club_assessments_club_org", "club_assessments", ["club_id", "org_id"])
    op.create_index("ix_club_assessments_club_id", "club_assessments", ["club_id"])
    op.create_index("ix_club_assessments_student_id", "club_assessments", ["student_id"])
    op.create_index("ix_club_assessments_org_id", "club_assessments", ["org_id"])


def downgrade() -> None:
    op.drop_table("club_assessments")
