"""Staff assessment rubric: criteria + per-criterion scores

Revision ID: 050_staff_assessment_criteria
Revises: 049_behaviour_tracker_config
Create Date: 2026-07-10 16:00:00.000000

Additive + reversible. Backs "Setup Staff Assessment": a configurable rubric
(staff_assessment_criteria) that the assessment form scores against
(staff_assessment_scores). No change to staff_assessments — its overall_rating
is now derived from the scores when present, else set manually as before.
"""
from alembic import op
import sqlalchemy as sa


revision = "050_staff_assessment_criteria"
down_revision = "049_behaviour_tracker_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_assessment_criteria",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_score", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_staff_assessment_criteria_org_id", "staff_assessment_criteria", ["org_id"])

    op.create_table(
        "staff_assessment_scores",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assessment_id", sa.String(length=36), nullable=False),
        sa.Column("criterion_id", sa.String(length=36), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assessment_id"], ["staff_assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["criterion_id"], ["staff_assessment_criteria.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_id", "criterion_id", name="uq_assessment_criterion_score"),
    )
    op.create_index("ix_staff_assessment_scores_assessment_id", "staff_assessment_scores", ["assessment_id"])
    op.create_index("ix_staff_assessment_scores_criterion_id", "staff_assessment_scores", ["criterion_id"])
    op.create_index("ix_staff_assessment_scores_org_id", "staff_assessment_scores", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_staff_assessment_scores_org_id", table_name="staff_assessment_scores")
    op.drop_index("ix_staff_assessment_scores_criterion_id", table_name="staff_assessment_scores")
    op.drop_index("ix_staff_assessment_scores_assessment_id", table_name="staff_assessment_scores")
    op.drop_table("staff_assessment_scores")
    op.drop_index("ix_staff_assessment_criteria_org_id", table_name="staff_assessment_criteria")
    op.drop_table("staff_assessment_criteria")
