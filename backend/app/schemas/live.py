"""Pydantic schemas for the Live Session module."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class LiveSessionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    class_id: Optional[str] = None
    subject_id: Optional[str] = None
    timetable_id: Optional[str] = None

    @field_validator("title", mode="before")
    @classmethod
    def _blank_title(cls, v):
        if isinstance(v, str) and not v.strip():
            raise ValueError("title must not be blank")
        return v


class LiveSessionResponse(BaseModel):
    id: str
    org_id: str
    host_user_id: str
    host_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    class_id: Optional[str] = None
    subject_id: Optional[str] = None
    timetable_id: Optional[str] = None
    is_active: bool
    started_at: datetime
    ended_at: Optional[datetime] = None
    viewer_count: int = 0
    has_recording: bool = False
    created_at: datetime


class TimetableSlotResponse(BaseModel):
    """A timetable slot with optional live session + metadata for one-click join."""
    timetable_id: str
    class_id: str
    class_name: Optional[str] = None
    subject_id: Optional[str] = None
    subject_name: Optional[str] = None
    day_of_week: int
    start_time: str
    end_time: str
    is_current: bool
    live_session_id: Optional[str] = None
    can_host: bool = False


class LiveRecordingResponse(BaseModel):
    id: str
    session_id: str
    file_url: str
    file_size: int
    duration_seconds: Optional[int] = None
    mime_type: Optional[str] = None
    created_at: datetime


class LiveAttendeeResponse(BaseModel):
    user_id: str
    user_name: Optional[str] = None
    joined_at: datetime
    left_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None


class LiveAnalyticsResponse(BaseModel):
    session_id: str
    total_joins: int
    unique_viewers: int
    current_viewer_count: int
    peak_viewer_count: int
    average_watch_seconds: Optional[int] = None
    attendees: list[LiveAttendeeResponse]
