"""Grade publishing schema — bulk publish/unpublish for the Result Publish helper."""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel


class GradePublish(BaseModel):
    term: str
    status: Literal["published", "draft"]
    class_id: Optional[str] = None
    exam_id: Optional[str] = None
    subject_id: Optional[str] = None
