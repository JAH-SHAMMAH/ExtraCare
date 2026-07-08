"""CBT Phase C schemas — interventions + org settings."""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class InterventionCreate(BaseModel):
    student_id: str
    exam_id: Optional[str] = None
    attempt_id: Optional[str] = None
    reason: str = Field(min_length=1)
    note: Optional[str] = None


class InterventionUpdate(BaseModel):
    status: Optional[Literal["open", "in_progress", "resolved"]] = None
    note: Optional[str] = None


class CBTSettingsUpdate(BaseModel):
    default_duration_minutes: Optional[int] = Field(default=None, ge=1, le=600)
    default_pass_percentage: Optional[int] = Field(default=None, ge=0, le=100)
    shuffle_default: Optional[bool] = None
    instructions: Optional[str] = None
