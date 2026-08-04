"""User.is_seed_account flag (report-demo marker) + backfill legacy @fairview.seed

Revision ID: 117_user_is_seed_account
Revises: 116_class_pc_teacher
Create Date: 2026-08-02 16:00:00.000000

Adds the authoritative "this account is fake" marker. Backfills it True for any
already-seeded @fairview.seed accounts (a provably-fake domain the login gate
forbids) so they are hidden from the Users list and removable by the new
flag-based teardown. Additive.
"""
from alembic import op
import sqlalchemy as sa


revision = "117_user_is_seed_account"
down_revision = "116_class_pc_teacher"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_seed_account", sa.Boolean(), nullable=False, server_default=sa.false()))
    # Backfill: the earlier seed run created @fairview.seed logins before this flag
    # existed. That domain can never be a real account (the login gate only permits
    # the school domain), so mark them as seed accounts now.
    op.execute("UPDATE users SET is_seed_account = true WHERE lower(email) LIKE '%@fairview.seed'")


def downgrade() -> None:
    op.drop_column("users", "is_seed_account")
