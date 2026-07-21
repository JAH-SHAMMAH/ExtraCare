"""Competency Mappings: staff_assessment_criteria.competency

Revision ID: 078_criterion_competency
Revises: 077_staff_confirmations
Create Date: 2026-07-21 11:00:00.000000

Additive + reversible. Adds a nullable ``competency`` column to appraisal criteria,
so each criterion can be mapped to a Competency (from the Competency managed list).
"""
from alembic import op
import sqlalchemy as sa


revision = "078_criterion_competency"
down_revision = "077_staff_confirmations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("staff_assessment_criteria", sa.Column("competency", sa.String(length=150), nullable=True))


def downgrade() -> None:
    op.drop_column("staff_assessment_criteria", "competency")
