"""Add users.force_password_change

Revision ID: 036_add_force_password_change
Revises: 035_add_teacher_ratings
Create Date: 2026-07-07 13:00:00.000000

Additive + reversible. Backs admin-initiated password reset: when an admin resets
a user to a temp password, this flag forces a change before the account is usable.
Existing rows default to false.
"""

from alembic import op
import sqlalchemy as sa


revision = "036_add_force_password_change"
down_revision = "035_add_teacher_ratings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("force_password_change", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "force_password_change")
