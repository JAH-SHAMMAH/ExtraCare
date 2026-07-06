"""Request schemas for class management (GET/POST/PATCH /school/classes).

The frontend `SchoolClass` shape uses friendlier names than the ORM columns:
  grade_level -> SchoolClass.level, capacity -> max_capacity,
  class_teacher_id -> teacher_id. These schemas accept the FRONTEND names; the
router maps them onto the model.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    grade_level: Optional[str] = None          # -> level
    section: Optional[str] = None
    capacity: Optional[int] = Field(default=40, ge=0)   # -> max_capacity
    academic_year: Optional[str] = None
    class_teacher_id: Optional[str] = None     # -> teacher_id
    room: Optional[str] = None


class ClassUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    grade_level: Optional[str] = None
    section: Optional[str] = None
    capacity: Optional[int] = Field(default=None, ge=0)
    academic_year: Optional[str] = None
    class_teacher_id: Optional[str] = None
    room: Optional[str] = None
