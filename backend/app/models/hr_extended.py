"""Deeper HR models (Phase 4) — Recruitment (job openings + applicants) and
Disciplinary cases. Confidential HR admin, gated ``hr:write`` at the router."""
from __future__ import annotations

from sqlalchemy import Column, String, Text, Integer, Numeric, Date, DateTime, ForeignKey, Index

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


class JobOpening(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A recruitment vacancy. ``status='open'`` feeds the HR 'Jobs Opening' card."""
    __tablename__ = "job_openings"

    title = Column(String(200), nullable=False)
    department = Column(String(120), nullable=True)
    description = Column(Text, nullable=True)
    employment_type = Column(String(40), nullable=True)   # full_time | part_time | contract
    positions = Column(Integer, default=1, nullable=False)
    status = Column(String(20), default="open", nullable=False)  # open | closed
    posted_on = Column(Date, nullable=True)
    closes_on = Column(Date, nullable=True)

    __table_args__ = (Index("ix_job_openings_org_status", "org_id", "status"),)


class Applicant(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A candidate against a JobOpening, moving through a pipeline stage."""
    __tablename__ = "job_applicants"

    job_id = Column(String(36), ForeignKey("job_openings.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    # applied → screening → interview → offer → hired | rejected
    stage = Column(String(20), default="applied", nullable=False)
    rating = Column(Integer, nullable=True)               # 1–5 (optional)
    resume_url = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    applied_on = Column(Date, nullable=True)

    __table_args__ = (Index("ix_job_applicants_job_stage", "job_id", "stage"),)


class DisciplinaryCase(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A staff disciplinary record. ``status in (open, under_review)`` feeds the
    HR 'Disciplinary Cases' card. Confidential."""
    __tablename__ = "disciplinary_cases"

    staff_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(20), default="minor", nullable=False)   # minor | major | gross
    status = Column(String(20), default="open", nullable=False)      # open | under_review | resolved | dismissed
    action_taken = Column(Text, nullable=True)
    reported_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    incident_on = Column(Date, nullable=True)
    resolved_on = Column(Date, nullable=True)

    __table_args__ = (Index("ix_disciplinary_org_status", "org_id", "status"),)


class StaffAppointment(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A staff appointment / contract event — the employment history that
    complements the one-row-per-employee HRProfile. Each row is an event
    (initial appointment, promotion, salary review, contract renewal, transfer,
    termination) with a grade, salary and effective date. Confidential (salary
    data): gated ``hr:write`` like the rest of this router. It records history;
    it does NOT auto-feed payroll (that is a deliberate future integration)."""
    __tablename__ = "staff_appointments"

    staff_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_type = Column(String(30), default="appointment", nullable=False)  # appointment|promotion|salary_review|contract_renewal|transfer|termination
    title = Column(String(200), nullable=False)              # position / job title
    grade = Column(String(60), nullable=True)                # salary grade (e.g. "Grade 8", "TS3")
    salary = Column(Numeric(14, 2), nullable=True)           # salary for this appointment
    salary_currency = Column(String(10), default="NGN", nullable=True)
    effective_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)                   # for contracts / termination
    status = Column(String(20), default="active", nullable=False)  # active | ended
    reference = Column(String(120), nullable=True)           # appointment-letter reference
    notes = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (Index("ix_staff_appointments_org_staff", "org_id", "staff_user_id"),)
