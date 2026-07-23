"""Schemas for the TimeTable module (setup, periods, activities, schedules).

org_id is pinned server-side, never from the client.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class _Orm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Settings ──────────────────────────────────────────────────────────────────

class TimetableSettingsResponse(_Orm):
    enable_even_odd_week: bool
    enable_subject_grouping: bool
    default_period_group_id: Optional[str]
    subject_group_type: Optional[str]
    week_start_day: str
    org_id: str


class TimetableSettingsUpdate(BaseModel):
    enable_even_odd_week: Optional[bool] = None
    enable_subject_grouping: Optional[bool] = None
    default_period_group_id: Optional[str] = None
    subject_group_type: Optional[str] = None
    week_start_day: Optional[str] = None


# ── Period groups ─────────────────────────────────────────────────────────────

class PeriodGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    year_group: Optional[str] = None


class PeriodGroupUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    year_group: Optional[str] = None


class PeriodGroupResponse(_Orm):
    id: str
    name: str
    year_group: Optional[str]
    org_id: str


# ── Subject groups ────────────────────────────────────────────────────────────

class SubjectGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    year_group: Optional[str] = None
    subject_ids: list[str] = []


class SubjectGroupUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    year_group: Optional[str] = None
    subject_ids: Optional[list[str]] = None


class SubjectGroupResponse(_Orm):
    id: str
    name: str
    year_group: Optional[str]
    subject_ids: list[str] = []
    org_id: str


# ── Activities ────────────────────────────────────────────────────────────────

class SchoolActivityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    color: Optional[str] = None


class SchoolActivityUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    color: Optional[str] = None


class SchoolActivityResponse(_Orm):
    id: str
    name: str
    color: Optional[str]
    org_id: str
