"""Add support_requests (server-side Support contact form)

Revision ID: 013_add_support
Revises: 012_add_platform
Create Date: 2026-06-23 17:00:00.000000

Additive + reversible.
"""

from alembic import op
import sqlalchemy as sa


revision = "013_add_support"
down_revision = "012_add_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_requests",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(150), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("emailed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.PrimaryKeyConstraint("id", name="pk_support_requests"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL", name="fk_support_requests_user_id_users"),
    )
    op.create_index("ix_support_requests_id", "support_requests", ["id"])
    op.create_index("ix_support_requests_org_id", "support_requests", ["org_id"])
    op.create_index("ix_support_requests_org", "support_requests", ["org_id"])


def downgrade() -> None:
    op.drop_table("support_requests")
