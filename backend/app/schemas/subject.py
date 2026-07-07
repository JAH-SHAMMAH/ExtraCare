"""Subject (curriculum) schemas — the Subject Management CRUD surface.

The frontend captures a free-text teacher name (not a linked user), plus a
department and credit hours, so those are first-class here. `class_ids` is
accepted/returned for the frontend type but not persisted yet (no subject↔class
join table); it round-trips as an empty list until that linkage is built.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: Optional[str] = Field(default=None, max_length=20)
    department: Optional[str] = Field(default=None, max_length=100)
    credit_hours: Optional[int] = Field(default=1, ge=0)
    teacher_name: Optional[str] = Field(default=None, max_length=120)
    teacher_id: Optional[str] = None
    is_active: Optional[bool] = True


class SubjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    code: Optional[str] = Field(default=None, max_length=20)
    department: Optional[str] = Field(default=None, max_length=100)
    credit_hours: Optional[int] = Field(default=None, ge=0)
    teacher_name: Optional[str] = Field(default=None, max_length=120)
    teacher_id: Optional[str] = None
    is_active: Optional[bool] = None
