"""Schemas for leave configuration + entitlements + assignment."""

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field

from app.models.leave import LeaveType


class LeavePolicyUpdate(BaseModel):
    default_days: int = Field(ge=0, le=366)
    requires_approval: bool = True
    is_active: bool = True


class LeavePolicyResponse(BaseModel):
    leave_type: str
    label: str
    default_days: int
    requires_approval: bool
    is_active: bool


class EntitlementRow(BaseModel):
    leave_type: str
    label: str
    allocated: int
    used: int
    remaining: int


class AssignLeaveCreate(BaseModel):
    user_id: str
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: Optional[str] = None
