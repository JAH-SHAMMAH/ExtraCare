"""Schemas for Lesson Planner Setup — categories, settings, supervisors, clone."""

from __future__ import annotations

from datetime import date
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
    org_id: str


class PlannerSettingsUpdate(BaseModel):
    require_approval: Optional[bool] = None
    default_duration_minutes: Optional[int] = Field(default=None, ge=5, le=240)
    allow_backdated: Optional[bool] = None


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
