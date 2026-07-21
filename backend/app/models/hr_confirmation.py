"""Staff Confirmation (HR) — the probation → confirmed workflow.

A confirmation is started for a staff member on probation and later decided
(confirm / decline). Confirming flips their ``HRProfile.employment_status`` from
``probation`` to ``active`` — the confirmation row is the audit trail. Gated
``hr:write``.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, Date, DateTime, ForeignKey, Index

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


class StaffConfirmation(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """One staff confirmation case."""
    __tablename__ = "staff_confirmations"

    staff_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    probation_start = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    status = Column(String(20), default="pending", nullable=False)   # pending | confirmed | declined
    recommendation = Column(Text, nullable=True)
    decided_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (Index("ix_staff_confirmations_org_status", "org_id", "status"),)
