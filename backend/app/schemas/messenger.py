"""Pydantic schemas for the Messenger module."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from app.models.messenger import ConversationKind, MessageType


def _empty_to_none(v):
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


# ── Conversations ───────────────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    """Client asks either for a DM with ``peer_id`` or a group (title + members).

    ``kind=global`` is never created by clients — the org's global room is
    auto-created on demand when listing or posting.
    """
    kind: ConversationKind = ConversationKind.DIRECT
    peer_id: Optional[str] = None           # required for kind=direct
    title: Optional[str] = None             # optional for kind=group
    member_ids: Optional[list[str]] = None  # required for kind=group

    @field_validator("title", mode="before")
    @classmethod
    def _blank_title(cls, v):
        return _empty_to_none(v)


class MemberSummary(BaseModel):
    id: str
    full_name: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None


class ConversationResponse(BaseModel):
    id: str
    org_id: str
    kind: ConversationKind
    title: Optional[str] = None
    members: list[MemberSummary] = []
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None
    created_at: datetime


# ── Messages ────────────────────────────────────────────────────────────────

class MessageCreate(BaseModel):
    conversation_id: str
    type: MessageType = MessageType.TEXT
    content: Optional[str] = None
    file_url: Optional[str] = None

    @field_validator("content", mode="before")
    @classmethod
    def _blank_content(cls, v):
        return _empty_to_none(v)

    @field_validator("file_url", mode="before")
    @classmethod
    def _blank_url(cls, v):
        return _empty_to_none(v)


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    org_id: str
    sender_id: str
    sender_name: Optional[str] = None
    sender_avatar_url: Optional[str] = None
    type: MessageType
    content: Optional[str] = None
    file_url: Optional[str] = None
    created_at: datetime


# ── Uploads ─────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    file_url: str
    type: MessageType
    size_bytes: int
    filename: str
