"""Pydantic schemas for the school Student endpoints.

The previous `data: dict` handler accepted whatever JSON the browser sent —
including `date_of_birth=""` from an un-filled `<input type="date">`, which
SQLAlchemy's `Column(Date)` rejects at flush with StatementError. The global
exception handler then 500'd the request, and the UI surfaced that as a
generic "failed to create student". These schemas close that gap at the
boundary so errors are specific and never reach the DB broken.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


def _empty_to_none(v):
    """Treat the empty string as 'not provided'.

    HTML forms submit `""` rather than omitting the field, so optional
    fields like `date_of_birth` arrive as empty strings. Pydantic would
    happily accept that for a plain `str`, but for `date`/`EmailStr` it
    raises — and even when it passes validation, an empty string in a
    `Column(Date)` blows up at flush.
    """
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


class StudentCreate(BaseModel):
    student_id: str
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    photo_url: Optional[str] = None
    address: Optional[str] = None
    class_id: Optional[str] = None
    admission_date: Optional[date] = None
    graduation_date: Optional[date] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    guardian_email: Optional[EmailStr] = None
    guardian_relationship: Optional[str] = None

    @field_validator(
        "email", "phone", "gender", "photo_url", "address",
        "class_id", "guardian_name", "guardian_phone",
        "guardian_email", "guardian_relationship",
        "date_of_birth", "admission_date", "graduation_date",
        mode="before",
    )
    @classmethod
    def _blank_str_to_none(cls, v):
        return _empty_to_none(v)

    @field_validator("student_id", "first_name", "last_name", mode="before")
    @classmethod
    def _required_not_blank(cls, v):
        if isinstance(v, str) and v.strip() == "":
            raise ValueError("must not be blank")
        return v


class StudentUpdate(BaseModel):
    student_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    photo_url: Optional[str] = None
    address: Optional[str] = None
    class_id: Optional[str] = None
    admission_date: Optional[date] = None
    graduation_date: Optional[date] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    guardian_email: Optional[EmailStr] = None
    guardian_relationship: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator(
        "email", "phone", "gender", "photo_url", "address",
        "class_id", "guardian_name", "guardian_phone",
        "guardian_email", "guardian_relationship",
        "date_of_birth", "admission_date", "graduation_date",
        mode="before",
    )
    @classmethod
    def _blank_str_to_none(cls, v):
        return _empty_to_none(v)
