"""Add missing organizations columns: features, onboarding_step, onboarding_completed_at

These columns exist on the Organization ORM model but were never captured in
a migration, causing UndefinedColumnError on fresh databases built from
alembic upgrade head.

Revision ID: 122_add_org_missing_columns
Revises: 121_narrow_student_role_scopes
Create Date: 2026-08-18
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "122_add_org_missing_columns"
down_revision = "121_narrow_student_role_scopes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("features", sa.JSON(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "onboarding_step",
            sa.String(length=32),
            nullable=False,
            server_default="modules",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Drop the server_default after backfilling existing rows — the model
    # applies "modules" as a Python-side default on new inserts, not a DB-side one.
    op.alter_column("organizations", "onboarding_step", server_default=None)


def downgrade() -> None:
    op.drop_column("organizations", "onboarding_completed_at")
    op.drop_column("organizations", "onboarding_step")
    op.drop_column("organizations", "features")
