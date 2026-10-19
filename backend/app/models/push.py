"""A phone/browser that agreed to receive alerts outside the app (Web Push)."""
from sqlalchemy import Column, String, Text
from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class PushSubscription(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "push_subscriptions"

    user_id = Column(String(36), nullable=False, index=True)
    endpoint = Column(Text, nullable=False)
    endpoint_hash = Column(String(64), nullable=False, unique=True)
    p256dh = Column(String(200), nullable=False)
    auth = Column(String(100), nullable=False)
    user_agent = Column(String(300), nullable=True)
