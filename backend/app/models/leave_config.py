"""Leave configuration — per-org policy for each leave type (the 'Configure' page).

One row per (org, leave_type) sets how many days that type grants per year, whether
it needs approval, and whether it's offered at all. Staff entitlements are computed
from this (allocated = default_days) minus approved days used — no separate
per-staff balance table, per the lighter scope.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Integer, Boolean, Enum, UniqueConstraint

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin
from app.models.leave import LeaveType


class LeavePolicy(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Per-org rules for a single leave type."""
    __tablename__ = "leave_policies"

    leave_type = Column(Enum(LeaveType), nullable=False)
    default_days = Column(Integer, nullable=False, default=0)
    requires_approval = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (UniqueConstraint("org_id", "leave_type", name="uq_leave_policy_org_type"),)


# Sensible starting allocations shown until an admin saves a policy row.
DEFAULT_LEAVE_DAYS: dict[str, int] = {
    "annual": 20, "casual": 5, "sick": 10, "maternity": 90,
    "paternity": 10, "bereavement": 5, "unpaid": 0, "other": 0,
}
