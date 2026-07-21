"""Staff Transfer Log (HR PIM) — records a staff member moving department/unit.

Creating a transfer both LOGS the move (from → to, with a snapshot of the prior
department) and updates the staff member's current ``User.department``, so the
directory reflects the change. Append-only history. Gated ``hr:write``.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, Date, ForeignKey, Index

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


class StaffTransfer(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """One staff transfer event."""
    __tablename__ = "staff_transfers"

    staff_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    from_department = Column(String(255), nullable=True)   # snapshot of the prior department
    to_department = Column(String(255), nullable=False)
    to_unit = Column(String(150), nullable=True)
    effective_date = Column(Date, nullable=True)
    reason = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (Index("ix_staff_transfers_org_staff", "org_id", "staff_user_id"),)
