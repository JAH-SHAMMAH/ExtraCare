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
# Position in REPORT_STAGES is load-bearing, not decorative: a report advances
# ONE stage at a time (so "approved" can't be skipped on the way to "published"),
# but may be sent back any distance in a single move — a reviewer rejecting a
# submission drops it straight to "draft" without walking down the ladder.
REPORT_STAGE_ORDER = {name: i for i, name in enumerate(REPORT_STAGES)}
# Stages that permit POST /school/grades/publish for the class + term. "published"
# is included so re-publishing after a retraction doesn't need a stage round-trip.
REPORT_PUBLISHABLE_STAGES = ("approved", "published")
# The stage the parent-facing report card requires. Narrower than the publish
# gate on purpose: approving readies a report, publishing releases it.
REPORT_RELEASED_STAGE = "published"
RECOGNITION_TYPES = {"conduct_point", "academic_award"}
AWARD_TYPES = {"honor_roll", "prize", "certificate"}


def stage_transition_error(current: str, target: str) -> Optional[str]:
    """Why ``current`` -> ``target`` is illegal, or None when the move is allowed.

    Forward one step, backward freely, and a no-op re-set of the same stage is
    tolerated (an idempotent PATCH shouldn't 422). A row holding a stage outside
    REPORT_STAGES — only reachable from data written before this rule existed —
    is never trapped: any valid target gets it back on the ladder.
    """
    if target not in REPORT_STAGE_ORDER:
        return f"stage must be one of {REPORT_STAGES}"
    if current not in REPORT_STAGE_ORDER:
        return None
    cur, nxt = REPORT_STAGE_ORDER[current], REPORT_STAGE_ORDER[target]
    if nxt > cur + 1:
        return (
            f"cannot jump from '{current}' to '{target}' — a report advances one stage "
            f"at a time (next is '{REPORT_STAGES[cur + 1]}')."
        )
    return None


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
    published_by: Optional[str] = None
    published_at: Optional[datetime] = None
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
