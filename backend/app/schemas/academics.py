"""Schemas for Academic Records & Recognition (Batch 3).

*Create schemas omit org_id (pinned server-side). *Response schemas are built by
the router so they can carry resolved display names. Status/stage/type values
are validated against the allowed sets here + in the router.
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


SELECTION_STATUSES = {"requested", "approved", "rejected"}
TRANSCRIPT_STATUSES = {"draft", "issued"}
REPORT_STAGES = ["draft", "submitted", "reviewed", "approved", "published"]
RECOGNITION_TYPES = {"conduct_point", "academic_award"}
AWARD_TYPES = {"honor_roll", "prize", "certificate"}


# ── Subject Selection ──────────────────────────────────────────────────────────

class SubjectSelectionCreate(BaseModel):
    student_id: str
    subject_id: str
    academic_year: Optional[str] = None
    term: Optional[str] = None
    status: str = "requested"


class SubjectSelectionUpdate(BaseModel):
    status: Optional[str] = None
    term: Optional[str] = None
    academic_year: Optional[str] = None


class SubjectSelectionResponse(BaseModel):
    id: str
    student_id: str
    student_name: Optional[str]
    subject_id: str
    subject_name: Optional[str]
    academic_year: Optional[str]
    term: Optional[str]
    status: str
    created_at: datetime
    org_id: str


class SubjectSelectionListResponse(BaseModel):
    items: list[SubjectSelectionResponse]
    total: int
    page: int
    page_size: int


# ── Transcripts ────────────────────────────────────────────────────────────────

class TranscriptEntryCreate(BaseModel):
    subject_name: str = Field(min_length=1, max_length=150)
    score: Optional[float] = None
    grade: Optional[str] = None
    remark: Optional[str] = None


class TranscriptEntryResponse(BaseModel):
    id: str
    subject_name: str
    score: Optional[float]
    grade: Optional[str]
    remark: Optional[str]


class TranscriptCreate(BaseModel):
    student_id: str
    academic_year: Optional[str] = None
    term: Optional[str] = None
    remark: Optional[str] = None
    entries: list[TranscriptEntryCreate] = Field(default_factory=list)


class TranscriptUpdate(BaseModel):
    academic_year: Optional[str] = None
    term: Optional[str] = None
    remark: Optional[str] = None
    status: Optional[str] = None


class TranscriptResponse(BaseModel):
    id: str
    student_id: str
    student_name: Optional[str]
    academic_year: Optional[str]
    term: Optional[str]
    average: Optional[float]
    remark: Optional[str]
    status: str
    entries: list[TranscriptEntryResponse]
    created_at: datetime
    org_id: str


class TranscriptListResponse(BaseModel):
    items: list[TranscriptResponse]
    total: int
    page: int
    page_size: int


# ── Report Workflow ────────────────────────────────────────────────────────────

class ReportApprovalCreate(BaseModel):
    class_id: Optional[str] = None
    academic_year: Optional[str] = None
    term: Optional[str] = None
    notes: Optional[str] = None


class ReportApprovalUpdate(BaseModel):
    stage: Optional[str] = None
    notes: Optional[str] = None


class ReportApprovalResponse(BaseModel):
    id: str
    class_id: Optional[str]
    class_name: Optional[str]
    academic_year: Optional[str]
    term: Optional[str]
    stage: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    org_id: str


class ReportApprovalListResponse(BaseModel):
    items: list[ReportApprovalResponse]
    total: int
    page: int
    page_size: int


# ── Merit & Awards (one typed model) ───────────────────────────────────────────

class RecognitionCreate(BaseModel):
    type: str  # conduct_point | academic_award
    student_id: str
    title: Optional[str] = None
    reason: Optional[str] = None
    points: Optional[int] = None
    house: Optional[str] = None
    category: Optional[str] = None
    award_type: Optional[str] = None
    term: Optional[str] = None
    awarded_on: Optional[date] = None


class RecognitionUpdate(BaseModel):
    title: Optional[str] = None
    reason: Optional[str] = None
    points: Optional[int] = None
    house: Optional[str] = None
    category: Optional[str] = None
    award_type: Optional[str] = None
    term: Optional[str] = None
    awarded_on: Optional[date] = None


class RecognitionResponse(BaseModel):
    id: str
    type: str
    student_id: str
    student_name: Optional[str]
    title: Optional[str]
    reason: Optional[str]
    points: Optional[int]
    house: Optional[str]
    category: Optional[str]
    award_type: Optional[str]
    term: Optional[str]
    awarded_on: Optional[date]
    created_at: datetime
    org_id: str


class RecognitionListResponse(BaseModel):
    items: list[RecognitionResponse]
    total: int
    page: int
    page_size: int


class HouseLeaderboardRow(BaseModel):
    house: str
    total_points: int
    entries: int


class LeaderboardResponse(BaseModel):
    houses: list[HouseLeaderboardRow]
