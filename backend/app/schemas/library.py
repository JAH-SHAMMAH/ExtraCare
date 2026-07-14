"""Schemas for Library Setup + Manage Reviews."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Settings (singleton per org) ──────────────────────────────────────────────

class LibrarySettingsResponse(BaseModel):
    loan_period_days: int
    max_books_per_user: int
    allow_reviews: bool
    review_needs_approval: bool
    org_id: str


class LibrarySettingsUpdate(BaseModel):
    loan_period_days: Optional[int] = Field(default=None, ge=1, le=365)
    max_books_per_user: Optional[int] = Field(default=None, ge=1, le=100)
    allow_reviews: Optional[bool] = None
    review_needs_approval: Optional[bool] = None


# ── Categories ────────────────────────────────────────────────────────────────

class LibraryCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class LibraryCategoryResponse(BaseModel):
    id: str
    name: str
    org_id: str


# ── Locations ─────────────────────────────────────────────────────────────────

class LibraryLocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    code: Optional[str] = Field(default=None, max_length=30)


class LibraryLocationResponse(BaseModel):
    id: str
    name: str
    code: Optional[str] = None
    org_id: str


# ── Reviews ───────────────────────────────────────────────────────────────────

class ReviewCreate(BaseModel):
    book_id: str
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None


class ReviewModerate(BaseModel):
    status: str   # approved | rejected | pending


class ReviewResponse(BaseModel):
    id: str
    book_id: str
    book_title: Optional[str] = None
    reviewer_id: Optional[str] = None
    reviewer_name: Optional[str] = None
    rating: int
    comment: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    org_id: str
