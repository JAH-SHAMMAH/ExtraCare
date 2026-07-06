"""Operations models (Batch 6, non-financial): Calendar, Facility, Visitor.

Visitor Management is treated as a SAFEGUARDING record, not just an operational
log: visitor + (especially) child-collection records are audited on every
mutation, soft-deleted only (never silently removed), and a collection captures
WHO authorised the pickup.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, ForeignKey, Index

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


class CalendarEvent(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A school-calendar / planner event."""
    __tablename__ = "calendar_events"

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    start_at = Column(DateTime(timezone=True), nullable=False, index=True)
    end_at = Column(DateTime(timezone=True), nullable=True)
    all_day = Column(Boolean, default=False, nullable=False)
    category = Column(String(40), nullable=True)   # academic | holiday | exam | meeting | sports | other
    location = Column(String(200), nullable=True)
    audience = Column(String(40), default="school", nullable=True)  # school | staff | students
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_calendar_events_org_start", "org_id", "start_at"),
    )


class Facility(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A bookable facility (hall, lab, field, room…)."""
    __tablename__ = "facilities"

    name = Column(String(150), nullable=False)
    type = Column(String(40), nullable=True)       # classroom | hall | lab | field | other
    capacity = Column(Integer, nullable=True)
    location = Column(String(200), nullable=True)
    status = Column(String(20), default="available", nullable=False)  # available | maintenance | unavailable
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("ix_facilities_org", "org_id"),
    )


class FacilityBooking(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A booking of a facility for a time window. Double-booking is guarded."""
    __tablename__ = "facility_bookings"

    facility_id = Column(String(36), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    purpose = Column(Text, nullable=True)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), default="booked", nullable=False)  # booked | cancelled
    booked_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_facility_bookings_facility_org", "facility_id", "org_id"),
    )


class VisitorLog(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A visitor sign-in/out record. Safeguarding: audited + soft-delete only."""
    __tablename__ = "visitor_logs"

    visitor_name = Column(String(200), nullable=False)
    organization = Column(String(200), nullable=True)
    purpose = Column(String(255), nullable=True)
    host_name = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True)
    badge_no = Column(String(40), nullable=True)
    sign_in_at = Column(DateTime(timezone=True), nullable=True)
    sign_out_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default="signed_in", nullable=False)  # signed_in | signed_out
    recorded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_visitor_logs_org_status", "org_id", "status"),
    )


class StudentCollection(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A child pickup/collection record — the safeguarding-critical one.

    ``authorized_by`` captures the staff member who authorised the pickup; every
    mutation is audited and the row is soft-deleted only (never silently removed).
    """
    __tablename__ = "student_collections"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    collector_name = Column(String(200), nullable=False)
    relationship_to_student = Column(String(80), nullable=True)
    authorized_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
    collected_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    recorded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_student_collections_student_org", "student_id", "org_id"),
        Index("ix_student_collections_org", "org_id"),
    )
