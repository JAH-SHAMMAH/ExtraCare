"""Pydantic schemas for the News Feed module."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, field_validator, model_validator


def _empty_to_none(v):
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


AttachmentKind = Literal["image", "video", "file", "link"]


class AttachmentIn(BaseModel):
    kind: AttachmentKind
    url: str                                   # /uploads/… (uploaded) or an external link
    filename: Optional[str] = None             # original name — the "View Document" label
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    title: Optional[str] = None                # link card title (or doc display name)

    @field_validator("url", mode="before")
    @classmethod
    def _url_required(cls, v):
        v = _empty_to_none(v)
        if not v:
            raise ValueError("attachment url must not be blank")
        return v

    @model_validator(mode="after")
    def _safe_link_scheme(self):
        # A link is rendered as a clickable <a href>; only allow http(s) so a
        # javascript:/data: URL can't become a stored-XSS-on-click. Uploaded
        # media (image/video/file) is a server-issued /uploads/… path.
        if self.kind == "link" and not re.match(r"^https?://", self.url, re.I):
            raise ValueError("link url must start with http:// or https://")
        return self


class AttachmentOut(BaseModel):
    id: str
    kind: str
    url: str
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    title: Optional[str] = None


class PostCreate(BaseModel):
    content: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[Literal["image", "video"]] = None
    attachments: list[AttachmentIn] = []
    # Publish-To targeting. Both empty = public (everyone in the org). Otherwise
    # the post reaches the listed roles (by slug) and/or specific users (by id),
    # plus the author. Unknown role slugs simply never match; user ids are
    # validated against the caller's org.
    audience_roles: list[str] = []
    audience_user_ids: list[str] = []

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
    attachments: list[AttachmentOut] = []
    # Targeting (empty both = public). Returned so the author/UI can show + edit
    # who a post reached.
    audience_roles: list[str] = []
    audience_user_ids: list[str] = []

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
