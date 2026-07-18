"""Schemas for Manage YearGroups (the class-level taxonomy)."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class YearGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    short_code: Optional[str] = Field(default=None, max_length=20)
    category: str = "active"          # active | alumni | prospective
    is_mock: bool = False


class YearGroupUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    short_code: Optional[str] = Field(default=None, max_length=20)
    category: Optional[str] = None
    is_mock: Optional[bool] = None
    position: Optional[int] = None


class YearGroupResponse(BaseModel):
    id: str
    name: str
    short_code: Optional[str] = None
    category: str
    position: int
    is_mock: bool
    org_id: str


class ReorderRequest(BaseModel):
    ids: list[str]   # year-group ids in the desired order
