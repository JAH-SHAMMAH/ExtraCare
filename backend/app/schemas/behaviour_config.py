"""Schemas for the Behaviour Tracker admin cluster: category/sub-category
taxonomy, conduct-level bands, and per-org settings."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Categories ("Manage behaviourTracker") ───────────────────────────────────

class CategoryCreate(BaseModel):
    name: str
    type: str = "positive"
    default_points: Optional[int] = None
    description: Optional[str] = None
    position: int = 0
    is_active: bool = True


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    default_points: Optional[int] = None
    description: Optional[str] = None
    position: Optional[int] = None
    is_active: Optional[bool] = None


class CategoryResponse(_OrmBase):
    id: str
    name: str
    type: str
    default_points: Optional[int]
    description: Optional[str]
    position: int
    is_active: bool
    org_id: str
    created_at: datetime


# ── Sub-categories ("Sub-manage behaviourTracker") ───────────────────────────

class SubCategoryCreate(BaseModel):
    category_id: str
    name: str
    default_points: Optional[int] = None
    position: int = 0
    is_active: bool = True


class SubCategoryUpdate(BaseModel):
    category_id: Optional[str] = None
    name: Optional[str] = None
    default_points: Optional[int] = None
    position: Optional[int] = None
    is_active: Optional[bool] = None


class SubCategoryResponse(_OrmBase):
    id: str
    category_id: str
    name: str
    default_points: Optional[int]
    position: int
    is_active: bool
    org_id: str
    created_at: datetime


# ── Levels ("Manage behaviour levels") ───────────────────────────────────────

class LevelCreate(BaseModel):
    name: str
    min_points: int
    max_points: Optional[int] = None
    colour: Optional[str] = None
    description: Optional[str] = None
    position: int = 0
    is_active: bool = True


class LevelUpdate(BaseModel):
    name: Optional[str] = None
    min_points: Optional[int] = None
    max_points: Optional[int] = None
    colour: Optional[str] = None
    description: Optional[str] = None
    position: Optional[int] = None
    is_active: Optional[bool] = None


class LevelResponse(_OrmBase):
    id: str
    name: str
    min_points: int
    max_points: Optional[int]
    colour: Optional[str]
    description: Optional[str]
    position: int
    is_active: bool
    org_id: str
    created_at: datetime


# ── Settings ("BehaviourTracker settings") ───────────────────────────────────

class SettingsUpdate(BaseModel):
    default_points: Optional[int] = Field(default=None)
    visible_to_students: Optional[bool] = None
    visible_to_parents: Optional[bool] = None
    auto_derive_levels: Optional[bool] = None


class SettingsResponse(_OrmBase):
    id: str
    default_points: int
    visible_to_students: bool
    visible_to_parents: bool
    auto_derive_levels: bool
    org_id: str
