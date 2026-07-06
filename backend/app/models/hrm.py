"""HRM data models.

Two tables here:

* ``HRProfile`` — extends ``User`` 1:1 with structured HR fields (the bits
  that don't belong on an auth/identity row). Keeps identity columns on
  ``User`` (email, full_name, phone, department, job_title) and pushes
  HR-only data (marital status, DOB, salary, emergency contact, etc.)
  into its own table. This avoids bloating ``User`` and lets us extend
  the HR side without touching the auth flow.

* ``Event`` — org-wide calendar events shown in the HR dashboard's
  "Upcoming Events" section. Intentionally minimal; school timetable
  lessons are a separate surface that already exists as ``Timetable``.

Both models are tenant-scoped (``org_id``) and the HR router pins
``org_id == current_user.org_id`` on every query.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Date, DateTime, Text, Float, Integer, ForeignKey, JSON, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


class HRProfile(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """One row per employee, keyed by ``user_id``.

    Created lazily on first ``GET /hr/me`` — we don't seed one per user
    up front so existing orgs aren't forced to migrate data before the
    UI is used.
    """
    __tablename__ = "hr_profiles"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # 1. Personal details
    title = Column(String(20), nullable=True)           # Mr / Mrs / Dr / …
    first_name = Column(String(100), nullable=True)     # may differ from User.full_name split
    middle_name = Column(String(100), nullable=True)
    surname = Column(String(100), nullable=True)
    staff_id = Column(String(50), nullable=True, index=True)
    employment_status = Column(String(40), nullable=True)  # active / probation / contract / terminated
    gender = Column(String(20), nullable=True)
    marital_status = Column(String(30), nullable=True)
    nationality = Column(String(80), nullable=True)
    date_of_birth = Column(Date, nullable=True, index=True)  # indexed for birthdays query

    # 2. Identification
    national_id = Column(String(80), nullable=True)
    national_id_expiry = Column(Date, nullable=True)

    # 3. Contact
    address = Column(Text, nullable=True)
    emergency_contact_name = Column(String(150), nullable=True)
    emergency_contact_phone = Column(String(50), nullable=True)
    emergency_contact_relationship = Column(String(50), nullable=True)

    # 4. Employment details
    # department + job_title live on User already; avoid duplicating.
    hire_date = Column(Date, nullable=True)

    # 5. Salary & pension — nullable; masked in responses based on viewer perm.
    salary = Column(Float, nullable=True)
    salary_currency = Column(String(10), nullable=True, default="NGN")
    bank_name = Column(String(120), nullable=True)
    bank_account_name = Column(String(150), nullable=True)
    bank_account_number = Column(String(40), nullable=True)
    pension_provider = Column(String(120), nullable=True)
    pension_id = Column(String(80), nullable=True)

    # 6. Memberships — list of {body, membership_number, expires_at} dicts.
    memberships = Column(JSON, default=list)

    # 7. Family — next_of_kin: {name, relationship, phone, email}. dependents: list.
    next_of_kin = Column(JSON, default=dict)
    dependents = Column(JSON, default=list)

    user = relationship("User", foreign_keys=[user_id], lazy="joined")

    __table_args__ = (
        # One HR profile per user per org. FK already guarantees one user →
        # but the unique constraint makes the invariant explicit.
        UniqueConstraint("user_id", name="uq_hr_profiles_user_id"),
        # Birthday lookups filter by org + month(date_of_birth); the plain
        # index on date_of_birth + org_id scan is enough at current scale.
        Index("ix_hr_profiles_org_dob", "org_id", "date_of_birth"),
    )


class Event(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Org calendar event. Shown in the HR dashboard's Upcoming section."""
    __tablename__ = "hr_events"

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    starts_at = Column(DateTime(timezone=True), nullable=False, index=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    location = Column(String(200), nullable=True)
    category = Column(String(40), nullable=True)  # free-form: meeting / training / holiday / …
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        # "Upcoming events for this org" is a range scan on starts_at scoped by org.
        Index("ix_hr_events_org_starts", "org_id", "starts_at"),
    )


class StaffAssessment(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A performance appraisal of a staff member by a reviewer.

    Confidential HR record — gated by ``hr:write`` (org_admin / manager only),
    so teachers (who hold ``hr:read`` for self-service) never see appraisals.
    ``overall_rating`` is a 1–5 scale; the descriptive fields capture the
    review narrative. ``status`` drives the draft → finalised workflow.
    """
    __tablename__ = "staff_assessments"

    staff_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    period = Column(String(60), nullable=False)         # e.g. "2025/2026 Term 1"
    review_date = Column(Date, nullable=True)
    overall_rating = Column(Integer, nullable=True)     # 1–5
    strengths = Column(Text, nullable=True)
    improvements = Column(Text, nullable=True)
    goals = Column(Text, nullable=True)
    status = Column(String(20), default="draft", nullable=False)  # draft | finalized

    staff = relationship("User", foreign_keys=[staff_user_id], lazy="joined")
    reviewer = relationship("User", foreign_keys=[reviewer_id], lazy="joined")

    __table_args__ = (
        # "Appraisals for this staff member" — the staff-detail hot path.
        Index("ix_staff_assessments_staff_org", "staff_user_id", "org_id"),
    )


class TalentCandidate(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A recruitment-pipeline candidate (talent pool).

    Confidential HR record — gated by ``hr:write``. ``stage`` tracks the hiring
    funnel; ``rating`` (1–5) is an optional shortlisting score.
    """
    __tablename__ = "talent_candidates"

    full_name = Column(String(200), nullable=False)
    email = Column(String(320), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    role_applied = Column(String(150), nullable=True)   # e.g. "Mathematics Teacher"
    source = Column(String(80), nullable=True)          # referral / job board / walk-in …
    stage = Column(String(20), default="applied", nullable=False)  # applied|screening|interview|offer|hired|rejected
    rating = Column(Integer, nullable=True)             # 1–5 shortlist score
    notes = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        # Kanban/board view filters by stage within an org.
        Index("ix_talent_candidates_org_stage", "org_id", "stage"),
    )
