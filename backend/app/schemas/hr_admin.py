"""Schemas for the HR Admin managed lists (Phase 1)."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class HrItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    code: Optional[str] = Field(default=None, max_length=40)
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class HrItemUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    code: Optional[str] = Field(default=None, max_length=40)
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class HrItemResponse(BaseModel):
    id: str
    list_type: str
    name: str
    code: Optional[str]
    description: Optional[str]
    sort_order: int
    is_active: bool
    created_at: datetime
    org_id: str


class HrListSummary(BaseModel):
    """One row of the Admin overview — a list's key, label and live item count."""
    list_type: str
    label: str
    count: int
