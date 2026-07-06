"""Schemas for Operations (Batch 6, non-financial): Calendar, Facility, Visitor."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


FACILITY_STATUSES = {"available", "maintenance", "unavailable"}
BOOKING_STATUSES = {"booked", "cancelled"}
VISITOR_STATUSES = {"signed_in", "signed_out"}


# ── Calendar ────────────────────────────────────────────────────────────────────

class CalendarEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    start_at: datetime
    end_at: Optional[datetime] = None
    all_day: bool = False
    category: Optional[str] = None
    location: Optional[str] = None
    audience: Optional[str] = "school"


class CalendarEventUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    all_day: Optional[bool] = None
    category: Optional[str] = None
    location: Optional[str] = None
    audience: Optional[str] = None


class CalendarEventResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    start_at: datetime
    end_at: Optional[datetime]
    all_day: bool
    category: Optional[str]
    location: Optional[str]
    audience: Optional[str]
    created_at: datetime
    org_id: str


class CalendarEventListResponse(BaseModel):
    items: list[CalendarEventResponse]
    total: int
    page: int
    page_size: int


# ── Facility ────────────────────────────────────────────────────────────────────

class FacilityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    type: Optional[str] = None
    capacity: Optional[int] = Field(default=None, ge=0)
    location: Optional[str] = None
    status: str = "available"
    notes: Optional[str] = None


class FacilityUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    type: Optional[str] = None
    capacity: Optional[int] = Field(default=None, ge=0)
    location: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class FacilityResponse(BaseModel):
    id: str
    name: str
    type: Optional[str]
    capacity: Optional[int]
    location: Optional[str]
    status: str
    notes: Optional[str]
    is_active: bool
    created_at: datetime
    org_id: str


class FacilityListResponse(BaseModel):
    items: list[FacilityResponse]
    total: int
    page: int
    page_size: int


class BookingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    purpose: Optional[str] = None
    start_at: datetime
    end_at: datetime


class BookingResponse(BaseModel):
    id: str
    facility_id: str
    title: str
    purpose: Optional[str]
    start_at: datetime
    end_at: datetime
    status: str
    booked_by: Optional[str]
    created_at: datetime
    org_id: str


# ── Visitor (safeguarding) ──────────────────────────────────────────────────────

class VisitorCreate(BaseModel):
    visitor_name: str = Field(min_length=1, max_length=200)
    organization: Optional[str] = None
    purpose: Optional[str] = None
    host_name: Optional[str] = None
    phone: Optional[str] = None
    badge_no: Optional[str] = None


class VisitorResponse(BaseModel):
    id: str
    visitor_name: str
    organization: Optional[str]
    purpose: Optional[str]
    host_name: Optional[str]
    phone: Optional[str]
    badge_no: Optional[str]
    sign_in_at: Optional[datetime]
    sign_out_at: Optional[datetime]
    status: str
    recorded_by: Optional[str]
    created_at: datetime
    org_id: str


class VisitorListResponse(BaseModel):
    items: list[VisitorResponse]
    total: int
    page: int
    page_size: int


class CollectionCreate(BaseModel):
    student_id: str
    collector_name: str = Field(min_length=1, max_length=200)
    relationship_to_student: Optional[str] = None
    authorized_by: str          # REQUIRED — who authorised the pickup
    collected_at: Optional[datetime] = None
    notes: Optional[str] = None


class CollectionResponse(BaseModel):
    id: str
    student_id: str
    student_name: Optional[str]
    collector_name: str
    relationship_to_student: Optional[str]
    authorized_by: str
    authorized_by_name: Optional[str]
    collected_at: Optional[datetime]
    notes: Optional[str]
    recorded_by: Optional[str]
    created_at: datetime
    org_id: str


class CollectionListResponse(BaseModel):
    items: list[CollectionResponse]
    total: int
    page: int
    page_size: int
