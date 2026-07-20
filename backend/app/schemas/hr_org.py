"""Schemas for Organization Structure (org units)."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class OrgUnitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    unit_type: Optional[str] = Field(default=None, max_length=40)
    parent_id: Optional[str] = None
    head_user_id: Optional[str] = None
    description: Optional[str] = None
    position: int = 0


class OrgUnitUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    unit_type: Optional[str] = Field(default=None, max_length=40)
    parent_id: Optional[str] = None   # null clears the parent (moves to root)
    head_user_id: Optional[str] = None
    description: Optional[str] = None
    position: Optional[int] = None


class OrgUnitResponse(BaseModel):
    id: str
    name: str
    unit_type: Optional[str]
    parent_id: Optional[str]
    head_user_id: Optional[str]
    head_name: Optional[str] = None
    description: Optional[str]
    position: int
    created_at: datetime
    org_id: str
