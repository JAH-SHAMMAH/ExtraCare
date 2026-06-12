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
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


def _empty_to_none(v):
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


class TeacherCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    department: Optional[str] = None
    qualification: Optional[str] = None
    subjects: list[str] = []
    hire_date: Optional[date] = None

    @field_validator("phone", "department", "qualification", "hire_date", mode="before")
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
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    qualification: Optional[str] = None
    subjects: Optional[list[str]] = None
    hire_date: Optional[date] = None
    is_active: Optional[bool] = None

    @field_validator(
        "first_name", "last_name", "phone", "department",
        "qualification", "hire_date",
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
    email: str
    phone: Optional[str] = None
    department: Optional[str] = None
    qualification: Optional[str] = None
    subjects: list[str] = []
    hire_date: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
