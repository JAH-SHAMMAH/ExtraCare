"""Teacher rating schema — the student→teacher 1–5 star feedback surface."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class RatingCreate(BaseModel):
    teacher_id: str
    student_id: str                 # student's uuid OR their human student_id code
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None
    subject_id: Optional[str] = None
    term: Optional[str] = None
