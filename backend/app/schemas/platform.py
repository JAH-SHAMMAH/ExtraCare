"""Schemas for Administration & Platform (Batch 7)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Biometric ───────────────────────────────────────────────────────────────────

class _DeviceSpecs(BaseModel):
    model_name: Optional[str] = None
    vendor: Optional[str] = None
    device_type: Optional[str] = None
    volume: Optional[int] = None
    language: Optional[str] = None
    firmware_version: Optional[str] = None
    fingerprint_version: Optional[str] = None
    face_version: Optional[str] = None
    mac_address: Optional[str] = None
    storage_used_percent: Optional[int] = None
    attendance_log_capacity: Optional[int] = None
    current_attendance_log: Optional[int] = None


class DeviceCreate(_DeviceSpecs):
    device_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=150)
    location: Optional[str] = None
    notes: Optional[str] = None


class DeviceUpdate(_DeviceSpecs):
    name: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class DeviceResponse(_DeviceSpecs):
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
    student_id: Optional[str] = None      # target a student …
    user_id: Optional[str] = None         # … OR a staff user (exactly one)
    label: Optional[str] = None
    fingerprint_count: int = 0
    has_face: bool = False
    has_card: bool = False
    profile_pic_url: Optional[str] = None
    status: str = "registered"


class EnrollmentResponse(BaseModel):
    id: str
    biometric_user_id: str
    student_id: Optional[str]
    user_id: Optional[str]
    person_name: Optional[str]
    person_type: str                      # "student" | "staff"
    role_name: Optional[str] = None       # staff role (for the Registered Users role grouping)
    label: Optional[str]
    fingerprint_count: int
    has_face: bool
    has_card: bool
    profile_pic_url: Optional[str]
    status: str
    created_at: datetime
    org_id: str


class BiometricCommandCreate(BaseModel):
    command: str = Field(min_length=1, max_length=100)


class BiometricCommandResponse(BaseModel):
    id: str
    device_pk: str
    device_id: Optional[str] = None
    command: str
    status: str
    result: Optional[str]
    created_at: datetime
    updated_at: datetime
    org_id: str


class BiometricSummary(BaseModel):
    total_devices: int
    total_device_users: int      # enrolments
    total_fingerprint: int       # enrolments with ≥1 fingerprint
    total_face: int
    total_card: int
    total_active_users: int      # active (registered) enrolments
    total_attendance: int        # attendance events


class AttendanceHistoryRow(BaseModel):
    id: str
    student_id: str
    name: Optional[str]
    event_type: str              # check_in | check_out
    event_time: datetime
    source: str                  # biometric | manual | …
    device_id: Optional[str]


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
    section_id: Optional[str] = None
    is_active: Optional[bool] = True


class HouseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    color: Optional[str] = None
    motto: Optional[str] = None
    section_id: Optional[str] = None
    is_active: Optional[bool] = None


class HouseResponse(BaseModel):
    id: str
    name: str
    color: Optional[str]
    motto: Optional[str]
    section_id: Optional[str] = None
    section_name: Optional[str] = None
    is_active: bool = True
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
    show_in_table: bool = True
    purpose: str = "grade"           # grade | keys | cumulative | mock
    bands: list[ScaleBandCreate] = Field(default_factory=list)


class GradingScaleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    is_provisional: Optional[bool] = None
    show_in_table: Optional[bool] = None
    purpose: Optional[str] = None


class GradingScaleResponse(BaseModel):
    id: str
    name: str
    scale_type: str
    is_provisional: bool
    show_in_table: bool = True
    purpose: str = "grade"
    bands: list[BandResponse]
    org_id: str


SCALE_PURPOSES = {"grade", "keys", "cumulative", "mock"}


class BrandingUpdate(BaseModel):
    school_motto: Optional[str] = None
    school_name_alias: Optional[str] = None
    school_address: Optional[str] = None
    school_website: Optional[str] = None
    school_email: Optional[str] = None
    school_phone: Optional[str] = None
    class_teacher_title: Optional[str] = None
    school_head_title: Optional[str] = None
    school_head_name: Optional[str] = None
    full_term_passmark: Optional[Decimal] = None
    mid_term_passmark: Optional[Decimal] = None
    min_average_honours: Optional[Decimal] = None
    promotion_comment: Optional[str] = None
    demotion_comment: Optional[str] = None
    logo_url: Optional[str] = None
    head_signature_url: Optional[str] = None
    logo_background_url: Optional[str] = None
    sponsor_url: Optional[str] = None


class BrandingResponse(BrandingUpdate):
    id: Optional[str] = None


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


class SubjectAssessmentResponse(BaseModel):
    subject_id: str
    subject_name: Optional[str] = None
    carries_cambridge: bool = False
    cambridge_scale_id: Optional[str] = None


class SubjectAssessmentUpdate(BaseModel):
    carries_cambridge: bool
    cambridge_scale_id: Optional[str] = None


class SetCambridgeAllRequest(BaseModel):
    carries_cambridge: bool
    cambridge_scale_id: Optional[str] = None


# ── School Reports R3: assessment domains + student ratings ───────────────────────

# eyfs_area / eyfs_goal — EYFS Areas of Learning + their Early Learning Goals
# (Nursery). cambridge_strand — a Cambridge attainment strand under a subject
# (hybrid overlay). psychomotor / affective — the Nigerian report's skills + character.
DOMAIN_TYPES = {"eyfs_area", "eyfs_goal", "cambridge_strand", "psychomotor", "affective"}


class DomainCreate(BaseModel):
    domain_type: str
    name: str = Field(min_length=1, max_length=150)
    parent_domain_id: Optional[str] = None    # eyfs_goal → its area
    parent_subject_id: Optional[str] = None   # cambridge_strand → its subject
    rating_scale_id: Optional[str] = None
    position: int = 0


class DomainUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    parent_domain_id: Optional[str] = None
    parent_subject_id: Optional[str] = None
    rating_scale_id: Optional[str] = None
    position: Optional[int] = None


class DomainResponse(BaseModel):
    id: str
    section_id: str
    domain_type: str
    name: str
    parent_domain_id: Optional[str] = None
    parent_subject_id: Optional[str] = None
    subject_name: Optional[str] = None
    rating_scale_id: Optional[str] = None
    position: int = 0
    org_id: str


class DomainRatingItem(BaseModel):
    domain_id: str
    rating: Optional[str] = None    # descriptor label; empty rating+comment clears the row
    comment: Optional[str] = None


class DomainRatingsSet(BaseModel):
    term: str = Field(min_length=1, max_length=50)
    ratings: list[DomainRatingItem] = Field(default_factory=list)


class DomainRatingResponse(BaseModel):
    id: str
    student_id: str
    term: str
    domain_id: str
    rating: Optional[str] = None
    comment: Optional[str] = None
    org_id: str


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


# ── Secondary Report parity S-0: Terms & Sub-term + periods + deadlines ──────

class SubTermCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    alias: Optional[str] = None
    position: int = 0


class SubTermUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    alias: Optional[str] = None
    position: Optional[int] = None
    is_active: Optional[bool] = None


class SubTermResponse(BaseModel):
    id: str
    name: str
    alias: Optional[str] = None
    position: int = 0
    is_active: bool = True


class TermCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    alias: Optional[str] = None
    position: int = 0


class TermUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    alias: Optional[str] = None
    position: Optional[int] = None
    is_active: Optional[bool] = None
    active_sub_term_id: Optional[str] = None


class TermResponse(BaseModel):
    id: str
    name: str
    alias: Optional[str] = None
    position: int = 0
    is_active: bool = False
    active_sub_term_id: Optional[str] = None
    active_sub_term_name: Optional[str] = None
    active_sub_term_position: Optional[int] = None


class TermPeriodUpsert(BaseModel):
    session_id: str
    term_id: str
    sub_term_id: str
    begin_date: Optional[date] = None
    end_date: Optional[date] = None
    next_term_begins: Optional[date] = None
    published_date: Optional[date] = None
    excluded_days: Optional[int] = None
    total_days: Optional[int] = None


class TermPeriodResponse(BaseModel):
    id: str
    session_id: str
    term_id: str
    term_name: Optional[str] = None
    sub_term_id: str
    sub_term_name: Optional[str] = None
    begin_date: Optional[date] = None
    end_date: Optional[date] = None
    next_term_begins: Optional[date] = None
    published_date: Optional[date] = None
    excluded_days: Optional[int] = None
    total_days: Optional[int] = None


class DeadlineUpsert(BaseModel):
    session_id: str
    term_id: str
    sub_term_id: Optional[str] = None
    status: str = "open"
    submission_deadline: Optional[date] = None


class DeadlineResponse(BaseModel):
    id: str
    session_id: str
    term_id: str
    term_name: Optional[str] = None
    sub_term_id: Optional[str] = None
    sub_term_name: Optional[str] = None
    status: str = "open"
    submission_deadline: Optional[date] = None


# ── Secondary Report parity S-1a: Comment types + Result Default Comments ────

class CommentTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    comment_type: str = "short"          # short | long
    max_length: Optional[int] = None


class CommentTypeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    comment_type: Optional[str] = None
    max_length: Optional[int] = None
    is_active: Optional[bool] = None


class CommentTypeResponse(BaseModel):
    id: str
    name: str
    comment_type: str = "short"
    max_length: Optional[int] = None
    is_active: bool = True


class DefaultCommentCreate(BaseModel):
    teacher_type: str = "class"          # subject | class | head
    grading_scale_id: Optional[str] = None
    year_group: Optional[str] = None
    min_score: Optional[Decimal] = None
    max_score: Optional[Decimal] = None
    comment: str = Field(min_length=1)


class DefaultCommentUpdate(BaseModel):
    teacher_type: Optional[str] = None
    grading_scale_id: Optional[str] = None
    year_group: Optional[str] = None
    min_score: Optional[Decimal] = None
    max_score: Optional[Decimal] = None
    comment: Optional[str] = Field(default=None, min_length=1)


class DefaultCommentResponse(BaseModel):
    id: str
    teacher_type: str = "class"
    grading_scale_id: Optional[str] = None
    grading_scale_name: Optional[str] = None
    year_group: Optional[str] = None
    min_score: Optional[Decimal] = None
    max_score: Optional[Decimal] = None
    comment: str


COMMENT_LENGTH_TYPES = {"short", "long"}
TEACHER_TYPES = {"subject", "class", "head"}


# ── Secondary Report parity S-1c: Result Type/Photo + Subject Exclusion ──────

RESULT_TYPES = {"junior", "senior"}


class LevelSettingUpsert(BaseModel):
    year_group: str = Field(min_length=1, max_length=60)
    result_type: str = "junior"
    show_position: bool = True
    show_photo: bool = True


class LevelSettingResponse(BaseModel):
    id: str
    year_group: str
    result_type: str = "junior"
    show_position: bool = True
    show_photo: bool = True


class SubjectExclusionCreate(BaseModel):
    year_group: str = Field(min_length=1, max_length=60)
    subject_id: str


class SubjectExclusionResponse(BaseModel):
    id: str
    year_group: str
    subject_id: str
    subject_name: Optional[str] = None


# ── Secondary Report parity S-2: Assessment Group + Assessment ───────────────

class AssessmentGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    position: int = 0


class AssessmentGroupUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    position: Optional[int] = None


class AssessmentGroupResponse(BaseModel):
    id: str
    name: str
    position: int = 0


class AssessmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    code: Optional[str] = None
    max_score: Decimal = Decimal("100")
    term_id: str
    sub_term_id: str
    year_group: Optional[str] = None      # None = All Levels
    decimal_places: int = 0
    group_id: Optional[str] = None
    position: int = 0


class AssessmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    code: Optional[str] = None
    max_score: Optional[Decimal] = None
    term_id: Optional[str] = None
    sub_term_id: Optional[str] = None
    year_group: Optional[str] = None
    decimal_places: Optional[int] = None
    group_id: Optional[str] = None
    position: Optional[int] = None


class AssessmentResponse(BaseModel):
    id: str
    name: str
    code: Optional[str] = None
    max_score: Decimal
    term_id: str
    term_name: Optional[str] = None
    sub_term_id: str
    sub_term_name: Optional[str] = None
    year_group: Optional[str] = None
    decimal_places: int = 0
    group_id: Optional[str] = None
    group_name: Optional[str] = None
    position: int = 0


# ── Secondary Report parity S-3: Cumulative curated engine ───────────────────

CUMUL_TYPES = {"score", "percentage", "custom_percentage"}
REF_TYPES = {"assessment", "cumulative"}


class CumulComponentIn(BaseModel):
    ref_type: str          # assessment | cumulative
    ref_id: str


class CumulComponentOut(BaseModel):
    ref_type: str
    ref_id: str
    label: Optional[str] = None


class CumulativeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: Optional[str] = None
    term_id: str
    sub_term_id: str
    year_group: Optional[str] = None
    cumul_type: str = "score"
    max_percent: Optional[Decimal] = None
    decimal_places: int = 0
    position: int = 0
    components: list[CumulComponentIn] = Field(default_factory=list)


class CumulativeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    code: Optional[str] = None
    cumul_type: Optional[str] = None
    max_percent: Optional[Decimal] = None
    decimal_places: Optional[int] = None
    position: Optional[int] = None


class CumulativeResponse(BaseModel):
    id: str
    name: str
    code: Optional[str] = None
    term_id: str
    term_name: Optional[str] = None
    sub_term_id: str
    sub_term_name: Optional[str] = None
    year_group: Optional[str] = None
    cumul_type: str = "score"
    max_percent: Optional[Decimal] = None
    decimal_places: int = 0
    position: int = 0
    components: list[CumulComponentOut] = Field(default_factory=list)


# ── Secondary Report parity S-4a: Report Entry (assessment scores) ───────────

class ReportEntryAssessment(BaseModel):
    id: str
    name: str
    max_score: Decimal
    sub_term_name: Optional[str] = None


class ReportEntryStudent(BaseModel):
    id: str
    name: str


class ReportEntryGrid(BaseModel):
    class_id: str
    subject_id: str
    term_id: str
    assessments: list[ReportEntryAssessment] = Field(default_factory=list)
    students: list[ReportEntryStudent] = Field(default_factory=list)
    # scores[student_id][assessment_id] = score
    scores: dict[str, dict[str, Optional[Decimal]]] = Field(default_factory=dict)


class ScoreItem(BaseModel):
    student_id: str
    assessment_id: str
    score: Optional[Decimal] = None


class ReportEntrySave(BaseModel):
    subject_id: str
    class_id: Optional[str] = None      # required for teacher (timetable) scoping
    items: list[ScoreItem] = Field(default_factory=list)


class TeachingAssignment(BaseModel):
    class_id: str
    class_name: Optional[str] = None
    subject_id: str
    subject_name: Optional[str] = None


# ── Secondary Report parity S-4b: Broadsheet ─────────────────────────────────

class BroadsheetSubject(BaseModel):
    id: str
    name: str


class BroadsheetCell(BaseModel):
    value: Optional[Decimal] = None
    grade: Optional[str] = None


class BroadsheetRow(BaseModel):
    student_id: str
    student_name: str
    subjects: dict[str, BroadsheetCell] = Field(default_factory=dict)
    total: Decimal = Decimal("0")
    average: Decimal = Decimal("0")
    grade: Optional[str] = None
    position: int = 0


class BroadsheetBand(BaseModel):
    grade: str
    min_score: Optional[Decimal] = None
    max_score: Optional[Decimal] = None
    remark: Optional[str] = None


class BroadsheetResponse(BaseModel):
    class_id: str
    class_name: Optional[str] = None
    term_name: Optional[str] = None
    sub_term_name: Optional[str] = None
    display_cumulative: Optional[str] = None
    subjects: list[BroadsheetSubject] = Field(default_factory=list)
    bands: list[BroadsheetBand] = Field(default_factory=list)
    rows: list[BroadsheetRow] = Field(default_factory=list)


# ── Secondary Report parity S-4c: printable report card ──────────────────────

class CardColumn(BaseModel):
    key: str            # assessment/cumulative id
    name: str
    kind: str           # assessment | cumulative
    max_score: Optional[Decimal] = None


class CardSubjectRow(BaseModel):
    subject_id: str
    subject_name: str
    values: dict[str, Optional[Decimal]] = Field(default_factory=dict)   # column key -> value
    grade: Optional[str] = None
    remark: Optional[str] = None
    subject_arm_average: Optional[Decimal] = None


class ReportCardResponse(BaseModel):
    student_id: str
    student_name: Optional[str] = None
    admission_no: Optional[str] = None
    photo_url: Optional[str] = None
    class_name: Optional[str] = None
    term_name: Optional[str] = None
    sub_term_name: Optional[str] = None
    report_title: Optional[str] = None
    branding: BrandingResponse = Field(default_factory=BrandingResponse)
    columns: list[CardColumn] = Field(default_factory=list)
    subjects: list[CardSubjectRow] = Field(default_factory=list)
    bands: list[BroadsheetBand] = Field(default_factory=list)
    total: Decimal = Decimal("0")
    average: Decimal = Decimal("0")
    grade: Optional[str] = None
    position: int = 0
    class_size: int = 0
    # Mean of every classmate's percentage average — the reference card's
    # "Total Class Average" box, shown beside the pupil's own average.
    class_average: Optional[Decimal] = None
    # attendance (from the existing StudentReport, if authored)
    attendance_present: Optional[int] = None
    attendance_total: Optional[int] = None
    # "Times Punctual": present-and-not-late days, counted from AttendanceRecord.
    # The check-in pipeline already resolves lateness against the org's
    # late_after_time when it ingests an AttendanceEvent (services/attendance.py),
    # so this reads that decision rather than re-deriving it from raw punches —
    # one source of truth. None when no roll-call data exists yet.
    attendance_punctual: Optional[int] = None
    # Three genuinely distinct comments. class_teacher/head come from the older
    # StudentReport row (which is where the authored text actually lives); pc is
    # the newer per-(term, sub-term) StudentReportComment store.
    class_teacher_comment: Optional[str] = None
    head_comment: Optional[str] = None
    pc_comment: Optional[str] = None


# ── Secondary Report parity S-4d: report-card comments (Head / PC) ───────────

REPORT_COMMENT_KINDS = {"head", "pc"}


class CommentGridRow(BaseModel):
    student_id: str
    student_name: str
    text: Optional[str] = None


class CommentGridResponse(BaseModel):
    class_id: str
    term_id: str
    sub_term_id: str
    kind: str
    rows: list[CommentGridRow] = Field(default_factory=list)


class CommentItem(BaseModel):
    student_id: str
    text: Optional[str] = None


class CommentGridSave(BaseModel):
    term_id: str
    sub_term_id: str
    kind: str
    class_id: Optional[str] = None      # required for teacher (PC / class) scoping
    items: list[CommentItem] = Field(default_factory=list)


# ── Secondary Report parity S-5: Result Insight (performance charts) ──────────

class InsightSubject(BaseModel):
    subject_id: str
    subject_name: str
    average: Decimal = Decimal("0")


class InsightGender(BaseModel):
    subject_id: str
    subject_name: str
    male: Optional[Decimal] = None
    female: Optional[Decimal] = None


class InsightClass(BaseModel):
    class_id: str
    class_name: str
    average: Decimal = Decimal("0")


class InsightResponse(BaseModel):
    term_name: Optional[str] = None
    sub_term_name: Optional[str] = None
    subjects: list[InsightSubject] = Field(default_factory=list)
    gender: list[InsightGender] = Field(default_factory=list)
    classes: list[InsightClass] = Field(default_factory=list)


# ── Secondary Report parity S-6: Reports Upload (bulk score import) ──────────

class ScoreUploadResult(BaseModel):
    rows: int = 0
    imported: int = 0
    errors: list[str] = Field(default_factory=list)
