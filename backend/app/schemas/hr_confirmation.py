"""Schemas for Staff Confirmation (probation → confirmed)."""

from datetime import date, datetime
from typing import Optional, Literal
from pydantic import BaseModel


class ConfirmationCreate(BaseModel):
    staff_user_id: str
    probation_start: Optional[date] = None
    due_date: Optional[date] = None
    recommendation: Optional[str] = None


class ConfirmationDecide(BaseModel):
    decision: Literal["confirm", "decline"]
    notes: Optional[str] = None


class ConfirmationResponse(BaseModel):
    id: str
    staff_user_id: str
    staff_name: Optional[str] = None
    employment_status: Optional[str] = None      # the staff member's CURRENT status
    probation_start: Optional[date]
    due_date: Optional[date]
    status: str                                   # pending | confirmed | declined
    recommendation: Optional[str]
    decided_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    org_id: str
