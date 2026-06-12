"""
Attendance schemas
===================
Request/response contracts for the event-sourced attendance layer. The
``AttendanceEventIn`` shape is the stable contract a future ZKTeco adapter
maps device punches into — keep it adapter-friendly (plain fields, no ORM).
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Any, Literal

from pydantic import BaseModel, Field


EventTypeLiteral = Literal["check_in", "check_out"]
SourceLiteral = Literal["manual", "zkteco", "import", "api"]


class AttendanceEventIn(BaseModel):
    """One check-in/out punch. ``event_time`` defaults to now if omitted.
    ``external_ref`` is the device-side id used to dedupe repeated pushes."""

    student_id: str
    event_type: EventTypeLiteral
    event_time: datetime | None = None
    source: SourceLiteral = "manual"
    external_ref: str | None = None
    device_id: str | None = None
    raw_payload: dict[str, Any] | None = None
    notes: str | None = None


class AttendanceIngestRequest(BaseModel):
    """Bulk ingestion envelope — the endpoint a future ZKTeco push targets."""

    events: list[AttendanceEventIn] = Field(min_length=1)


class ManualAttendanceIn(BaseModel):
    """Staff-recorded single check-in/out from the portal UI."""

    student_id: str
    event_type: EventTypeLiteral
    event_time: datetime | None = None
    notes: str | None = None


class IngestError(BaseModel):
    index: int
    student_id: str | None = None
    reason: str


class IngestResultOut(BaseModel):
    created: int = 0
    duplicates: int = 0
    notified: int = 0
    errors: list[IngestError] = []


class AttendanceEventOut(BaseModel):
    id: str
    student_id: str
    event_type: str
    event_time: datetime
    source: str
    device_id: str | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}


class DailyAttendanceRow(BaseModel):
    student_id: str
    student_name: str
    status: str | None = None  # present | late | absent | excused | None
    first_check_in: datetime | None = None
    last_check_out: datetime | None = None


class DailyAttendanceSummary(BaseModel):
    date: date
    present: int = 0
    late: int = 0
    absent: int = 0
    excused: int = 0
    total_students: int = 0
    rows: list[DailyAttendanceRow] = []


class MonthlyAttendanceSummary(BaseModel):
    year: int
    month: int
    present: int = 0
    late: int = 0
    absent: int = 0
    excused: int = 0
    days_recorded: int = 0
