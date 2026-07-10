"""Schemas for the Feedback section's additional surfaces: settings, staff daily
reports, per-student daily reports, and a light CRM/enquiry pipeline."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Feedback settings ────────────────────────────────────────────────────────

class FeedbackSettingsUpdate(BaseModel):
    allow_anonymous: Optional[bool] = None
    notify_on_submit: Optional[bool] = None
    acknowledgement_message: Optional[str] = None


class FeedbackSettingsResponse(_OrmBase):
    id: str
    allow_anonymous: bool
    notify_on_submit: bool
    acknowledgement_message: Optional[str]
    org_id: str


# ── Daily report (staff) ─────────────────────────────────────────────────────

class DailyReportCreate(BaseModel):
    report_date: date
    class_id: Optional[str] = None
    summary: str = Field(min_length=1)
    highlights: Optional[str] = None
    challenges: Optional[str] = None


class DailyReportUpdate(BaseModel):
    report_date: Optional[date] = None
    class_id: Optional[str] = None
    summary: Optional[str] = None
    highlights: Optional[str] = None
    challenges: Optional[str] = None


class DailyReportResponse(_OrmBase):
    id: str
    author_id: str
    author_name: Optional[str] = None
    report_date: date
    class_id: Optional[str]
    summary: str
    highlights: Optional[str]
    challenges: Optional[str]
    created_at: datetime
    org_id: str


# ── Student daily report ─────────────────────────────────────────────────────

class StudentDailyReportCreate(BaseModel):
    student_id: str
    report_date: date
    mood: Optional[str] = None
    academic: Optional[str] = None
    behaviour: Optional[str] = None
    notes: Optional[str] = None


class StudentDailyReportUpdate(BaseModel):
    report_date: Optional[date] = None
    mood: Optional[str] = None
    academic: Optional[str] = None
    behaviour: Optional[str] = None
    notes: Optional[str] = None


class StudentDailyReportResponse(_OrmBase):
    id: str
    student_id: str
    student_name: Optional[str] = None
    author_id: str
    report_date: date
    mood: Optional[str]
    academic: Optional[str]
    behaviour: Optional[str]
    notes: Optional[str]
    created_at: datetime
    org_id: str


# ── CRM contact ──────────────────────────────────────────────────────────────

_CRM_STAGES = {"new", "contacted", "engaged", "converted", "lost"}


class CRMContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: Optional[str] = None
    phone: Optional[str] = None
    contact_type: str = "prospective_parent"
    stage: str = "new"
    source: Optional[str] = None
    notes: Optional[str] = None


class CRMContactUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    email: Optional[str] = None
    phone: Optional[str] = None
    contact_type: Optional[str] = None
    stage: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None


class CRMContactResponse(_OrmBase):
    id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    contact_type: str
    stage: str
    source: Optional[str]
    assigned_to: Optional[str]
    notes: Optional[str]
    created_at: datetime
    org_id: str
