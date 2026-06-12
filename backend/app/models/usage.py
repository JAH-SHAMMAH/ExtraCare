"""
Aggregated per-tenant usage counters.

One row per (org, module, event_type, day). Written through the in-memory
buffer in services.usage — never inserted one-per-event. The unique
constraint is the upsert key; concurrent buffer flushes converge on the
same row via UPDATE + fallback INSERT.
"""

from sqlalchemy import Column, String, Integer, Date, UniqueConstraint, Index
from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class UsageEvent(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "usage_events"

    # "school" / "hospital" / "business" for module-scoped usage;
    # "platform" for cross-cutting events (user_created, login, ...).
    module = Column(String(64), nullable=False, index=True)

    # "request" for the middleware counter. Explicit event types are
    # free-form but conventionally snake_case ("user_created",
    # "student_created", "invoice_created", ...).
    event_type = Column(String(64), nullable=False, index=True)

    count = Column(Integer, nullable=False, default=0)

    # Daily bucket. Kept as DATE (not DATETIME) so aggregation queries
    # group naturally without a date_trunc dance.
    date_bucket = Column(Date, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("org_id", "module", "event_type", "date_bucket", name="uq_usage_bucket"),
        Index("ix_usage_org_date", "org_id", "date_bucket"),
    )
