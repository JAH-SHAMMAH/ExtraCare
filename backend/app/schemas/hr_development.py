"""Schemas for HR Development (Batch 1): Staff Assessment + Talent Pool.

Both are confidential HR records gated by ``hr:write`` (org_admin / manager).
*Create schemas omit org_id (pinned server-side). Ratings are validated to the
1–5 scale. *Response schemas embed resolved names so the table renders directly.
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Staff Assessment ─────────────────────────────────────────────────────────

_ASSESSMENT_STATUSES = {"draft", "finalized"}


class StaffAssessmentCreate(BaseModel):
    staff_user_id: str
    period: str = Field(min_length=1, max_length=60)
    review_date: Optional[date] = None
    overall_rating: Optional[int] = Field(default=None, ge=1, le=5)
    strengths: Optional[str] = None
    improvements: Optional[str] = None
    goals: Optional[str] = None
    status: str = "draft"


class StaffAssessmentUpdate(BaseModel):
    period: Optional[str] = Field(default=None, min_length=1, max_length=60)
    review_date: Optional[date] = None
    overall_rating: Optional[int] = Field(default=None, ge=1, le=5)
    strengths: Optional[str] = None
    improvements: Optional[str] = None
    goals: Optional[str] = None
    status: Optional[str] = None


class StaffAssessmentResponse(_OrmBase):
    id: str
    staff_user_id: str
    staff_name: Optional[str] = None
    reviewer_id: Optional[str] = None
    reviewer_name: Optional[str] = None
    period: str
    review_date: Optional[date]
    overall_rating: Optional[int]
    strengths: Optional[str]
    improvements: Optional[str]
    goals: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    org_id: str


class StaffAssessmentListResponse(BaseModel):
    items: list[StaffAssessmentResponse]
    total: int
    page: int
    page_size: int


# ── Talent Pool ──────────────────────────────────────────────────────────────

_TALENT_STAGES = {"applied", "screening", "interview", "offer", "hired", "rejected"}


class TalentCandidateCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: Optional[str] = None
    phone: Optional[str] = None
    role_applied: Optional[str] = None
    source: Optional[str] = None
    stage: str = "applied"
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    notes: Optional[str] = None


class TalentCandidateUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    email: Optional[str] = None
    phone: Optional[str] = None
    role_applied: Optional[str] = None
    source: Optional[str] = None
    stage: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    notes: Optional[str] = None


class TalentCandidateResponse(_OrmBase):
    id: str
    full_name: str
    email: Optional[str]
    phone: Optional[str]
    role_applied: Optional[str]
    source: Optional[str]
    stage: str
    rating: Optional[int]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    org_id: str


class TalentCandidateListResponse(BaseModel):
    items: list[TalentCandidateResponse]
    total: int
    page: int
    page_size: int
