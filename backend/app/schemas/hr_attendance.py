"""Schemas for staff attendance (HR Access Control)."""

from datetime import datetime, time
from typing import Optional
from pydantic import BaseModel, Field

from app.models.hr_attendance import StaffClockType


class SelfClockCreate(BaseModel):
    """A staff member clocking THEMSELVES in / out (event_time is server 'now').
    lat/lng are the caller's coordinates — required only when geofencing is on."""
    event_type: StaffClockType
    note: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


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


# ── Access Control configuration ──────────────────────────────────────────────

class AttendanceSettingsResponse(BaseModel):
    work_start_time: Optional[time]
    work_end_time: Optional[time]
    late_grace_minutes: int
    geofence_enabled: bool
    geofence_lat: Optional[float]
    geofence_lng: Optional[float]
    geofence_radius_m: Optional[int]


class AttendanceSettingsUpdate(BaseModel):
    work_start_time: Optional[time] = None
    work_end_time: Optional[time] = None
    late_grace_minutes: int = Field(default=0, ge=0, le=720)
    geofence_enabled: bool = False
    geofence_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    geofence_lng: Optional[float] = Field(default=None, ge=-180, le=180)
    geofence_radius_m: Optional[int] = Field(default=None, ge=10, le=100000)
