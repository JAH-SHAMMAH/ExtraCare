"""
In-app notifications.

Deliberately flat: one row per delivered notification, no fan-out tables,
no queues. The read side is a straight `SELECT ... WHERE org_id = ? AND
(user_id = ? OR user_id IS NULL) ORDER BY created_at DESC`.

`user_id` nullable means "org-wide" — every member of the tenant sees it.
Frontends collapse these into a single feed client-side.

Types are free-form strings intentionally — we'd rather add a new kind
without a migration than carry an enum that drifts from reality. Keep
them snake_case so grep/analytics stay sane.
"""

from sqlalchemy import Column, String, Boolean, Text, ForeignKey, JSON, Index
from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin


# Canonical types — string constants rather than an Enum so callers can
# extend without a migration. The frontend keys its icon/copy table off
# these values, so don't change them casually.
TYPE_USER_INVITED = "user_invited"
TYPE_ONBOARDING_STEP = "onboarding_step"
TYPE_PLAN_LIMIT = "plan_limit"
TYPE_SYSTEM = "system"
# Attendance arrival/departure alerts sent to a student's guardians.
TYPE_ATTENDANCE = "attendance"


class Notification(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "notifications"

    # Null = org-wide broadcast. Any member of the tenant can see it.
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)

    type = Column(String(64), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)

    # Small structured payload the frontend can render extras from (e.g.
    # the invited user's email, the plan being recommended). Optional.
    payload = Column(JSON, nullable=True)

    read = Column(Boolean, nullable=False, default=False, index=True)

    __table_args__ = (
        # Primary query shape: unread notifications for a user, newest first.
        Index("ix_notif_org_user_read", "org_id", "user_id", "read"),
    )
