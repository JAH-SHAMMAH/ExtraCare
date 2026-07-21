"""Schemas for PIM extras — Staff Account Numbers + Staff Transfer Log."""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Staff Account Numbers (reuses HRProfile bank fields) ──────────────────────

class AccountRow(BaseModel):
    user_id: str
    full_name: Optional[str]
    email: Optional[str]
    staff_id: Optional[str]
    job_title: Optional[str]
    department: Optional[str]
    bank_name: Optional[str]
    bank_account_name: Optional[str]
    bank_account_number: Optional[str]


class AccountUpdate(BaseModel):
    bank_name: Optional[str] = Field(default=None, max_length=120)
    bank_account_name: Optional[str] = Field(default=None, max_length=150)
    bank_account_number: Optional[str] = Field(default=None, max_length=40)


# ── Staff Transfer Log ────────────────────────────────────────────────────────

class TransferCreate(BaseModel):
    staff_user_id: str
    to_department: str = Field(min_length=1, max_length=255)
    to_unit: Optional[str] = Field(default=None, max_length=150)
    effective_date: Optional[date] = None
    reason: Optional[str] = None


class TransferResponse(BaseModel):
    id: str
    staff_user_id: str
    staff_name: Optional[str] = None
    from_department: Optional[str]
    to_department: str
    to_unit: Optional[str]
    effective_date: Optional[date]
    reason: Optional[str]
    created_at: datetime
    org_id: str
