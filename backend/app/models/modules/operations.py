"""Operations models (Batch 6, non-financial): Calendar, Facility, Visitor.

Visitor Management is treated as a SAFEGUARDING record, not just an operational
log: visitor + (especially) child-collection records are audited on every
mutation, soft-deleted only (never silently removed), and a collection captures
WHO authorised the pickup.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, DateTime, Date, Integer, Boolean, Numeric, ForeignKey, Index, UniqueConstraint

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
    type = Column(String(40), nullable=True)       # legacy free-text type (kept)
    facility_type_id = Column(String(36), ForeignKey("facility_types.id", ondelete="SET NULL"), nullable=True, index=True)
    quantity = Column(Integer, default=1, nullable=False)   # "Quantities"
    capacity = Column(Integer, nullable=True)
    location = Column(String(200), nullable=True)   # legacy single location (kept; managed locations via tags)
    status = Column(String(20), default="available", nullable=False)  # booking status: available|maintenance|unavailable
    notes = Column(Text, nullable=True)             # "Description"
    is_active = Column(Boolean, default=True, nullable=False)   # "Facility Status" Active/Inactive

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


# ── Facility Management (Educare parity) ─────────────────────────────────────
# Extends the base Facility above with the reference's full structure: managed
# lookups (types/locations/departments), a role-assignment pool, and the
# Complaint → Inspection → Maintenance → Requisition → Disbursement workflow
# chain (each stage FK-links back toward the originating complaint). Audit Trail
# is a filtered view over the GLOBAL AuditLog — no facility audit table here.

class FacilityType(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Lookup: Buildings, Vehicles, Electrical, Furniture, …"""
    __tablename__ = "facility_types"
    name = Column(String(100), nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class FacilityLocation(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Lookup: Reception, Playground, Year 1 Amber, … Tagged onto facilities (M2M).
    Its own list (not SchoolClass) because locations include non-class places."""
    __tablename__ = "facility_locations"
    name = Column(String(150), nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class FacilityLocationTag(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """M2M: which locations a facility is assigned to ("Assigned Locations")."""
    __tablename__ = "facility_location_tags"
    facility_id = Column(String(36), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    location_id = Column(String(36), ForeignKey("facility_locations.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    __table_args__ = (UniqueConstraint("facility_id", "location_id", name="uq_facility_location_tag"),)


class FacilityDepartment(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Lookup: Electrical Works, Plumbing Works, … Officers assigned via FacilityStaff."""
    __tablename__ = "facility_departments"
    name = Column(String(100), nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class FacilityStaff(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A user's facility role assignment — backs Config's Facility Managers /
    Requisition Managers / Store Keepers pools, and department officers."""
    __tablename__ = "facility_staff"
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_type = Column(String(30), nullable=False)   # facility_manager|requisition_manager|store_keeper|officer
    department_id = Column(String(36), ForeignKey("facility_departments.id", ondelete="SET NULL"), nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    __table_args__ = (
        Index("ix_facility_staff_org_role", "org_id", "role_type"),
        UniqueConstraint("user_id", "role_type", "department_id", name="uq_facility_staff"),
    )


class FacilityManagerLink(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """M2M: the facility manager(s) assigned to a specific facility."""
    __tablename__ = "facility_manager_links"
    facility_id = Column(String(36), ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    __table_args__ = (UniqueConstraint("facility_id", "user_id", name="uq_facility_manager_link"),)


class FacilityComplaint(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Start of the workflow: a lodged problem with a facility."""
    __tablename__ = "facility_complaints"
    reference = Column(String(40), nullable=False, index=True)   # auto-generated
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    facility_id = Column(String(36), ForeignKey("facilities.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(20), default="open", nullable=False)  # open|in_progress|resolved|closed
    lodged_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    date_lodged = Column(Date, nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    __table_args__ = (Index("ix_facility_complaints_org_status", "org_id", "status"),)


class FacilityInspection(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """An inspection of a facility, optionally arising from a complaint."""
    __tablename__ = "facility_inspections"
    facility_id = Column(String(36), ForeignKey("facilities.id", ondelete="SET NULL"), nullable=True, index=True)
    inspector_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    complaint_id = Column(String(36), ForeignKey("facility_complaints.id", ondelete="SET NULL"), nullable=True, index=True)
    comment = Column(Text, nullable=True)
    outcome = Column(String(30), nullable=True)      # ok|needs_attention|failed
    inspection_date = Column(Date, nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class FacilityMaintenance(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A maintenance request/record, optionally from a complaint."""
    __tablename__ = "facility_maintenance"
    facility_id = Column(String(36), ForeignKey("facilities.id", ondelete="SET NULL"), nullable=True, index=True)
    complaint_id = Column(String(36), ForeignKey("facility_complaints.id", ondelete="SET NULL"), nullable=True, index=True)
    maintenance_type = Column(String(80), nullable=True)   # repair|preventive|replacement|…
    comment = Column(Text, nullable=True)
    total_cost = Column(Numeric(14, 2), default=0, nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # pending|approved|in_progress|completed|rejected
    requested_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    request_date = Column(Date, nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    __table_args__ = (Index("ix_facility_maintenance_org_status", "org_id", "status"),)


class FacilityApprovalLevel(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A tiered expense-approval level by cost threshold (Config). A requisition
    routes to the level whose threshold its cost falls into."""
    __tablename__ = "facility_approval_levels"
    name = Column(String(120), nullable=False)
    threshold = Column(Numeric(14, 2), default=0, nullable=False)   # min cost for this level
    handler_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    position = Column(Integer, default=0, nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class FacilityRequisition(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A facility spend requisition arising from maintenance, routed through the
    tiered approval levels. Disbursement (money leaving) posts to the GLOBAL
    ledger via the finance ledger service — no parallel cash tracking here."""
    __tablename__ = "facility_requisitions"
    reference = Column(String(40), nullable=False, index=True)   # auto-generated
    title = Column(String(200), nullable=False)
    maintenance_id = Column(String(36), ForeignKey("facility_maintenance.id", ondelete="SET NULL"), nullable=True, index=True)
    maintenance_type = Column(String(80), nullable=True)
    maintenance_cost = Column(Numeric(14, 2), default=0, nullable=False)
    requisition_cost = Column(Numeric(14, 2), default=0, nullable=False)
    status = Column(String(20), default="draft", nullable=False)  # draft|pending|approved|rejected|disbursed
    approval_level_id = Column(String(36), ForeignKey("facility_approval_levels.id", ondelete="SET NULL"), nullable=True)
    total_approved = Column(Numeric(14, 2), default=0, nullable=False)
    approval_date = Column(Date, nullable=True)
    total_disbursed = Column(Numeric(14, 2), default=0, nullable=False)
    # Set when a disbursement posts to the ledger (reuses the finance journal engine).
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    requested_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    approved_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    __table_args__ = (Index("ix_facility_requisitions_org_status", "org_id", "status"),)
