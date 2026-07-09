"""Schemas for Attendance Setup — per-org late cutoff + absence reason codes."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AttendanceSettingsResponse(BaseModel):
    late_after_time: str  # "HH:MM" local time; check-in at/after → LATE


class AttendanceSettingsUpdate(BaseModel):
    late_after_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")  # "HH:MM"


class AbsenceReasonResponse(BaseModel):
    id: str
    code: str
    label: str
    is_authorized: bool
    is_active: bool


class AbsenceReasonCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=120)
    is_authorized: bool = True


class AbsenceReasonUpdate(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=120)
    is_authorized: Optional[bool] = None
    is_active: Optional[bool] = None
