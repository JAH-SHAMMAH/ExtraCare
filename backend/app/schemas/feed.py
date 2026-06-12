"""Pydantic schemas for the News Feed module."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, field_validator


def _empty_to_none(v):
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


class PostCreate(BaseModel):
    content: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[Literal["image", "video"]] = None

    @field_validator("content", mode="before")
    @classmethod
    def _blank_content(cls, v):
        return _empty_to_none(v)

    @field_validator("media_url", mode="before")
    @classmethod
    def _blank_url(cls, v):
        return _empty_to_none(v)


class PostResponse(BaseModel):
    id: str
    org_id: str
    user_id: str
    author_name: Optional[str] = None
    author_avatar_url: Optional[str] = None

    content: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None

    like_count: int
    comment_count: int
    liked_by_me: bool

    created_at: datetime


class CommentCreate(BaseModel):
    content: str

    @field_validator("content", mode="before")
    @classmethod
    def _blank(cls, v):
        if isinstance(v, str) and v.strip() == "":
            # Reject blank up-front so the 422 arrives before hitting the DB.
            raise ValueError("content must not be blank")
        return v


class CommentResponse(BaseModel):
    id: str
    post_id: str
    user_id: str
    author_name: Optional[str] = None
    author_avatar_url: Optional[str] = None
    content: str
    created_at: datetime


class LikeToggleResponse(BaseModel):
    liked: bool
    like_count: int
