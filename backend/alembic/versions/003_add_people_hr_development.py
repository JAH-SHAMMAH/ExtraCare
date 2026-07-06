"""Add staff_assessments + talent_candidates (HR Development, Batch 1)

Revision ID: 003_add_people_hr_development
Revises: 002_add_attendance_events
Create Date: 2026-06-21 00:00:00.000000

Purely additive and fully reversible:
- creates `staff_assessments` and `talent_candidates` with their indexes
- touches no existing table or row

Parents Directory (the third Batch 1 feature) reuses the existing
`parent_guardians` table, so it needs no schema change here.
"""

from alembic import op
import sqlalchemy as sa


revision = "003_add_people_hr_development"
down_revision = "002_add_attendance_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_assessments",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("staff_user_id", sa.String(36), nullable=False),
        sa.Column("reviewer_id", sa.String(36), nullable=True),
        sa.Column("period", sa.String(60), nullable=False),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column("overall_rating", sa.Integer(), nullable=True),
        sa.Column("strengths", sa.Text(), nullable=True),
        sa.Column("improvements", sa.Text(), nullable=True),
        sa.Column("goals", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.PrimaryKeyConstraint("id", name="pk_staff_assessments"),
        sa.ForeignKeyConstraint(["staff_user_id"], ["users.id"], ondelete="CASCADE", name="fk_staff_assessments_staff_user_id_users"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL", name="fk_staff_assessments_reviewer_id_users"),
    )
    op.create_index("ix_staff_assessments_id", "staff_assessments", ["id"])
    op.create_index("ix_staff_assessments_org_id", "staff_assessments", ["org_id"])
    op.create_index("ix_staff_assessments_staff_user_id", "staff_assessments", ["staff_user_id"])
    op.create_index("ix_staff_assessments_reviewer_id", "staff_assessments", ["reviewer_id"])
    op.create_index("ix_staff_assessments_staff_org", "staff_assessments", ["staff_user_id", "org_id"])

    op.create_table(
        "talent_candidates",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("role_applied", sa.String(150), nullable=True),
        sa.Column("source", sa.String(80), nullable=True),
        sa.Column("stage", sa.String(20), nullable=False, server_default="applied"),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_talent_candidates"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL", name="fk_talent_candidates_created_by_users"),
    )
    op.create_index("ix_talent_candidates_id", "talent_candidates", ["id"])
    op.create_index("ix_talent_candidates_org_id", "talent_candidates", ["org_id"])
    op.create_index("ix_talent_candidates_email", "talent_candidates", ["email"])
    op.create_index("ix_talent_candidates_org_stage", "talent_candidates", ["org_id", "stage"])


def downgrade() -> None:
    op.drop_index("ix_talent_candidates_org_stage", table_name="talent_candidates")
    op.drop_index("ix_talent_candidates_email", table_name="talent_candidates")
    op.drop_index("ix_talent_candidates_org_id", table_name="talent_candidates")
    op.drop_index("ix_talent_candidates_id", table_name="talent_candidates")
    op.drop_table("talent_candidates")

    op.drop_index("ix_staff_assessments_staff_org", table_name="staff_assessments")
    op.drop_index("ix_staff_assessments_reviewer_id", table_name="staff_assessments")
    op.drop_index("ix_staff_assessments_staff_user_id", table_name="staff_assessments")
    op.drop_index("ix_staff_assessments_org_id", table_name="staff_assessments")
    op.drop_index("ix_staff_assessments_id", table_name="staff_assessments")
    op.drop_table("staff_assessments")
