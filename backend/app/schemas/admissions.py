"""Schemas for Admissions & Enrollment (Batch 2).

*Create schemas omit org_id (pinned server-side). *Response schemas are built
explicitly by the router so they can carry resolved display names (class /
student) without ORM relationships. Status/stage/outcome/type values are
validated here against the allowed sets.
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


# Allowed value sets (validated in the router on create/update).
ADMISSION_STATUSES = {"enquiry", "applied", "screening", "offered", "admitted", "rejected", "withdrawn"}
EXAM_STATUSES = {"scheduled", "completed"}
EXAM_OUTCOMES = {"pending", "pass", "fail"}
PROMOTION_OUTCOMES = {"promoted", "repeated", "graduated"}
TRANSFER_TYPES = {"transfer_out", "withdrawal"}
TRANSFER_STATUSES = {"pending", "completed"}


# ── Admission Applications ─────────────────────────────────────────────────────

class AdmissionApplicationCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    guardian_email: Optional[str] = None
    applying_for_class_id: Optional[str] = None
    applying_for_level: Optional[str] = None
    source: Optional[str] = None
    status: str = "enquiry"
    notes: Optional[str] = None


class AdmissionApplicationUpdate(BaseModel):
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    guardian_email: Optional[str] = None
    applying_for_class_id: Optional[str] = None
    applying_for_level: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class AdmissionApplicationResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    full_name: str
    date_of_birth: Optional[date]
    gender: Optional[str]
    guardian_name: Optional[str]
    guardian_phone: Optional[str]
    guardian_email: Optional[str]
    applying_for_class_id: Optional[str]
    applying_for_class_name: Optional[str]
    applying_for_level: Optional[str]
    source: Optional[str]
    status: str
    notes: Optional[str]
    admitted_student_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    org_id: str


class AdmissionApplicationListResponse(BaseModel):
    items: list[AdmissionApplicationResponse]
    total: int
    page: int
    page_size: int


class AdmitRequest(BaseModel):
    """Optional overrides applied when converting an application to a Student."""
    class_id: Optional[str] = None       # defaults to applying_for_class_id
    student_id: Optional[str] = None     # org-assigned code; auto-generated if omitted
    admission_date: Optional[date] = None


# ── Entrance Exams ─────────────────────────────────────────────────────────────

class EntranceExamCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    exam_date: Optional[date] = None
    subject: Optional[str] = None
    max_score: int = Field(default=100, ge=1, le=1000)
    status: str = "scheduled"
    notes: Optional[str] = None


class EntranceExamUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    exam_date: Optional[date] = None
    subject: Optional[str] = None
    max_score: Optional[int] = Field(default=None, ge=1, le=1000)
    status: Optional[str] = None
    notes: Optional[str] = None


class EntranceExamResponse(BaseModel):
    id: str
    title: str
    exam_date: Optional[date]
    subject: Optional[str]
    max_score: int
    status: str
    notes: Optional[str]
    result_count: int = 0
    created_at: datetime
    org_id: str


class EntranceExamListResponse(BaseModel):
    items: list[EntranceExamResponse]
    total: int
    page: int
    page_size: int


class EntranceExamResultCreate(BaseModel):
    application_id: Optional[str] = None
    candidate_name: str = Field(min_length=1, max_length=200)
    score: Optional[int] = Field(default=None, ge=0)
    outcome: str = "pending"
    remark: Optional[str] = None


class EntranceExamResultUpdate(BaseModel):
    candidate_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    score: Optional[int] = Field(default=None, ge=0)
    outcome: Optional[str] = None
    remark: Optional[str] = None


class EntranceExamResultResponse(BaseModel):
    id: str
    exam_id: str
    application_id: Optional[str]
    candidate_name: str
    score: Optional[int]
    outcome: str
    remark: Optional[str]
    created_at: datetime
    org_id: str


# ── Promotions ─────────────────────────────────────────────────────────────────

class PromotionCreate(BaseModel):
    student_ids: list[str] = Field(min_length=1)
    to_class_id: Optional[str] = None      # None allowed for "graduated" outcome
    from_class_id: Optional[str] = None
    academic_year: Optional[str] = None
    outcome: str = "promoted"


class PromotionRecordResponse(BaseModel):
    id: str
    batch_id: str
    student_id: str
    student_name: Optional[str]
    from_class_id: Optional[str]
    from_class_name: Optional[str]
    to_class_id: Optional[str]
    to_class_name: Optional[str]
    academic_year: Optional[str]
    outcome: str
    reverted_at: Optional[datetime] = None
    created_at: datetime
    org_id: str


class PromotionListResponse(BaseModel):
    items: list[PromotionRecordResponse]
    total: int
    page: int
    page_size: int


class PromotionPreviewItem(BaseModel):
    student_id: str
    student_name: Optional[str]
    from_class_id: Optional[str]
    from_class_name: Optional[str]
    eligible: bool
    reason: Optional[str] = None  # why an entry is skipped (e.g. "inactive")


class PromotionPreviewResponse(BaseModel):
    """Dry-run: who WOULD be affected before a mass promotion commits."""
    outcome: str
    to_class_id: Optional[str]
    to_class_name: Optional[str]
    eligible_count: int
    skipped_count: int
    items: list[PromotionPreviewItem]


class PromotionRevertResponse(BaseModel):
    batch_id: str
    reverted: int


# ── Transfers ──────────────────────────────────────────────────────────────────

class TransferCreate(BaseModel):
    student_id: str
    transfer_type: str = "transfer_out"
    destination_school: Optional[str] = None
    reason: Optional[str] = None
    transfer_date: Optional[date] = None
    status: str = "pending"


class TransferUpdate(BaseModel):
    transfer_type: Optional[str] = None
    destination_school: Optional[str] = None
    reason: Optional[str] = None
    transfer_date: Optional[date] = None
    status: Optional[str] = None


class TransferRecordResponse(BaseModel):
    id: str
    student_id: str
    student_name: Optional[str]
    transfer_type: str
    destination_school: Optional[str]
    reason: Optional[str]
    transfer_date: Optional[date]
    status: str
    created_at: datetime
    org_id: str


class TransferListResponse(BaseModel):
    items: list[TransferRecordResponse]
    total: int
    page: int
    page_size: int
