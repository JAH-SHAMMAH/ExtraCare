"""Leave application model.

One row per employee request. Lifecycle is simple:

    pending → approved  (irreversible)
           └→ rejected  (irreversible)

We keep the approver trail (approver_id, decided_at, decision_note) on the
same row rather than a separate audit table — all decisions are already
captured via AuditLog and splitting a one-step workflow across two tables
buys us nothing at this scale.

Tenant-scoped via TenantMixin; `org_id` pinned on every query.
"""
from __future__ import annotations

import enum

from sqlalchemy import Column, String, Date, DateTime, Text, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


class LeaveType(str, enum.Enum):
    ANNUAL = "annual"
    CASUAL = "casual"
    SICK = "sick"
    MATERNITY = "maternity"
    PATERNITY = "paternity"
    BEREAVEMENT = "bereavement"
    UNPAID = "unpaid"
    OTHER = "other"


class LeaveStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class LeaveApplication(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "leave_applications"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    leave_type = Column(Enum(LeaveType), nullable=False, default=LeaveType.ANNUAL)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=True)

    status = Column(Enum(LeaveStatus), nullable=False, default=LeaveStatus.PENDING, index=True)

    # Decision trail — null until someone approves/rejects.
    approver_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decision_note = Column(Text, nullable=True)

    user = relationship("User", foreign_keys=[user_id], lazy="joined")
    approver = relationship("User", foreign_keys=[approver_id], lazy="joined")

    __table_args__ = (
        # Dashboard filters by org + status (pending queue) and org + start_date
        # (monthly trend). Composite indexes avoid a full-table scan on both.
        Index("ix_leave_org_status", "org_id", "status"),
        Index("ix_leave_org_start", "org_id", "start_date"),
    )
