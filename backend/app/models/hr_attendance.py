"""Staff attendance (HR Access Control) — clock-in / clock-out events.

Mirrors the student ``AttendanceEvent`` design (an event-sourced, ZKTeco-ready
punch log) but in its OWN table keyed to a staff ``User`` — the student event
model is FK'd to ``students`` and shouldn't be entangled with staff concerns.
Same provenance fields (source / external_ref / device_id) so a future biometric
adapter can push staff punches idempotently, exactly like the student layer.
"""
from __future__ import annotations

import enum

from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Index, Text

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class StaffClockType(str, enum.Enum):
    CLOCK_IN = "clock_in"
    CLOCK_OUT = "clock_out"


class StaffClockSource(str, enum.Enum):
    MANUAL = "manual"   # entered in the portal (self clock, or admin correction)
    ZKTECO = "zkteco"   # pushed by a ZKTeco biometric device adapter (future)
    IMPORT = "import"   # bulk import / sync
    API = "api"         # generic external integration


class StaffAttendanceEvent(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """One staff clock-in / clock-out punch at a precise time."""
    __tablename__ = "staff_attendance_events"

    staff_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(Enum(StaffClockType), nullable=False)
    event_time = Column(DateTime(timezone=True), nullable=False, index=True)

    # Provenance — mirrors the student attendance layer for ZKTeco-readiness.
    source = Column(Enum(StaffClockSource), nullable=False, default=StaffClockSource.MANUAL)
    external_ref = Column(String(128), nullable=True, index=True)   # device punch id → idempotent ingest
    device_id = Column(String(128), nullable=True)
    note = Column(Text, nullable=True)
    recorded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # admin who added a manual event

    __table_args__ = (Index("ix_staff_attendance_org_staff_time", "org_id", "staff_user_id", "event_time"),)
