"""Schemas for Pastoral & Boarding (Batch 4): Hostel, Exeat, Mentor Reports.

Medical schemas live in schemas/medical.py (separate confidential surface).
*Create schemas omit org_id (pinned server-side); *Response built by the router
to carry resolved names. Values validated against the allowed sets.
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


HOSTEL_GENDERS = {"boys", "girls", "mixed"}
EXEAT_STATUSES = {"pending", "approved", "rejected", "returned"}


# ── Hostel + Boarding ──────────────────────────────────────────────────────────

class HostelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    gender: Optional[str] = None
    capacity: Optional[int] = Field(default=None, ge=0)
    warden_id: Optional[str] = None
    notes: Optional[str] = None


class HostelUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    gender: Optional[str] = None
    capacity: Optional[int] = Field(default=None, ge=0)
    warden_id: Optional[str] = None
    notes: Optional[str] = None


class HostelResponse(BaseModel):
    id: str
    name: str
    gender: Optional[str]
    capacity: Optional[int]
    warden_id: Optional[str]
    warden_name: Optional[str]
    notes: Optional[str]
    occupancy: int = 0
    created_at: datetime
    org_id: str


class HostelListResponse(BaseModel):
    items: list[HostelResponse]
    total: int
    page: int
    page_size: int


class AllocationCreate(BaseModel):
    student_id: str
    hostel_id: str
    room: Optional[str] = None
    bed: Optional[str] = None
    allocated_on: Optional[date] = None


class AllocationResponse(BaseModel):
    id: str
    student_id: str
    student_name: Optional[str]
    hostel_id: str
    hostel_name: Optional[str]
    room: Optional[str]
    bed: Optional[str]
    allocated_on: Optional[date]
    is_active: bool
    created_at: datetime
    org_id: str


# ── Exeat ──────────────────────────────────────────────────────────────────────

class ExeatCreate(BaseModel):
    student_id: str
    reason: Optional[str] = None
    destination: Optional[str] = None
    depart_at: Optional[datetime] = None
    expected_return_at: Optional[datetime] = None


class ExeatUpdate(BaseModel):
    reason: Optional[str] = None
    destination: Optional[str] = None
    depart_at: Optional[datetime] = None
    expected_return_at: Optional[datetime] = None


class ExeatDecision(BaseModel):
    decision_note: Optional[str] = None


class ExeatResponse(BaseModel):
    id: str
    student_id: str
    student_name: Optional[str]
    reason: Optional[str]
    destination: Optional[str]
    depart_at: Optional[datetime]
    expected_return_at: Optional[datetime]
    actual_return_at: Optional[datetime]
    status: str
    requested_by: Optional[str]
    approved_by: Optional[str]
    approved_by_name: Optional[str]
    decided_at: Optional[datetime]
    decision_note: Optional[str]
    created_at: datetime
    org_id: str


class ExeatListResponse(BaseModel):
    items: list[ExeatResponse]
    total: int
    page: int
    page_size: int


# ── Mentor Reports ─────────────────────────────────────────────────────────────

class MentorReportCreate(BaseModel):
    student_id: str
    term: Optional[str] = None
    period: Optional[str] = None
    summary: Optional[str] = None
    strengths: Optional[str] = None
    concerns: Optional[str] = None
    recommendations: Optional[str] = None


class MentorReportUpdate(BaseModel):
    term: Optional[str] = None
    period: Optional[str] = None
    summary: Optional[str] = None
    strengths: Optional[str] = None
    concerns: Optional[str] = None
    recommendations: Optional[str] = None


class MentorReportResponse(BaseModel):
    id: str
    student_id: str
    student_name: Optional[str]
    mentor_id: Optional[str]
    mentor_name: Optional[str]
    term: Optional[str]
    period: Optional[str]
    summary: Optional[str]
    strengths: Optional[str]
    concerns: Optional[str]
    recommendations: Optional[str]
    created_at: datetime
    org_id: str


class MentorReportListResponse(BaseModel):
    items: list[MentorReportResponse]
    total: int
    page: int
    page_size: int
