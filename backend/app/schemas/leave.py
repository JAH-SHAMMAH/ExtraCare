"""Pydantic schemas for the Leave module.

Mirrors the router's endpoints:
  * LeaveApplicationCreate — what an employee submits
  * LeaveDecision          — approver-supplied note on approve/reject
  * LeaveApplicationResponse — row-shape returned everywhere
  * LeaveAnalytics         — aggregates for the HR dashboard

Blank-string → None coercion is applied to `reason` so the HTML textarea
doesn't push "" into a nullable Text column.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from app.models.leave import LeaveType, LeaveStatus


def _empty_to_none(v):
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


class LeaveApplicationCreate(BaseModel):
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: Optional[str] = None

    @field_validator("reason", mode="before")
    @classmethod
    def _blank(cls, v):
        return _empty_to_none(v)


class LeaveDecision(BaseModel):
    """Optional approver note — rejections benefit most from a reason."""
    decision_note: Optional[str] = None

    @field_validator("decision_note", mode="before")
    @classmethod
    def _blank(cls, v):
        return _empty_to_none(v)


class LeaveApplicationResponse(BaseModel):
    id: str
    user_id: str
    org_id: str
    applicant_name: Optional[str] = None
    applicant_email: Optional[str] = None

    leave_type: LeaveType
    start_date: date
    end_date: date
    days: int
    reason: Optional[str] = None

    status: LeaveStatus
    approver_id: Optional[str] = None
    approver_name: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_note: Optional[str] = None

    created_at: Optional[datetime] = None


# ── Analytics ────────────────────────────────────────────────────────────────

class StatusCount(BaseModel):
    status: LeaveStatus
    count: int


class MonthCount(BaseModel):
    month: str   # "2026-03"
    count: int


class TypeCount(BaseModel):
    leave_type: LeaveType
    count: int


class LeaveAnalytics(BaseModel):
    total: int
    by_status: list[StatusCount]
    by_month: list[MonthCount]       # last 12 months, chronological
    by_type: list[TypeCount]
    pending_count: int               # convenience for dashboard badges
