"""Support request records — captured server-side so a contact submission is
never lost even when email delivery fails."""
from __future__ import annotations

from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Index

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class SupportRequest(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "support_requests"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(150), nullable=True)
    email = Column(String(255), nullable=True)
    subject = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    emailed = Column(Boolean, default=False, nullable=False)   # did the SMTP send succeed?
    status = Column(String(20), default="open", nullable=False)  # open | resolved

    __table_args__ = (
        Index("ix_support_requests_org", "org_id"),
    )
