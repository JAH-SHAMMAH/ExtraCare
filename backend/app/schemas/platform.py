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
    # An AcademicTerm id, not a name. The rest of the report pipeline
    # (report-card, broadsheet, report-entry) takes term_id, and a name here was
    # the last string-matched term reference in the codebase — the mechanism
    # behind the report-card blanking incident.
    term_id: str = Field(min_length=1, description="AcademicTerm id (not a name)")
    ratings: list[DomainRatingItem] = Field(default_factory=list)


class DomainRatingColumn(BaseModel):
    """One assessment domain as a column of the ratings grid.

    Carries its own descriptor `options`, so the grid does not need a separate
    grading-scales round trip to know what a cell may be set to — the same reason
    ReportEntryAssessment carries max_score.
    """
    domain_id: str
    name: str
    domain_type: str
    parent_domain_id: Optional[str] = None
    parent_subject_id: Optional[str] = None
    options: list[str] = Field(default_factory=list)


class DomainRatingCell(BaseModel):
    rating: Optional[str] = None
    comment: Optional[str] = None


class DomainRatingsStudentRow(BaseModel):
    student_id: str
    student_name: str
    admission_no: Optional[str] = None
    # domain_id -> the pupil's rating for it. Absent keys mean unrated.
    ratings: dict[str, DomainRatingCell] = Field(default_factory=dict)


class DomainRatingsGrid(BaseModel):
    """A whole class's domain ratings for one term, in ONE call.

    The per-pupil GET could not hydrate a class grid without one request per
    child, which is why the entry form was shipping with `ratings={[]}` and a TODO.
    Shaped after ReportEntryGrid so the two authoring surfaces read alike.
    """
    class_id: str
    class_name: Optional[str] = None
    term_id: str
    term_name: Optional[str] = None
    section_name: Optional[str] = None
    domains: list[DomainRatingColumn] = Field(default_factory=list)
    students: list[DomainRatingsStudentRow] = Field(default_factory=list)


class DomainRatingResponse(BaseModel):
    id: str
    student_id: str
    term_id: str
    term_name: Optional[str] = None
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
    # A custom slot is PC-teacher-writable by DEFAULT; the admin opts it out at
    # creation. Carried on all three schemas because a rule the API cannot set
    # is a rule that does not exist — the column and its gate were live while
    # nothing could ever turn it on.
    admin_only: bool = False


class CommentTypeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    comment_type: Optional[str] = None
    max_length: Optional[int] = None
    is_active: Optional[bool] = None
    admin_only: Optional[bool] = None


class CommentTypeResponse(BaseModel):
    id: str
    name: str
    comment_type: str = "short"
    max_length: Optional[int] = None
    is_active: bool = True
    admin_only: bool = False


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
    # Which academic year this belongs to. Optional in the REQUEST and resolved
    # to the current session server-side, so existing callers keep working; the
    # column itself is NOT NULL. Absent from AssessmentUpdate on purpose —
    # moving an assessment between years would drag its marks with it.
    session_id: Optional[str] = None
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
    session_id: Optional[str] = None      # see AssessmentCreate.session_id
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


class ReportEntrySubmission(BaseModel):
    """The report-workflow state behind a Make Report grid."""
    # None when no workflow row exists yet — the teacher has not handed it in and
    # the office has not opened one. Distinct from "draft", which is a real row.
    stage: Optional[str] = None
    can_submit: bool = False
    # Why not, when can_submit is False and the report is still open. Lets the page
    # explain rather than silently hiding the control.
    reason: Optional[str] = None


class ReportEntryGrid(BaseModel):
    class_id: str
    subject_id: str
    term_id: str
    assessments: list[ReportEntryAssessment] = Field(default_factory=list)
    students: list[ReportEntryStudent] = Field(default_factory=list)
    # scores[student_id][assessment_id] = score
    scores: dict[str, dict[str, Optional[Decimal]]] = Field(default_factory=dict)
    # Why an expected column is empty — chiefly a CBT exam whose results were
    # published but whose scores never reached here. Without this the grid cannot
    # distinguish "not marked yet" from "marked, but the feed was skipped", and
    # the teacher has no way to tell which. Already phrased for the viewer: a
    # setup problem only an admin can fix is generalised before it gets here.
    notices: list[str] = Field(default_factory=list)
    # Where this class's term report has got to, and whether THIS user may hand it
    # in. Carried on the grid the page already loads so the UI never offers a
    # button that would 403 — only the class teacher may submit, and only from
    # 'draft'.
    submission: "ReportEntrySubmission" = Field(default_factory=lambda: ReportEntrySubmission())


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


class CardSlotComment(BaseModel):
    """One custom comment slot's text on a pupil's card."""
    comment_type_id: str
    name: str
    text: str


class CardSubjectRow(BaseModel):
    subject_id: str
    subject_name: str
    values: dict[str, Optional[Decimal]] = Field(default_factory=dict)   # column key -> value
    # Cumulative columns whose components are not all marked for this pupil. Their
    # entry in `values` is None rather than a number: an unmarked component is
    # scored as zero by the evaluator, so a total built on one understates what the
    # child actually earned, on the page their parent reads. `grade` is withheld
    # for the same reason — a letter from a deflated total is the same false claim
    # in one character — and the subject is left out of the average and total.
    incomplete_components: list[str] = Field(default_factory=list)
    grade: Optional[str] = None
    remark: Optional[str] = None
    subject_arm_average: Optional[Decimal] = None
    # This subject's mean percentage across the session's terms. None where the
    # subject has marks in no term but the one being viewed — there is nothing
    # to average, and repeating the term's own figure would dress a single term
    # up as a session.
    sessional: Optional[Decimal] = None
    # The subject teacher's remark on this pupil for this subject.
    comment: Optional[str] = None


class SessionalTerm(BaseModel):
    """One term's contribution to the Sessional Score, named so a card can show
    what the figure is actually built from. `average` is None for a term with no
    marks, which is what keeps "based on 1 of 3 terms" honest."""
    term_id: str
    term_name: Optional[str] = None
    average: Optional[Decimal] = None


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
    # Sessional Score: the unweighted mean of the session's per-term averages.
    # Computed at read time from the same cumulatives the card already uses —
    # nothing is stored, so it cannot drift from the marks behind it.
    sessional_score: Optional[Decimal] = None
    sessional_terms: list[SessionalTerm] = Field(default_factory=list)
    # How many of `sessional_terms` actually carried marks. A card should say so
    # rather than presenting a one-term mean as a full session's score.
    sessional_terms_counted: int = 0
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
    # Configured custom slots that HAVE a comment for this pupil. Slots with no
    # text are absent from the list entirely rather than present-and-empty, so the
    # card never prints a labelled blank box.
    slot_comments: list["CardSlotComment"] = Field(default_factory=list)


# ── Secondary Report parity S-4d: report-card comments (Head / PC) ───────────

REPORT_COMMENT_KINDS = {"head", "pc"}
# The `kind` every CUSTOM slot row carries. A literal, never the slot's name: a
# name is editable, and a mutable string inside a uniqueness key is precisely what
# made report_approvals.term and cbt_exams.term drift out from under their gates.
# The slot itself lives in comment_type_id.
CUSTOM_COMMENT_KIND = "custom"


class SubjectCommentItem(BaseModel):
    student_id: str
    text: Optional[str] = None


class SubjectCommentGridRow(BaseModel):
    student_id: str
    student_name: str
    text: Optional[str] = None
    # Whether this pupil has any mark in this subject. A comment on a pupil with
    # no marks is legitimate (a remark about missing work), so this informs the
    # grid rather than gating it.
    has_marks: bool = False


class SubjectCommentGridResponse(BaseModel):
    class_id: str
    class_name: Optional[str] = None
    subject_id: str
    subject_name: Optional[str] = None
    term_id: str
    sub_term_id: str
    rows: list[SubjectCommentGridRow] = Field(default_factory=list)
    # Max length the UI should enforce, from the configured comment type where the
    # school has set one. None means unlimited.
    max_length: Optional[int] = None


class SubjectCommentSave(BaseModel):
    class_id: str
    subject_id: str
    term_id: str
    sub_term_id: str
    items: list[SubjectCommentItem] = Field(default_factory=list)


# ── Subject enrolment (the register, and the gate on marks) ───────────────────

class EnrollmentSubject(BaseModel):
    subject_id: str
    subject_name: Optional[str] = None
    enrolled: bool = False
    # True when the pupil has a mark in this subject. A subject with marks but no
    # enrolment is the state migration 128's backfill exists to prevent, so
    # surfacing it means a later gap is visible rather than silent.
    has_marks: bool = False


class EnrollmentStudentRow(BaseModel):
    student_id: str
    student_name: str
    admission_no: Optional[str] = None
    subjects: list[EnrollmentSubject] = Field(default_factory=list)
    enrolled_count: int = 0


class EnrollmentGridResponse(BaseModel):
    """The shape Educare's Subject Enrollment screen needs: a class's pupils down
    the side, the available subjects across the top, a tick in each cell."""
    class_id: str
    class_name: Optional[str] = None
    academic_year: str
    subjects: list[EnrollmentSubject] = Field(default_factory=list)   # the columns
    students: list[EnrollmentStudentRow] = Field(default_factory=list)
    total_enrolled: int = 0


class EnrollmentStudentSet(BaseModel):
    student_id: str
    subject_ids: list[str] = Field(default_factory=list)


class EnrollmentSave(BaseModel):
    """Replaces each listed pupil's enrolment set for the session.

    A REPLACE, not a merge, because that is what a checkbox grid means: unticking
    a box has to remove the enrolment, and a merge-only endpoint could never
    express that. Only the pupils named in `items` are touched.
    """
    class_id: str
    academic_year: Optional[str] = None      # defaults to the current session
    items: list[EnrollmentStudentSet] = Field(default_factory=list)


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
    comment_type_id: Optional[str] = None
    slot_name: Optional[str] = None


class CommentItem(BaseModel):
    student_id: str
    text: Optional[str] = None


class CommentGridSave(BaseModel):
    term_id: str
    sub_term_id: str
    kind: str = "head"
    # A custom slot (report_comment_types). When present it identifies the row and
    # `kind` is ignored — every custom row carries the literal 'custom', so `kind`
    # cannot tell two slots apart.
    comment_type_id: Optional[str] = None
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


# ── Result Analysis (Wave 1: Remedial List + Honour Roll) ────────────────────

class AnalysisSubjectMark(BaseModel):
    subject_id: str
    subject_name: Optional[str] = None
    percentage: Decimal


class AnalysisPupil(BaseModel):
    student_id: str
    student_name: str
    admission_no: Optional[str] = None
    class_id: Optional[str] = None
    class_name: Optional[str] = None
    average: Optional[Decimal] = None
    grade: Optional[str] = None
    subjects_counted: int = 0
    # Remedial List: the subjects below the passmark, so the list says WHAT to
    # remediate rather than only who. Empty on the Honour Roll.
    subjects_below: list[AnalysisSubjectMark] = Field(default_factory=list)
    # Honour Roll: 1-based standing within the returned list.
    position: Optional[int] = None


class ResultAnalysisResponse(BaseModel):
    term_name: Optional[str] = None
    sub_term_name: Optional[str] = None
    class_name: Optional[str] = None       # when scoped to one class
    threshold: Decimal
    # 'configured' | 'partial' | 'default' — which thresholds were actually used.
    # Surfaced so a page can say so: naming a pupil as failing against a threshold
    # nobody set should not look like a settled fact.
    threshold_source: str = "configured"
    pupils: list[AnalysisPupil] = Field(default_factory=list)
    # How many pupils were assessed at all, so "3 of 180" is expressible rather
    # than a bare list of three.
    considered: int = 0
    # Pupils in scope with NO marks. They are neither failing nor honoured, and
    # counting them either way would be wrong — reported separately instead.
    unmarked: int = 0
    # True when the term has no display cumulative or no assessments, i.e. nothing
    # was computable. An empty list then means "not set up", not "nobody qualified".
    not_configured: bool = False


# ── Secondary Report parity S-6: Reports Upload (bulk score import) ──────────

class ScoreUploadResult(BaseModel):
    rows: int = 0
    imported: int = 0
    errors: list[str] = Field(default_factory=list)


# ── Performance Tracker (teacher Result Analysis) ─────────────────────────────

class TrackerColumn(BaseModel):
    """One column of the tracker: a (term, sub-term) pair, or the sessional total.

    `key` is what a cell is looked up by. `available` is False when that term and
    sub-term have no cumulative or no assessments configured — the column is still
    SHOWN (the layout is the school's reporting shape, not a reflection of what
    happens to be marked) but every cell in it reads as not-entered rather than 0.
    """
    key: str
    term_id: Optional[str] = None
    term_name: Optional[str] = None
    sub_term_id: Optional[str] = None
    sub_term_name: Optional[str] = None
    label: str
    group: Optional[str] = None          # "Autumn" / "Spring" / "Summer" / None
    available: bool = True


class TrackerCell(BaseModel):
    # None means NOT ENTERED — never 0. A blank cell and a zero are different
    # claims about a child, and the second one is a mark they did not receive.
    score: Optional[Decimal] = None
    grade: Optional[str] = None


class TrackerRow(BaseModel):
    sn: int
    student_id: str
    student_name: str
    admission_no: Optional[str] = None
    # column key -> cell. A missing key is a cell with no mark.
    cells: dict[str, TrackerCell] = Field(default_factory=dict)
    sessional_score: Optional[Decimal] = None
    sessional_grade: Optional[str] = None
    # How many terms fed the sessional score, so "based on 1 of 3 terms" is
    # expressible and a one-term figure is not presented as a full session.
    sessional_terms_counted: int = 0


class PerformanceTrackerResponse(BaseModel):
    class_id: str
    class_name: Optional[str] = None
    subject_id: str
    subject_name: Optional[str] = None
    session_name: Optional[str] = None
    columns: list[TrackerColumn] = Field(default_factory=list)
    rows: list[TrackerRow] = Field(default_factory=list)
    # True when NO column in the whole grid is configured — the difference between
    # "this class has not been marked" and "reports are not set up at all".
    not_configured: bool = False


class AnalysisClassOption(BaseModel):
    """A class the signed-in user may open Result Analysis for."""
    id: str
    name: Optional[str] = None
    section_id: Optional[str] = None


# ── Result Analysis wave 2: Order of Merit, Grade Summary, Subject Performance ──
#
# All three are PIVOTS of `analyse_term`. None computes a percentage of its own:
# the Booster List, the Honour Roll, the Performance Tracker and these read one
# function, so no two screens can disagree about what a pupil scored.

class MeritRow(BaseModel):
    position: int
    student_id: str
    student_name: str
    admission_no: Optional[str] = None
    class_name: Optional[str] = None
    average: Decimal
    grade: Optional[str] = None
    subjects_counted: int = 0
    # True when this pupil shares their position with another. Standard
    # competition ranking (1, 2, 2, 4) — two equal averages are equal, and
    # printing them as 2nd and 3rd would assert an order the marks do not contain.
    tied: bool = False


class OrderOfMeritResponse(BaseModel):
    term_name: Optional[str] = None
    sub_term_name: Optional[str] = None
    class_name: Optional[str] = None
    rows: list[MeritRow] = Field(default_factory=list)
    considered: int = 0
    # Pupils in scope with no marks. Never ranked: their standing is unknown, not
    # last, and a merit list that places them would be inventing a result.
    unmarked: int = 0
    not_configured: bool = False


class GradeSummaryRow(BaseModel):
    subject_id: Optional[str] = None      # None on the "All subjects" total row
    subject_name: str
    # grade letter -> count, for the school's own bands in their own order.
    counts: dict[str, int] = Field(default_factory=dict)
    entered: int = 0                      # marks counted in this row
    average: Optional[Decimal] = None


class GradeSummaryResponse(BaseModel):
    term_name: Optional[str] = None
    sub_term_name: Optional[str] = None
    class_name: Optional[str] = None
    grades: list[str] = Field(default_factory=list)   # column order, best first
    rows: list[GradeSummaryRow] = Field(default_factory=list)
    total_row: Optional[GradeSummaryRow] = None
    not_configured: bool = False


class SubjectPerformanceRow(BaseModel):
    subject_id: str
    subject_name: str
    entered: int = 0                      # pupils with a usable mark
    average: Optional[Decimal] = None
    highest: Optional[Decimal] = None
    lowest: Optional[Decimal] = None
    passed: int = 0
    failed: int = 0
    pass_rate: Optional[Decimal] = None   # None when nobody has a mark
    # Pupils who HAVE marks in this subject but not every component the total
    # needs. Excluded from every figure above rather than scored low, and surfaced
    # so a mean computed over 12 of 15 pupils does not read as the whole class.
    incomplete: int = 0


class SubjectPerformanceResponse(BaseModel):
    term_name: Optional[str] = None
    sub_term_name: Optional[str] = None
    class_name: Optional[str] = None
    passmark: Decimal
    # 'configured' | 'partial' | 'default' — naming a subject's pass rate against a
    # threshold nobody set should not look like a settled fact.
    threshold_source: str = "configured"
    rows: list[SubjectPerformanceRow] = Field(default_factory=list)
    not_configured: bool = False


# ── Departmental Analysis ─────────────────────────────────────────────────────

class DepartmentRow(BaseModel):
    # None is the real "unassigned" bucket, not an error: a subject with no
    # department is shown as such rather than silently dropped from the totals.
    department: Optional[str] = None
    subjects: list[str] = Field(default_factory=list)
    entered: int = 0                      # marks counted across the department
    pupils: int = 0                       # distinct pupils with at least one mark
    average: Optional[Decimal] = None
    highest: Optional[Decimal] = None
    lowest: Optional[Decimal] = None
    passed: int = 0
    failed: int = 0
    pass_rate: Optional[Decimal] = None
    # Pupil-subject pairs with some marks but not every component the total needs.
    # Counted in no other figure here, for the same reason as Subject Performance.
    incomplete: int = 0


# ── Subjects Averages Across Sessions ────────────────────────────────────────
#
# The report migration 134 existed for. Terms are shared across sessions, so
# before assessments carried a session_id there was no way to tell 2025/2026's
# Autumn from 2026/2027's, and a cross-year figure would silently have been a
# blend of the two.

class SessionAverageCell(BaseModel):
    """One subject's standing in one session."""
    average: Optional[Decimal] = None
    # Terms of the session that produced a figure for this subject. Carried
    # because a mean over ONE term is not a year, and the two are
    # indistinguishable once reduced to a single number on a grid.
    terms_counted: int = 0
    entered: int = 0


class SessionAverageColumn(BaseModel):
    session_id: str
    session_name: Optional[str] = None
    is_current: bool = False
    terms_counted: int = 0
    term_names: list[str] = Field(default_factory=list)
    # True when nothing in this session was computable for the chosen sub-term.
    # The column still appears: a year that exists but is not set up is worth
    # showing, and omitting it would make the grid silently misrepresent which
    # years the school has.
    not_configured: bool = True


class SessionAverageRow(BaseModel):
    subject_id: str
    subject_name: str
    department: Optional[str] = None
    # session_id -> cell. Absent keys mean "no figure for that year", which the
    # client renders as "not entered" rather than as a zero.
    cells: dict[str, SessionAverageCell] = Field(default_factory=dict)
    # Mean of the session figures this subject actually has.
    overall: Optional[Decimal] = None
    # Latest minus earliest session that BOTH hold a figure. None when fewer than
    # two do — a single year has no direction, and a dash in a trend column reads
    # as a fall to zero.
    trend: Optional[Decimal] = None
    sessions_counted: int = 0


class SubjectAveragesAcrossSessionsResponse(BaseModel):
    sub_term_name: Optional[str] = None
    class_name: Optional[str] = None
    columns: list[SessionAverageColumn] = Field(default_factory=list)
    rows: list[SessionAverageRow] = Field(default_factory=list)
    # True when NO session was computable — nothing is set up for this sub-term
    # anywhere, as opposed to set up and unmarked.
    not_configured: bool = False
    # True when only one session holds figures, so no comparison is possible yet.
    # Said explicitly so the page can explain an un-interesting grid instead of
    # looking broken.
    single_session: bool = False


class DepartmentalAnalysisResponse(BaseModel):
    term_name: Optional[str] = None
    sub_term_name: Optional[str] = None
    class_name: Optional[str] = None
    passmark: Decimal
    threshold_source: str = "configured"
    rows: list[DepartmentRow] = Field(default_factory=list)
    # True when no subject carries a department at all — the report is empty
    # because nothing has been categorised, which is a different thing from a
    # term that was never set up.
    no_departments: bool = False
    not_configured: bool = False
