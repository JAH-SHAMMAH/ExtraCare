"""
Bulk SMS models (Phase 6.6).

A campaign is one send action by an admin (an SMS "blast"). Each campaign
fans out into N SmsMessage rows — one per recipient — which hold the
delivery status for that recipient. Keeping campaign and message separate
means the admin list view is a cheap query on one row per send, while the
per-recipient detail drill-down pulls from the message table.
"""

import enum

from sqlalchemy import (
    Column, String, Integer, DateTime, Text, Enum, ForeignKey, JSON, Index,
)

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class SmsTargetType(str, enum.Enum):
    ALL_STUDENTS = "all_students"
    ALL_PARENTS = "all_parents"
    ALL_TEACHERS = "all_teachers"
    CLASS = "class"
    CLASS_PARENTS = "class_parents"
    CUSTOM = "custom"


class SmsCampaignStatus(str, enum.Enum):
    # Kept simple on purpose. The mock provider resolves synchronously so
    # most campaigns go directly DRAFT → COMPLETED. When we plug in a real
    # async provider (Termii/AT) we'll add SENDING between them.
    QUEUED = "queued"
    SENDING = "sending"
    COMPLETED = "completed"
    FAILED = "failed"


class SmsMessageStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"           # accepted by provider
    DELIVERED = "delivered" # provider confirmed delivery to handset
    FAILED = "failed"


class SmsCampaign(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "sms_campaigns"

    # Display + audit
    subject = Column(String(255), nullable=True)  # internal label, optional
    body = Column(Text, nullable=False)
    sender_id = Column(String(20), nullable=False)  # e.g. "FAIRVIEW"
    provider = Column(String(40), nullable=False, default="mock")
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)

    # Targeting — resolved server-side from this pair. `target_value` is a
    # JSON blob so CLASS can store class_id, CUSTOM a list of user ids, etc.
    target_type = Column(Enum(SmsTargetType), nullable=False)
    target_value = Column(JSON, nullable=True)
    target_label = Column(String(255), nullable=True)  # human-friendly label for UI

    # Counters kept denormalised so the list-view never has to aggregate
    # the messages table. Updated atomically in the send handler.
    total_recipients = Column(Integer, default=0, nullable=False)
    sent_count = Column(Integer, default=0, nullable=False)
    delivered_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)

    status = Column(Enum(SmsCampaignStatus), default=SmsCampaignStatus.QUEUED, nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        # Campaigns list is sorted by recency, scoped to tenant.
        Index("ix_sms_campaigns_org_created", "org_id", "created_at"),
    )


class SmsMessage(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "sms_messages"

    campaign_id = Column(String(36), ForeignKey("sms_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    # Recipient identity snapshotted at send time. Keeping name+phone on the
    # message row lets logs survive user renames/deletions.
    recipient_user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    recipient_name = Column(String(255), nullable=True)
    recipient_phone = Column(String(30), nullable=False)

    status = Column(Enum(SmsMessageStatus), default=SmsMessageStatus.PENDING, nullable=False, index=True)
    provider_message_id = Column(String(120), nullable=True, index=True)
    # Raw provider DLR payload — kept JSON so the schema doesn't shift when
    # we plug in a new provider (Termii vs AT vs Twilio all have different
    # status field names). Webhook handler writes here; nothing reads it
    # yet on the demo path.
    provider_status_raw = Column(JSON, nullable=True)
    error_message = Column(String(500), nullable=True)

    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        # Detail drawer: all messages for one campaign, most recent first.
        Index("ix_sms_messages_campaign_status", "campaign_id", "status"),
    )
