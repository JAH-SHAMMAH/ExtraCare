"""Phones that allowed alerts outside the app

Revision ID: 148_push_subscriptions
Revises: 147_office_tables_sync
"""
from alembic import op

revision = "148_push_subscriptions"
down_revision = "147_office_tables_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.models.push import PushSubscription
    PushSubscription.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.drop_table("push_subscriptions")
