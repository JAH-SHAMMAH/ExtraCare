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


# ── Pastoral Setup: settings (Exeat + Default Settings) ──────────────────────

# All flags optional on update (PUT is an upsert-merge); every flag echoed back.
_FLAGS = [
    "enable_head_only_approval", "notify_parent_on_exeat_approval",
    "notify_house_parent_on_exeat_approval", "notify_pastoral_head_on_new_request",
    "enable_tutorial_week", "email_parent_on_new_point_entry", "enable_academic_cohesion",
    "show_award_in_point_analysis", "allow_referral_in_mentor_comment", "enable_point_category",
    "enable_mentor_report_assessment", "allow_only_merits_in_point_entry",
    "allow_observation_in_mentor_comment",
]


class PastoralSettingsUpdate(BaseModel):
    enable_head_only_approval: Optional[bool] = None
    notify_parent_on_exeat_approval: Optional[bool] = None
    notify_house_parent_on_exeat_approval: Optional[bool] = None
    notify_pastoral_head_on_new_request: Optional[bool] = None
    enable_tutorial_week: Optional[bool] = None
    email_parent_on_new_point_entry: Optional[bool] = None
    enable_academic_cohesion: Optional[bool] = None
    show_award_in_point_analysis: Optional[bool] = None
    allow_referral_in_mentor_comment: Optional[bool] = None
    enable_point_category: Optional[bool] = None
    enable_mentor_report_assessment: Optional[bool] = None
    allow_only_merits_in_point_entry: Optional[bool] = None
    allow_observation_in_mentor_comment: Optional[bool] = None
    school_nurse_role_id: Optional[str] = None       # "" / null clears it


class PastoralSettingsResponse(PastoralSettingsUpdate):
    school_nurse_role_name: Optional[str] = None


# ── Batch B: House Masters / House Weeks / Pastoral Students ──────────────────

class HouseMasterCreate(BaseModel):
    house_id: str
    user_id: str


class HouseMasterResponse(BaseModel):
    id: str
    house_id: str
    house_name: Optional[str] = None
    user_id: str
    user_name: Optional[str] = None


class HouseWeekCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: bool = True


class HouseWeekUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None


class HouseWeekResponse(BaseModel):
    id: str
    name: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: bool


class PastoralStudentAssign(BaseModel):
    house_id: Optional[str] = None
    mentor_id: Optional[str] = None
    is_leader: Optional[bool] = None


class PastoralBulkAssign(BaseModel):
    student_ids: list[str] = []
    house_id: Optional[str] = None
    mentor_id: Optional[str] = None
    is_leader: Optional[bool] = None


class PastoralStudentRow(BaseModel):
    student_id: str
    student_name: Optional[str] = None
    class_name: Optional[str] = None
    house_id: Optional[str] = None
    house_name: Optional[str] = None
    mentor_id: Optional[str] = None
    mentor_name: Optional[str] = None
    is_leader: bool = False


# ── Batch C: Point System / Award System / Point Entry / Points Analysis ─────

class PointTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scope: str = "weekly"          # sessional | weekly
    max_point: Optional[int] = None
    category: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True


class PointTypeUpdate(BaseModel):
    name: Optional[str] = None
    scope: Optional[str] = None
    max_point: Optional[int] = None
    category: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PointTypeResponse(BaseModel):
    id: str
    name: str
    scope: str
    max_point: Optional[int] = None
    category: Optional[str] = None
    description: Optional[str] = None
    is_active: bool


class AwardTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    min_point: Optional[int] = None
    max_point: Optional[int] = None
    description: Optional[str] = None
    is_active: bool = True


class AwardTypeUpdate(BaseModel):
    name: Optional[str] = None
    min_point: Optional[int] = None
    max_point: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class AwardTypeResponse(BaseModel):
    id: str
    name: str
    min_point: Optional[int] = None
    max_point: Optional[int] = None
    description: Optional[str] = None
    is_active: bool


class PointEntryCreate(BaseModel):
    student_id: str
    points: int
    category: Optional[str] = None     # point type name / category
    title: Optional[str] = None
    reason: Optional[str] = None
    term: Optional[str] = None
    house: Optional[str] = None


class PointEntryResponse(BaseModel):
    id: str
    student_id: str
    student_name: Optional[str] = None
    points: int
    title: Optional[str] = None
    category: Optional[str] = None
    reason: Optional[str] = None
    term: Optional[str] = None
    house: Optional[str] = None
    awarded_on: Optional[date] = None


class PointsAnalysisRow(BaseModel):
    student_id: str
    student_name: Optional[str] = None
    house_name: Optional[str] = None
    opening_point: int = 0
    autumn: int = 0
    spring: int = 0
    summer: int = 0
    total_pg: int = 0    # points gained (positive)
    total_pl: int = 0    # points lost (|negative|)
    total: int = 0       # net


# ── Batch D-1: Hostel Setup + Hostel Students ────────────────────────────────

class HostelManagerCreate(BaseModel):
    hostel_id: str
    user_id: str


class HostelManagerResponse(BaseModel):
    id: str
    hostel_id: str
    hostel_name: Optional[str] = None
    user_id: str
    user_name: Optional[str] = None


class HostelLifeGradeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: Optional[str] = None
    sort_order: int = 0


class HostelLifeGradeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class HostelLifeGradeResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class HostelCommentBankCreate(BaseModel):
    text: str = Field(..., min_length=1)
    category: Optional[str] = None


class HostelCommentBankUpdate(BaseModel):
    text: Optional[str] = Field(None, min_length=1)
    category: Optional[str] = None
    is_active: Optional[bool] = None


class HostelCommentBankResponse(BaseModel):
    id: str
    text: str
    category: Optional[str] = None
    is_active: bool = True


class HostelStudentRow(BaseModel):
    allocation_id: str
    student_id: str
    student_name: Optional[str] = None
    admission_no: Optional[str] = None
    hostel_id: str
    hostel_name: Optional[str] = None
    room: Optional[str] = None
    bed: Optional[str] = None
    allocated_on: Optional[date] = None


class HostelImportResult(BaseModel):
    imported: int = 0
    errors: list[str] = Field(default_factory=list)
