"""Exam (manual gradebook) schemas.

The frontend calls the exam's sitting date `date` (mapped to exam_date on the
model). Results are submitted as a list of per-student rows; a row with a null
score is treated as "not entered" and skipped.
"""
from __future__ import annotations

from datetime import date as _date
from typing import Optional
from pydantic import BaseModel, Field


EXAM_TYPES = {"midterm", "final", "quiz", "assignment", "practical"}
EXAM_STATUSES = {"scheduled", "in_progress", "completed", "cancelled"}


class ExamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    exam_type: str = "midterm"
    subject_id: Optional[str] = None
    class_id: Optional[str] = None
    term: Optional[str] = None
    session_year: Optional[str] = None
    date: Optional[_date] = None            # -> exam_date
    start_time: Optional[str] = Field(default=None, max_length=10)
    end_time: Optional[str] = Field(default=None, max_length=10)
    total_marks: Optional[float] = Field(default=100, gt=0)
    pass_marks: Optional[float] = Field(default=40, ge=0)
    status: Optional[str] = None           # defaults to "scheduled"


class ExamUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    exam_type: Optional[str] = None
    subject_id: Optional[str] = None
    class_id: Optional[str] = None
    term: Optional[str] = None
    session_year: Optional[str] = None
    date: Optional[_date] = None
    start_time: Optional[str] = Field(default=None, max_length=10)
    end_time: Optional[str] = Field(default=None, max_length=10)
    total_marks: Optional[float] = Field(default=None, gt=0)
    pass_marks: Optional[float] = Field(default=None, ge=0)
    status: Optional[str] = None


class ExamResultRow(BaseModel):
    student_id: str
    score: Optional[float] = Field(default=None, ge=0)
    remarks: Optional[str] = None
