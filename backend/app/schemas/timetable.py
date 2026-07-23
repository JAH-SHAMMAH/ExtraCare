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


# ── Periods ───────────────────────────────────────────────────────────────────

class PeriodCreate(BaseModel):
    period_group_id: str
    academic_year: Optional[str] = None
    day_of_week: int = Field(ge=0, le=6)
    start_time: str
    end_time: str
    period_type: str = "LESSON"
    sort_order: int = 0


class PeriodUpdate(BaseModel):
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    period_type: Optional[str] = None
    sort_order: Optional[int] = None


class PeriodResponse(_Orm):
    id: str
    period_group_id: str
    academic_year: Optional[str]
    day_of_week: int
    start_time: str
    end_time: str
    period_type: str
    sort_order: int
    org_id: str


class NonLessonPeriod(BaseModel):
    name: str                       # e.g. "SHORT BREAK", "RECESS"
    after_period: int = Field(ge=0)  # insert after this many lesson periods
    minutes: int = Field(gt=0)


class PeriodGenerateRequest(BaseModel):
    period_group_id: str
    academic_year: Optional[str] = None
    days: list[int] = Field(min_length=1)         # 0=Mon .. 6=Sun
    periods_per_day: int = Field(gt=0, le=20)
    start_time: str                                # "07:45"
    minutes_per_period: int = Field(gt=0, le=240)
    non_lesson: list[NonLessonPeriod] = []
    replace_existing: bool = True                  # clear the group's periods first


class PeriodGenerateResult(BaseModel):
    created: int


# ── Schedules ─────────────────────────────────────────────────────────────────

class PeriodScheduleCreate(BaseModel):
    period_id: str
    class_id: str
    subject_id: str
    teacher_id: Optional[str] = None
    academic_year: Optional[str] = None


class PeriodScheduleResponse(BaseModel):
    id: str
    period_id: str
    class_id: str
    subject_id: str
    subject_name: Optional[str] = None
    teacher_id: Optional[str] = None
    teacher_name: Optional[str] = None
    academic_year: Optional[str] = None


# ── Curriculum ────────────────────────────────────────────────────────────────

class CurriculumCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    class_id: Optional[str] = None
    subject_id: Optional[str] = None
    file_url: Optional[str] = None
    academic_year: Optional[str] = None


class CurriculumUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    class_id: Optional[str] = None
    subject_id: Optional[str] = None
    file_url: Optional[str] = None
    academic_year: Optional[str] = None


class CurriculumResponse(_Orm):
    id: str
    class_id: Optional[str]
    subject_id: Optional[str]
    subject_name: Optional[str] = None
    name: str
    file_url: Optional[str]
    academic_year: Optional[str]
    org_id: str


# ── Time Tabler ───────────────────────────────────────────────────────────────

class TimetableJobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    period_group_id: Optional[str] = None
    academic_year: Optional[str] = None
    period_type: Optional[str] = None


class TimetableJobResponse(_Orm):
    id: str
    title: str
    period_group_id: Optional[str]
    academic_year: Optional[str]
    period_type: Optional[str]
    status: str
    created_at: object
    updated_at: object
    org_id: str


class TimetableGenerateResult(BaseModel):
    status: str
    created: int


# ── Subject attendance (filtered view) ────────────────────────────────────────

class SubjectAttendanceRow(BaseModel):
    student_id: str
    student_name: str
    present: int
    absent: int
    late: int
    total: int


class SubjectAttendanceResponse(BaseModel):
    items: list[SubjectAttendanceRow]
    days: int
