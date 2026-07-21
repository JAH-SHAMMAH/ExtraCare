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


# ── Assessment criteria / rubric ("Setup Staff Assessment") ──────────────────

class CriterionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: Optional[str] = None
    category: Optional[str] = None
    competency: Optional[str] = Field(default=None, max_length=150)
    weight: int = Field(default=1, ge=1)
    max_score: int = Field(default=5, ge=1, le=100)
    position: int = 0
    is_active: bool = True


class CriterionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    description: Optional[str] = None
    category: Optional[str] = None
    competency: Optional[str] = Field(default=None, max_length=150)
    weight: Optional[int] = Field(default=None, ge=1)
    max_score: Optional[int] = Field(default=None, ge=1, le=100)
    position: Optional[int] = None
    is_active: Optional[bool] = None


class CriterionResponse(_OrmBase):
    id: str
    name: str
    description: Optional[str]
    category: Optional[str]
    competency: Optional[str] = None
    weight: int
    max_score: int
    position: int
    is_active: bool
    org_id: str
    created_at: datetime


class CriterionListResponse(BaseModel):
    items: list[CriterionResponse]


class ScoreInput(BaseModel):
    criterion_id: str
    score: int = Field(ge=0)
    comment: Optional[str] = None


class ScoreResponse(BaseModel):
    criterion_id: str
    criterion_name: Optional[str] = None
    category: Optional[str] = None
    score: int
    max_score: Optional[int] = None
    weight: Optional[int] = None
    comment: Optional[str] = None


class StaffAssessmentCreate(BaseModel):
    staff_user_id: str
    period: str = Field(min_length=1, max_length=60)
    review_date: Optional[date] = None
    overall_rating: Optional[int] = Field(default=None, ge=1, le=5)
    strengths: Optional[str] = None
    improvements: Optional[str] = None
    goals: Optional[str] = None
    status: str = "draft"
    # When provided, per-criterion scores drive overall_rating (weighted average).
    scores: Optional[list[ScoreInput]] = None


class StaffAssessmentUpdate(BaseModel):
    period: Optional[str] = Field(default=None, min_length=1, max_length=60)
    review_date: Optional[date] = None
    overall_rating: Optional[int] = Field(default=None, ge=1, le=5)
    strengths: Optional[str] = None
    improvements: Optional[str] = None
    goals: Optional[str] = None
    status: Optional[str] = None
    scores: Optional[list[ScoreInput]] = None


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
    scores: list[ScoreResponse] = []
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
