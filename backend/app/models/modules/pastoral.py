"""Pastoral, Boarding & Health models (Batch 4).

  • Hostel + BoardingAllocation — boarding houses and per-student bed allocation.
  • ExeatRequest — a boarder's request to leave campus; approval is a
    safety-sensitive action, so it carries explicit approver + decision fields.
  • MentorReport — a mentor's pastoral report on a mentee.
  • MedicalRecord — CONFIDENTIAL student health data, on its own ``medical:*``
    permission namespace (see role.py / workspace.py), never the broad school net.

All tenant-scoped; status/type stored as validated strings.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, Date, DateTime, Integer, Boolean, ForeignKey, Index

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


class Hostel(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A boarding house."""
    __tablename__ = "hostels"

    name = Column(String(120), nullable=False)
    gender = Column(String(20), nullable=True)        # boys | girls | mixed
    capacity = Column(Integer, nullable=True)
    warden_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_hostels_org", "org_id"),
    )


class BoardingAllocation(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A student's bed allocation in a hostel."""
    __tablename__ = "boarding_allocations"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    hostel_id = Column(String(36), ForeignKey("hostels.id", ondelete="CASCADE"), nullable=False, index=True)
    room = Column(String(40), nullable=True)
    bed = Column(String(40), nullable=True)
    allocated_on = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    allocated_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_boarding_alloc_hostel_org", "hostel_id", "org_id"),
        Index("ix_boarding_alloc_student_org", "student_id", "org_id"),
    )


class ExeatRequest(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A boarder's request to leave campus. Authorising it is safety-sensitive,
    so the approver, decision time, and note are recorded explicitly (and audited
    at the router)."""
    __tablename__ = "exeat_requests"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    reason = Column(Text, nullable=True)
    destination = Column(String(200), nullable=True)
    depart_at = Column(DateTime(timezone=True), nullable=True)
    expected_return_at = Column(DateTime(timezone=True), nullable=True)
    actual_return_at = Column(DateTime(timezone=True), nullable=True)
    # pending | approved | rejected | returned
    status = Column(String(20), default="pending", nullable=False)
    requested_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decision_note = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_exeat_org_status", "org_id", "status"),
        Index("ix_exeat_student_org", "student_id", "org_id"),
    )


class MentorReport(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A mentor's pastoral report on a mentee."""
    __tablename__ = "mentor_reports"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    mentor_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    term = Column(String(40), nullable=True)
    period = Column(String(60), nullable=True)
    summary = Column(Text, nullable=True)
    strengths = Column(Text, nullable=True)
    concerns = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_mentor_reports_student_org", "student_id", "org_id"),
    )


class StudentMedicalRecord(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """CONFIDENTIAL student health record. Gated by the ``medical:*`` namespace —
    never the broad school read. Soft-deleted to preserve the health history.

    Named ``StudentMedicalRecord`` (table ``student_medical_records``) to avoid
    colliding with the retained hospital-EMR ``MedicalRecord`` model.
    """
    __tablename__ = "student_medical_records"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    # visit | allergy | medication | immunization | condition | note
    record_type = Column(String(20), default="visit", nullable=False)
    title = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    treatment = Column(Text, nullable=True)
    severity = Column(String(20), nullable=True)       # low | medium | high
    recorded_on = Column(Date, nullable=True)
    follow_up_on = Column(Date, nullable=True)
    recorded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_student_medical_records_student_org", "student_id", "org_id"),
        Index("ix_student_medical_records_org_type", "org_id", "record_type"),
    )


class PastoralSettings(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Per-org Pastoral configuration — the flag groups behind Pastoral Setup →
    Exeat Settings + Default Settings. One row per org (upserted). Mirrors the
    BehaviourSettings / ClubSettings pattern."""
    __tablename__ = "pastoral_settings"

    # ── Exeat Settings ────────────────────────────────────────────────────────
    enable_head_only_approval = Column(Boolean, default=False, nullable=False)
    notify_parent_on_exeat_approval = Column(Boolean, default=True, nullable=False)
    notify_house_parent_on_exeat_approval = Column(Boolean, default=False, nullable=False)
    notify_pastoral_head_on_new_request = Column(Boolean, default=True, nullable=False)

    # ── Default Settings ──────────────────────────────────────────────────────
    enable_tutorial_week = Column(Boolean, default=False, nullable=False)
    email_parent_on_new_point_entry = Column(Boolean, default=False, nullable=False)
    enable_academic_cohesion = Column(Boolean, default=False, nullable=False)
    show_award_in_point_analysis = Column(Boolean, default=False, nullable=False)
    allow_referral_in_mentor_comment = Column(Boolean, default=True, nullable=False)
    enable_point_category = Column(Boolean, default=False, nullable=False)
    enable_mentor_report_assessment = Column(Boolean, default=False, nullable=False)
    allow_only_merits_in_point_entry = Column(Boolean, default=False, nullable=False)
    allow_observation_in_mentor_comment = Column(Boolean, default=True, nullable=False)
    # "School Nurse Role" — points at an existing RBAC role (never a new one).
    school_nurse_role_id = Column(String(36), ForeignKey("roles.id", ondelete="SET NULL"), nullable=True)

    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, unique=True, index=True)
