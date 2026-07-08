"""Question Bank schemas — reusable CBT questions + test composition."""
from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


_DIFFICULTY = ("easy", "medium", "hard")
_TYPES = ("mcq", "true_false", "short_answer", "long_answer")


class BankItemCreate(BaseModel):
    question_text: str = Field(min_length=1)
    question_type: str = "mcq"
    subject_id: Optional[str] = None
    topic: Optional[str] = Field(default=None, max_length=150)
    difficulty: str = "medium"
    options: Optional[list[dict[str, Any]]] = None
    correct_answer: Optional[str] = None
    points: float = Field(default=1.0, ge=0)


class BankItemUpdate(BaseModel):
    question_text: Optional[str] = Field(default=None, min_length=1)
    question_type: Optional[str] = None
    subject_id: Optional[str] = None
    topic: Optional[str] = Field(default=None, max_length=150)
    difficulty: Optional[str] = None
    options: Optional[list[dict[str, Any]]] = None
    correct_answer: Optional[str] = None
    points: Optional[float] = Field(default=None, ge=0)


class ComposeFromBank(BaseModel):
    question_ids: list[str] = Field(min_length=1)
