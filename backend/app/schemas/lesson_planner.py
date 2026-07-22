"""Schemas for Lesson Planner Setup — categories, settings, supervisors, clone."""

from __future__ import annotations

from datetime import date, time
from typing import Optional
from pydantic import BaseModel, Field


# ── Categories ────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class CategoryUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class CategoryResponse(BaseModel):
    id: str
    name: str
    org_id: str


# ── Settings (singleton per org) ──────────────────────────────────────────────

class PlannerSettingsResponse(BaseModel):
    require_approval: bool
    default_duration_minutes: int
    allow_backdated: bool
    display_category_names: bool
    change_subject_topic: bool
    change_day_format: bool
    edit_lesson_plan: bool
    supervisor_signature: Optional[str] = None
    org_id: str


class PlannerSettingsUpdate(BaseModel):
    require_approval: Optional[bool] = None
    default_duration_minutes: Optional[int] = Field(default=None, ge=5, le=240)
    allow_backdated: Optional[bool] = None
    display_category_names: Optional[bool] = None
    change_subject_topic: Optional[bool] = None
    change_day_format: Optional[bool] = None
    edit_lesson_plan: Optional[bool] = None
    supervisor_signature: Optional[str] = Field(default=None, max_length=500)


# ── Supervisors ───────────────────────────────────────────────────────────────

class SupervisorCreate(BaseModel):
    supervisor_id: str
    section_id: Optional[str] = None   # null = org-wide


class SupervisorResponse(BaseModel):
    id: str
    supervisor_id: str
    supervisor_name: Optional[str] = None
    section_id: Optional[str] = None
    section_name: Optional[str] = None
    org_id: str


# ── Clone ─────────────────────────────────────────────────────────────────────

class CloneLessonsRequest(BaseModel):
    """Copy plans dated in [source_start, source_end] to new drafts anchored at
    target_start, preserving each plan's day-offset from source_start. A plan
    already existing at the target (same class+subject+date+period) is skipped."""
    source_start: date
    source_end: date
    target_start: date
    only_mine: bool = False   # admins can clone the whole school; default all


class CloneLessonsResult(BaseModel):
    cloned: int
    skipped: int


# ── Reminder schedules ────────────────────────────────────────────────────────

SCHEDULE_AUDIENCES = {"teachers", "all_staff"}
SCHEDULE_FREQUENCIES = {"daily", "weekly"}


class ScheduleCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=200)   # the "email content"
    body: Optional[str] = None
    audience: str = "teachers"
    frequency: str = "weekly"
    days: Optional[list[int]] = None    # [0..6] weekdays (Mon=0) — required for weekly
    run_time: time
    is_active: bool = True


class ScheduleUpdate(BaseModel):
    subject: Optional[str] = Field(default=None, min_length=1, max_length=200)
    body: Optional[str] = None
    audience: Optional[str] = None
    frequency: Optional[str] = None
    days: Optional[list[int]] = None
    run_time: Optional[time] = None
    is_active: Optional[bool] = None


class ScheduleResponse(BaseModel):
    id: str
    subject: str
    body: Optional[str] = None
    audience: str
    frequency: str
    days: Optional[list[int]] = None
    run_time: time
    is_active: bool
    last_run_on: Optional[date] = None
    org_id: str


class ScheduleRunResult(BaseModel):
    dispatched: int      # number of schedules that fired
    recipients: int      # total recipient deliveries created
