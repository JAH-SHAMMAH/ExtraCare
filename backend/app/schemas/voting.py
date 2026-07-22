"""Schemas for the Voting System module."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Periods (Rating Setup) ────────────────────────────────────────────────────

class PeriodCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    section_id: Optional[str] = None


class PeriodExtend(BaseModel):
    ends_at: datetime


class PeriodResponse(BaseModel):
    id: str
    name: str
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    status: str
    section_id: Optional[str]
    section_name: Optional[str] = None
    created_at: datetime
    org_id: str


# ── Categories (Voting Setup) ─────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    section_id: Optional[str] = None
    is_active: bool = True


class CategoryUpdate(BaseModel):
    description: Optional[str] = Field(default=None, min_length=1, max_length=300)
    section_id: Optional[str] = None
    is_active: Optional[bool] = None


class CategoryResponse(BaseModel):
    id: str
    description: str
    section_id: Optional[str]
    section_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    org_id: str


# ── Sessions (Manage Votes) ───────────────────────────────────────────────────

class SessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    instructions: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    session_id: Optional[str] = None
    section_id: Optional[str] = None
    positions: int = Field(default=1, ge=1, le=50)
    candidate_role: Optional[str] = None
    voter_role: Optional[str] = None
    category_ids: list[str] = []


class SessionUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=250)
    instructions: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    session_id: Optional[str] = None
    section_id: Optional[str] = None
    positions: Optional[int] = Field(default=None, ge=1, le=50)
    candidate_role: Optional[str] = None
    voter_role: Optional[str] = None
    category_ids: Optional[list[str]] = None


class SessionResponse(BaseModel):
    id: str
    title: str
    instructions: Optional[str]
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    session_id: Optional[str]
    section_id: Optional[str]
    positions: int
    candidate_role: Optional[str]
    voter_role: Optional[str]
    status: str
    result_published: bool
    category_ids: list[str] = []
    candidate_count: int = 0
    total_ballots: int = 0
    created_at: datetime
    org_id: str


# ── Candidates ────────────────────────────────────────────────────────────────

class CandidateCreate(BaseModel):
    category_id: str
    user_id: str


class CandidateResponse(BaseModel):
    id: str
    session_id: str
    category_id: str
    user_id: str
    name: Optional[str] = None
    votes: int = 0                       # populated on results


# ── Ballots (My Votes) ────────────────────────────────────────────────────────

class BallotCreate(BaseModel):
    category_id: str
    candidate_id: str


# ── Results ───────────────────────────────────────────────────────────────────

class CategoryResult(BaseModel):
    category_id: str
    category_description: Optional[str]
    total_votes: int
    candidates: list[CandidateResponse]     # sorted desc by votes
    winner_ids: list[str]                    # top `positions`


class SessionResults(BaseModel):
    session_id: str
    title: str
    status: str
    result_published: bool
    positions: int
    categories: list[CategoryResult]


# ── Voter ballot view (My Votes) ──────────────────────────────────────────────

class BallotCandidate(BaseModel):
    id: str
    name: Optional[str]


class BallotCategory(BaseModel):
    category_id: str
    description: Optional[str]
    candidates: list[BallotCandidate]


class BallotView(BaseModel):
    session_id: str
    title: str
    instructions: Optional[str]
    categories: list[BallotCategory]
    my_votes: dict[str, str] = {}          # category_id → candidate_id already chosen
