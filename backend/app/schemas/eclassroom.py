"""Schemas for the eClassroom module."""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


# ── Setup ─────────────────────────────────────────────────────────────────────

class SettingsResponse(BaseModel):
    can_teacher_publish: bool
    automatic_approval: bool
    learning_program_enabled: bool


class SettingsUpdate(BaseModel):
    can_teacher_publish: bool = True
    automatic_approval: bool = False
    learning_program_enabled: bool = False


# ── Programs ──────────────────────────────────────────────────────────────────

class ProgramCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    cbt_type: str = "student"
    section_id: Optional[str] = None
    session_id: Optional[str] = None
    is_active: bool = True


class ProgramUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    cbt_type: Optional[str] = None
    section_id: Optional[str] = None
    session_id: Optional[str] = None
    is_active: Optional[bool] = None


class ProgramResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    cbt_type: str
    section_id: Optional[str]
    section_name: Optional[str] = None
    session_id: Optional[str]
    session_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    org_id: str


# ── Schedules (Manage eClassrooms + Live Broadcast) ───────────────────────────

class ScheduleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    section_id: Optional[str] = None
    session_id: Optional[str] = None
    year_group_id: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class ScheduleUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    section_id: Optional[str] = None
    session_id: Optional[str] = None
    year_group_id: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class ScheduleResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    section_id: Optional[str]
    section_name: Optional[str] = None
    session_id: Optional[str]
    session_name: Optional[str] = None
    year_group_id: Optional[str]
    year_group_name: Optional[str] = None
    scheduled_at: Optional[datetime]
    status: str
    live_session_id: Optional[str]
    created_at: datetime
    org_id: str
