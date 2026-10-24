"""per-user notification dismissals; drop plan / onboarding notifications

Revision ID: 158_notification_dismissals
Revises: 157_student_other_name
"""
import sqlalchemy as sa
from alembic import op

revision = "158_notification_dismissals"
down_revision = "157_student_other_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    if "notification_dismissals" not in tables:
        op.create_table(
            "notification_dismissals",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("notification_id", sa.String(36), sa.ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.UniqueConstraint("user_id", "notification_id", name="uq_notification_dismissal"),
        )
    # The school has no plans or onboarding wizard to report on.
    if "notifications" in tables:
        op.execute("DELETE FROM notifications WHERE type IN ('plan_limit', 'onboarding_step')")


def downgrade() -> None:
    if "notification_dismissals" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("notification_dismissals")
