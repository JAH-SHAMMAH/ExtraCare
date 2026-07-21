"""Staff attendance (HR Access Control) — clock-in / clock-out events.

Mirrors the student ``AttendanceEvent`` design (an event-sourced, ZKTeco-ready
punch log) but in its OWN table keyed to a staff ``User`` — the student event
model is FK'd to ``students`` and shouldn't be entangled with staff concerns.
Same provenance fields (source / external_ref / device_id) so a future biometric
adapter can push staff punches idempotently, exactly like the student layer.
"""
from __future__ import annotations

import enum

from sqlalchemy import (
    Column, String, DateTime, Time, Enum, ForeignKey, Index, Text, Integer, Boolean, Float, UniqueConstraint,
)

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


class StaffAttendanceSettings(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """One row per org — staff clock configuration (Access Control › Configuration).

    Work hours + a late-arrival grace period drive the "late" flag on clock-ins;
    geofencing (a centre + radius) is enforced at self clock-in when enabled.
    """
    __tablename__ = "staff_attendance_settings"

    work_start_time = Column(Time, nullable=True)          # e.g. 08:00
    work_end_time = Column(Time, nullable=True)            # e.g. 16:00
    late_grace_minutes = Column(Integer, nullable=False, default=0)   # minutes after start before "late"

    geofence_enabled = Column(Boolean, nullable=False, default=False)
    geofence_lat = Column(Float, nullable=True)
    geofence_lng = Column(Float, nullable=True)
    geofence_radius_m = Column(Integer, nullable=True)     # permitted radius, metres

    __table_args__ = (UniqueConstraint("org_id", name="uq_staff_attendance_settings_org"),)
