"""Schemas for staff attendance (HR Access Control)."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.models.hr_attendance import StaffClockType


class SelfClockCreate(BaseModel):
    """A staff member clocking THEMSELVES in / out (event_time is server 'now')."""
    event_type: StaffClockType
    note: Optional[str] = None


class AdminEventCreate(BaseModel):
    """Admin adding / correcting a punch for any staff member."""
    staff_user_id: str
    event_type: StaffClockType
    event_time: Optional[datetime] = None   # defaults to now if omitted
    note: Optional[str] = None


class AttendanceEventResponse(BaseModel):
    id: str
    staff_user_id: str
    staff_name: Optional[str] = None
    event_type: str
    event_time: datetime
    source: str
    note: Optional[str]
    created_at: datetime
