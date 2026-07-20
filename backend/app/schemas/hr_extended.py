"""Schemas for Recruitment + Disciplinary (Phase 4 Batch 1)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


# ── Recruitment: Job openings ─────────────────────────────────────────────────────

class JobOpeningCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    department: Optional[str] = None
    description: Optional[str] = None
    employment_type: Optional[str] = None
    positions: int = 1
    posted_on: Optional[date] = None
    closes_on: Optional[date] = None


class JobOpeningUpdate(BaseModel):
    title: Optional[str] = None
    department: Optional[str] = None
    description: Optional[str] = None
    employment_type: Optional[str] = None
    positions: Optional[int] = None
    status: Optional[str] = None
    closes_on: Optional[date] = None


class JobOpeningResponse(BaseModel):
    id: str
    title: str
    department: Optional[str]
    description: Optional[str]
    employment_type: Optional[str]
    positions: int
    status: str
    posted_on: Optional[date]
    closes_on: Optional[date]
    applicant_count: int = 0
    created_at: datetime
    org_id: str


# ── Recruitment: Applicants ───────────────────────────────────────────────────────

class ApplicantCreate(BaseModel):
    job_id: str
    name: str = Field(min_length=1, max_length=150)
    email: Optional[str] = None
    phone: Optional[str] = None
    stage: str = "applied"
    rating: Optional[int] = None
    resume_url: Optional[str] = None
    notes: Optional[str] = None
    applied_on: Optional[date] = None


class ApplicantUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    stage: Optional[str] = None
    rating: Optional[int] = None
    resume_url: Optional[str] = None
    notes: Optional[str] = None


class ApplicantResponse(BaseModel):
    id: str
    job_id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    stage: str
    rating: Optional[int]
    resume_url: Optional[str]
    notes: Optional[str]
    applied_on: Optional[date]
    created_at: datetime
    org_id: str


# ── Disciplinary ──────────────────────────────────────────────────────────────────

class DisciplinaryCreate(BaseModel):
    staff_user_id: str
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    severity: str = "minor"
    incident_on: Optional[date] = None


class DisciplinaryUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    action_taken: Optional[str] = None
    resolved_on: Optional[date] = None


class DisciplinaryResponse(BaseModel):
    id: str
    staff_user_id: str
    staff_name: Optional[str]
    title: str
    description: Optional[str]
    severity: str
    status: str
    action_taken: Optional[str]
    reported_by: Optional[str]
    incident_on: Optional[date]
    resolved_on: Optional[date]
    created_at: datetime
    org_id: str


class MyDisciplinaryResponse(BaseModel):
    """Self-service view of one's OWN disciplinary record (Discipline › My Actions).
    Deliberately omits reported_by — a staff member sees the action taken against
    them, not who reported it."""
    id: str
    title: str
    description: Optional[str]
    severity: str
    status: str
    action_taken: Optional[str]
    incident_on: Optional[date]
    resolved_on: Optional[date]
    created_at: datetime


class HrExtendedStats(BaseModel):
    open_jobs: int
    total_applicants: int
    open_disciplinary: int


# ── Staff Appointments (Appointment Manager) ──────────────────────────────────────

APPOINTMENT_TYPES = {"appointment", "promotion", "salary_review", "contract_renewal", "transfer", "termination"}


class AppointmentCreate(BaseModel):
    staff_user_id: str
    appointment_type: str = "appointment"
    title: str = Field(min_length=1, max_length=200)
    grade: Optional[str] = None
    salary: Optional[Decimal] = None
    salary_currency: str = "NGN"
    effective_date: Optional[date] = None
    end_date: Optional[date] = None
    reference: Optional[str] = None
    notes: Optional[str] = None


class AppointmentUpdate(BaseModel):
    appointment_type: Optional[str] = None
    title: Optional[str] = None
    grade: Optional[str] = None
    salary: Optional[Decimal] = None
    salary_currency: Optional[str] = None
    effective_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None            # active | ended
    reference: Optional[str] = None
    notes: Optional[str] = None


class AppointmentResponse(BaseModel):
    id: str
    staff_user_id: str
    staff_name: Optional[str]
    appointment_type: str
    title: str
    grade: Optional[str]
    salary: Optional[float]
    salary_currency: Optional[str]
    effective_date: Optional[date]
    end_date: Optional[date]
    status: str
    reference: Optional[str]
    notes: Optional[str]
    created_by: Optional[str]
    created_at: datetime
    org_id: str
