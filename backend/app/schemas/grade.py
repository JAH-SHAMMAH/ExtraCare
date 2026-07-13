"""Grade publishing schema — bulk publish/unpublish for the Result Publish helper."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel


class GradePublish(BaseModel):
    term: str
    status: Literal["published", "draft"]
    class_id: Optional[str] = None
    exam_id: Optional[str] = None
    subject_id: Optional[str] = None


class ReportMetaUpdate(BaseModel):
    """Human-authored report fields (School Reports R1) — the parts of a report
    card not derivable from grades. All optional (partial upsert)."""
    class_teacher_comment: Optional[str] = None
    head_teacher_comment: Optional[str] = None
    attendance_present: Optional[int] = None
    attendance_total: Optional[int] = None
    next_term_begins: Optional[date] = None
