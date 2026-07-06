"""Schemas for the CONFIDENTIAL Medicals surface (Batch 4).

Kept separate from pastoral on purpose — this data is gated by the dedicated
``medical:*`` namespace (org_admin + nurse only). org_id pinned server-side.
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


MEDICAL_TYPES = {"visit", "allergy", "medication", "immunization", "condition", "note"}
SEVERITIES = {"low", "medium", "high"}


class MedicalRecordCreate(BaseModel):
    student_id: str
    record_type: str = "visit"
    title: Optional[str] = None
    description: Optional[str] = None
    treatment: Optional[str] = None
    severity: Optional[str] = None
    recorded_on: Optional[date] = None
    follow_up_on: Optional[date] = None


class MedicalRecordUpdate(BaseModel):
    record_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    treatment: Optional[str] = None
    severity: Optional[str] = None
    recorded_on: Optional[date] = None
    follow_up_on: Optional[date] = None


class MedicalRecordResponse(BaseModel):
    id: str
    student_id: str
    student_name: Optional[str]
    record_type: str
    title: Optional[str]
    description: Optional[str]
    treatment: Optional[str]
    severity: Optional[str]
    recorded_on: Optional[date]
    follow_up_on: Optional[date]
    recorded_by: Optional[str]
    created_at: datetime
    org_id: str


class MedicalRecordListResponse(BaseModel):
    items: list[MedicalRecordResponse]
    total: int
    page: int
    page_size: int
