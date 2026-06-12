"""Messenger models — conversations and messages.

Three entities model the chat surface:

* ``Conversation`` — a container. Three flavours:
    - ``kind=global`` — exactly one per org, all users are implicit members.
    - ``kind=direct`` — 1-to-1 between two users, deduplicated by pair.
    - ``kind=group`` — arbitrary subset of org users (future-ready; API
      already supports it).

* ``ConversationMember`` — join row for direct/group conversations. Empty
  for ``kind=global`` so we don't have to write N×members on org signup.

* ``Message`` — text, image, or video. Media is uploaded separately and
  the public URL is stored in ``file_url``.

Every row is scoped by ``org_id`` and must match the sender's org. No
cross-tenant joins possible; every query pins ``org_id`` explicitly.
"""
from __future__ import annotations

import enum

from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Enum, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class ConversationKind(str, enum.Enum):
    GLOBAL = "global"
    DIRECT = "direct"
    GROUP = "group"


class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"


class Conversation(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "conversations"

    kind = Column(Enum(ConversationKind), nullable=False, default=ConversationKind.DIRECT, index=True)
    title = Column(String(120), nullable=True)

    # Only set for ``kind=direct`` — lets us dedupe "pair a,b" ↔ "pair b,a"
    # with a single unique index. Format: sorted("user_a_id:user_b_id").
    dm_pair_key = Column(String(80), nullable=True, index=True)

    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    members = relationship(
        "ConversationMember",
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("org_id", "dm_pair_key", name="uq_conversation_org_dm_pair"),
        Index("ix_conversation_org_kind", "org_id", "kind"),
    )


class ConversationMember(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "conversation_members"

    conversation_id = Column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    conversation = relationship("Conversation", back_populates="members")
    user = relationship("User", lazy="joined")

    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="uq_member_conv_user"),
    )


class Message(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "messages"

    conversation_id = Column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    type = Column(Enum(MessageType), nullable=False, default=MessageType.TEXT)
    content = Column(Text, nullable=True)
    file_url = Column(String(500), nullable=True)

    is_deleted = Column(Boolean, default=False, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User", lazy="joined")

    __table_args__ = (
        # Primary access pattern: list by conversation, newest first.
        Index("ix_message_conv_created", "conversation_id", "created_at"),
    )
