"""Schemas for Administration & Platform (Batch 7)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Biometric ───────────────────────────────────────────────────────────────────

class DeviceCreate(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=150)
    location: Optional[str] = None
    notes: Optional[str] = None


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class DeviceResponse(BaseModel):
    id: str
    device_id: str
    name: str
    location: Optional[str]
    is_active: bool
    last_seen_at: Optional[datetime]
    clock_skew_seconds: Optional[int]
    notes: Optional[str]
    created_at: datetime
    org_id: str
    # Ingest-token status (never the token itself).
    has_token: bool = False
    token_prefix: Optional[str] = None
    token_issued_at: Optional[datetime] = None


class DeviceTokenResponse(BaseModel):
    """Returned ONCE when a device ingest token is issued or rotated. The
    plaintext ``token`` is not stored and cannot be retrieved again."""
    device_pk: str
    device_id: str
    token: str
    token_prefix: str
    token_issued_at: datetime


class EnrollmentCreate(BaseModel):
    biometric_user_id: str = Field(min_length=1, max_length=128)
    student_id: str
    label: Optional[str] = None


class EnrollmentResponse(BaseModel):
    id: str
    biometric_user_id: str
    student_id: str
    student_name: Optional[str]
    label: Optional[str]
    created_at: datetime
    org_id: str


class PunchIn(BaseModel):
    """One device punch. ``record_id`` is the device's own transaction id — the
    AUTHORITATIVE dedup key (not the timestamp). ``event_time`` is the device
    clock (authoritative for the punch time)."""
    device_id: str
    biometric_user_id: str
    event_time: Optional[datetime] = None
    direction: str = "check_in"            # check_in | check_out
    record_id: Optional[str] = None        # device transaction id → external_ref
    raw: Optional[dict[str, Any]] = None


class IngestPunchesRequest(BaseModel):
    punches: list[PunchIn] = Field(min_length=1)


class IngestSummary(BaseModel):
    ingested: int
    duplicates: int
    quarantined: int


class UnmappedPunchResponse(BaseModel):
    id: str
    device_id: Optional[str]
    biometric_user_id: Optional[str]
    event_time: Optional[datetime]
    direction: Optional[str]
    reason: str
    status: str
    created_at: datetime
    org_id: str


class ResolvePunchRequest(BaseModel):
    student_id: str
    enroll: bool = True            # also create a BiometricEnrollment for future punches


# ── School Setup ────────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    term: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: bool = False


class SessionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    term: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = None


class SessionResponse(BaseModel):
    id: str
    name: str
    term: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    is_current: bool
    created_at: datetime
    org_id: str


class CurrentSessionResponse(BaseModel):
    """The org's current session resolved for consumers (readable at school:read).
    All null when no session is marked current."""
    session: Optional[SessionResponse] = None
    term: Optional[str] = None
    name: Optional[str] = None


# ── Academic Weeks (calendar backbone) ────────────────────────────────────────

class WeekCreate(BaseModel):
    academic_year: str = Field(min_length=1, max_length=20)
    term: str = Field(min_length=1, max_length=40)
    week_number: int = Field(ge=1, le=60)
    start_date: date
    end_date: date
    label: Optional[str] = Field(default=None, max_length=120)
    is_holiday: bool = False


class WeekUpdate(BaseModel):
    week_number: Optional[int] = Field(default=None, ge=1, le=60)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    label: Optional[str] = Field(default=None, max_length=120)
    is_holiday: Optional[bool] = None
    is_locked: Optional[bool] = None


class WeekGenerate(BaseModel):
    """Auto-fill sequential 7-day weeks across a term's date range."""
    academic_year: str = Field(min_length=1, max_length=20)
    term: str = Field(min_length=1, max_length=40)
    start_date: date
    end_date: date


class WeekResponse(BaseModel):
    id: str
    academic_year: str
    term: str
    week_number: int
    start_date: date
    end_date: date
    label: Optional[str]
    is_holiday: bool
    is_locked: bool
    created_at: datetime
    org_id: str


class HouseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: Optional[str] = None
    motto: Optional[str] = None


class HouseResponse(BaseModel):
    id: str
    name: str
    color: Optional[str]
    motto: Optional[str]
    created_at: datetime
    org_id: str


class BandCreate(BaseModel):
    grade: str = Field(min_length=1, max_length=10)
    min_score: Decimal
    max_score: Decimal
    remark: Optional[str] = None


class BandResponse(BaseModel):
    id: str
    grade: str
    min_score: Optional[float] = None   # None for descriptor-scale bands
    max_score: Optional[float] = None
    remark: Optional[str]
    scale_id: Optional[str] = None
    position: int = 0
    created_at: datetime
    org_id: str


# ── School Reports R2: sections, grading scales, report templates ─────────────────

SECTION_CURRICULA = {"eyfs", "nigerian", "hybrid"}
ASSESSMENT_MODES = {"descriptive", "numeric", "hybrid"}
SCALE_TYPES = {"numeric", "descriptor"}


class SectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    curriculum: str = "nigerian"
    position: int = 0
    aliases: list[str] = Field(default_factory=list)   # class `level` values that map here


class SectionUpdate(BaseModel):
    name: Optional[str] = None
    curriculum: Optional[str] = None
    position: Optional[int] = None
    aliases: Optional[list[str]] = None


class SectionResponse(BaseModel):
    id: str
    name: str
    curriculum: str
    position: int
    aliases: list[str] = Field(default_factory=list)
    org_id: str


class ScaleBandCreate(BaseModel):
    grade: str = Field(min_length=1, max_length=20)
    min_score: Optional[Decimal] = None
    max_score: Optional[Decimal] = None
    remark: Optional[str] = None
    position: int = 0


class GradingScaleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scale_type: str = "numeric"
    is_provisional: bool = True
    bands: list[ScaleBandCreate] = Field(default_factory=list)


class GradingScaleResponse(BaseModel):
    id: str
    name: str
    scale_type: str
    is_provisional: bool
    bands: list[BandResponse]
    org_id: str


class ReportTemplateCreate(BaseModel):
    section_id: str
    name: str = Field(min_length=1, max_length=120)
    assessment_mode: str = "hybrid"
    ca_weight: Optional[Decimal] = None
    exam_weight: Optional[Decimal] = None
    grading_scale_id: Optional[str] = None
    show_cognitive_table: bool = True
    show_position: bool = True
    show_attendance: bool = True
    show_affective: bool = False
    show_psychomotor: bool = False
    is_provisional: bool = True


class ReportTemplateUpdate(BaseModel):
    name: Optional[str] = None
    assessment_mode: Optional[str] = None
    ca_weight: Optional[Decimal] = None
    exam_weight: Optional[Decimal] = None
    grading_scale_id: Optional[str] = None
    show_cognitive_table: Optional[bool] = None
    show_position: Optional[bool] = None
    show_attendance: Optional[bool] = None
    show_affective: Optional[bool] = None
    show_psychomotor: Optional[bool] = None
    is_provisional: Optional[bool] = None


class ReportTemplateResponse(BaseModel):
    id: str
    section_id: str
    section_name: Optional[str] = None
    name: str
    assessment_mode: str
    ca_weight: Optional[float]
    exam_weight: Optional[float]
    grading_scale_id: Optional[str]
    grading_scale_name: Optional[str] = None
    show_cognitive_table: bool
    show_position: bool
    show_attendance: bool
    show_affective: bool
    show_psychomotor: bool
    is_provisional: bool
    org_id: str


class AutoMapResult(BaseModel):
    linked: int
    unassigned: list[str]        # class names left unmatched (blank/typo/unknown level)


# ── Custom Fields ────────────────────────────────────────────────────────────────

class FieldDefCreate(BaseModel):
    entity_type: str = Field(min_length=1, max_length=40)
    field_key: str = Field(min_length=1, max_length=60)
    label: str = Field(min_length=1, max_length=120)
    field_type: str = "text"
    options: Optional[list[str]] = None
    required: bool = False


class FieldDefResponse(BaseModel):
    id: str
    entity_type: str
    field_key: str
    label: str
    field_type: str
    options: Optional[Any]
    required: bool
    created_at: datetime
    org_id: str


class FieldValueSet(BaseModel):
    field_id: str
    entity_type: str
    entity_id: str
    value: Optional[str] = None


class FieldValueResponse(BaseModel):
    id: str
    field_id: str
    entity_type: str
    entity_id: str
    value: Optional[str]
    org_id: str


# ── Voting ──────────────────────────────────────────────────────────────────────

class PollCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    closes_at: Optional[datetime] = None
    options: list[str] = Field(min_length=2)


class PollOptionResult(BaseModel):
    id: str
    label: str
    votes: int


class PollResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    status: str
    closes_at: Optional[datetime]
    total_votes: int
    options: list[PollOptionResult]
    my_vote_option_id: Optional[str] = None
    created_at: datetime
    org_id: str


class PollListResponse(BaseModel):
    items: list[PollResponse]
    total: int
    page: int
    page_size: int


class CastVote(BaseModel):
    option_id: str


# ── Mailbox ──────────────────────────────────────────────────────────────────────

class MessageCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: Optional[str] = None
    recipient_ids: list[str] = Field(default_factory=list)
    all_staff: bool = False


class MessageResponse(BaseModel):
    id: str
    subject: str
    body: Optional[str]
    sender_id: Optional[str]
    audience: Optional[str]
    recipient_count: int
    read_count: int
    created_at: datetime
    org_id: str


class InboxItemResponse(BaseModel):
    recipient_row_id: str
    message_id: str
    subject: str
    body: Optional[str]
    sender_id: Optional[str]
    read_at: Optional[datetime]
    created_at: datetime


# ── Mobile Manager ───────────────────────────────────────────────────────────────

class MobileDeviceRegister(BaseModel):
    push_token: str = Field(min_length=1, max_length=255)
    platform: Optional[str] = None
    label: Optional[str] = None


class MobileDeviceResponse(BaseModel):
    id: str
    user_id: Optional[str]
    push_token: str
    platform: Optional[str]
    label: Optional[str]
    is_active: bool
    last_seen_at: Optional[datetime]
    created_at: datetime
    org_id: str


class AppConfigSet(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    value: Optional[str] = None
    description: Optional[str] = None


class AppConfigResponse(BaseModel):
    id: str
    key: str
    value: Optional[str]
    description: Optional[str]
    org_id: str
