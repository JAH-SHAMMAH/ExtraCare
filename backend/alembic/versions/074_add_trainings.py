"""Training: trainings + training_sessions

Revision ID: 074_trainings
Revises: 073_leave_policies
Create Date: 2026-07-20 15:00:00.000000

Additive + reversible. Training programs and their scheduled sessions. Matches
TenantMixin — org_id is an indexed String, no FK.
"""
from alembic import op
import sqlalchemy as sa


revision = "074_trainings"
down_revision = "073_leave_policies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trainings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="planned"),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trainings_org_id", "trainings", ["org_id"])
    op.create_index("ix_trainings_org_status", "trainings", ["org_id", "status"])

    op.create_table(
        "training_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("training_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("session_date", sa.Date(), nullable=True),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("facilitator", sa.String(length=150), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["training_id"], ["trainings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_training_sessions_training_id", "training_sessions", ["training_id"])
    op.create_index("ix_training_sessions_session_date", "training_sessions", ["session_date"])
    op.create_index("ix_training_sessions_org_id", "training_sessions", ["org_id"])
    op.create_index("ix_training_sessions_org_date", "training_sessions", ["org_id", "session_date"])


def downgrade() -> None:
    op.drop_index("ix_training_sessions_org_date", table_name="training_sessions")
    op.drop_index("ix_training_sessions_org_id", table_name="training_sessions")
    op.drop_index("ix_training_sessions_session_date", table_name="training_sessions")
    op.drop_index("ix_training_sessions_training_id", table_name="training_sessions")
    op.drop_table("training_sessions")
    op.drop_index("ix_trainings_org_status", table_name="trainings")
    op.drop_index("ix_trainings_org_id", table_name="trainings")
    op.drop_table("trainings")
