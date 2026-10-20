"""Pydantic schemas for the school Teacher endpoints.

Teachers in this codebase are not a separate table — they are Users tagged
with `job_title="Teacher"`. SchoolClass.teacher_id, Subject.teacher_id, and
Timetable.teacher_id all FK into `users.id`, so a dedicated Teacher model
would duplicate identity/auth fields and create FK churn. These schemas
shape the request/response around that reality: the teacher-specific bits
(qualification, subjects, hire_date) live in `User.preferences` JSON.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


def _empty_to_none(v):
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


class TeacherCreate(BaseModel):
    first_name: str
    last_name: str
    other_names: Optional[str] = None
    employee_id: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    department: Optional[str] = None
    qualification: Optional[str] = None
    subjects: list[str] = []
    hire_date: Optional[date] = None
    section_id: Optional[str] = None       # Educare "Select School" section
    section_ids: Optional[list[str]] = None  # several sections (Primary AND Secondary)

    @field_validator("phone", "department", "qualification", "hire_date",
                     "other_names", "employee_id", "section_id", mode="before")
    @classmethod
    def _blank_str_to_none(cls, v):
        return _empty_to_none(v)

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def _required_not_blank(cls, v):
        if isinstance(v, str) and v.strip() == "":
            raise ValueError("must not be blank")
        return v

    @field_validator("subjects", mode="before")
    @classmethod
    def _coerce_subjects(cls, v):
        # Accept "Math, Physics" as a convenience for non-JSON clients.
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v or []


class TeacherUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    other_names: Optional[str] = None
    employee_id: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    qualification: Optional[str] = None
    subjects: Optional[list[str]] = None
    hire_date: Optional[date] = None
    is_active: Optional[bool] = None
    section_id: Optional[str] = None
    section_ids: Optional[list[str]] = None

    @field_validator(
        "first_name", "last_name", "phone", "department",
        "qualification", "hire_date", "other_names", "employee_id", "section_id",
        mode="before",
    )
    @classmethod
    def _blank_str_to_none(cls, v):
        return _empty_to_none(v)

    @field_validator("subjects", mode="before")
    @classmethod
    def _coerce_subjects(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v


class TeacherResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    other_names: Optional[str] = None
    employee_id: Optional[str] = None
    photo_url: Optional[str] = None
    email: str
    phone: Optional[str] = None
    department: Optional[str] = None
    qualification: Optional[str] = None
    subjects: list[str] = []
    hire_date: Optional[str] = None
    is_active: bool
    section_id: Optional[str] = None
    section_name: Optional[str] = None
    sections: list[dict] = []
    section_ids: list[str] = []
    created_at: Optional[datetime] = None


class TeacherSubjectsUpdate(BaseModel):
    """Set which Subjects a teacher teaches (real Subject.teacher_id links). One
    teacher per subject — assigning a subject here reassigns it from its previous
    teacher; subjects dropped from the list are unassigned."""
    subject_ids: list[str] = []


class AssignSectionRequest(BaseModel):
    section_id: Optional[str] = None       # null = unassign from any section
    # set = replace all (default); add = join this one too; remove = leave this one
    mode: Literal["set", "add", "remove"] = "set"


class BulkTeacherRow(BaseModel):
    first_name: str
    last_name: str = ""
    title: Optional[str] = None            # Mr / Mrs / Ms ... kept in preferences, not in the name
    subject: Optional[str] = None
    department: Optional[str] = None       # "Primary" / "Secondary" / "Early Years" -> the section
    email: Optional[str] = None            # blank -> firstname@<school domain>

    @field_validator("first_name", mode="before")
    @classmethod
    def _first_required(cls, v):
        if not isinstance(v, str) or not v.strip():
            raise ValueError("must not be blank")
        return v.strip()

    @field_validator("last_name", mode="before")
    @classmethod
    def _last_name_text(cls, v):
        # Surname is optional but always a string: blank/missing -> "".
        return v.strip() if isinstance(v, str) else ""

    @field_validator("title", "subject", "department", "email", mode="before")
    @classmethod
    def _strip(cls, v):
        if v is None:
            return None
        return (v.strip() or None) if isinstance(v, str) else v


class BulkTeacherRequest(BaseModel):
    rows: list[BulkTeacherRow] = Field(min_length=1, max_length=100)
    dry_run: bool = False                  # preview: resolve emails/sections, create nothing
    email_domain: Optional[str] = None     # default: the signed-in admin's own domain


class TeachingPair(BaseModel):
    class_id: str
    subject_id: str


class TeachingAssignmentsUpdate(BaseModel):
    """REPLACES the teacher's class x subject assignments with exactly these pairs."""
    pairs: list[TeachingPair] = Field(default_factory=list, max_length=500)
