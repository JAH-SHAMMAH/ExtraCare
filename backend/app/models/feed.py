"""News Feed models — posts, likes, comments.

Internal Facebook-style feed, scoped per org. Every row carries ``org_id``
so a cross-tenant leak is impossible even if a query forgets to filter.

* ``Post`` — text + optional media URL. Media uploads reuse the messenger
  upload endpoint (same ``/uploads/`` static mount) so we don't need two
  file pipelines.
* ``PostLike`` — unique per (post, user). The API is idempotent: liking an
  already-liked post is a no-op, unliking an un-liked post is a no-op.
* ``PostComment`` — flat list under a post (no threading yet — add a
  ``parent_id`` later if nesting is ever needed).

Counts (likes/comments) are computed at list time via subqueries rather
than stored on ``Post`` so we don't have to worry about drift from a
partial failure. Cheap at small scale; swap to denormalised counters if
the feed ever exceeds a few thousand posts per org.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, Integer, ForeignKey, Boolean, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin

# Attachment kinds a post can carry. "image"/"video" render inline; "file" is a
# document (rendered as a "View Document" card); "link" is an external URL card.
ATTACHMENT_KINDS = ("image", "video", "file", "link")


class Post(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "feed_posts"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=True)
    # Legacy single-attachment columns — kept for existing posts. New posts use
    # the ``attachments`` relationship (feed_post_attachments), which supports
    # multiple items of mixed kinds (image/video/file/link).
    media_url = Column(String(500), nullable=True)
    media_type = Column(String(20), nullable=True)  # "image" | "video"

    user = relationship("User", lazy="joined")
    likes = relationship("PostLike", back_populates="post", cascade="all, delete-orphan", passive_deletes=True)
    comments = relationship("PostComment", back_populates="post", cascade="all, delete-orphan", passive_deletes=True)
    attachments = relationship(
        "PostAttachment", back_populates="post", cascade="all, delete-orphan",
        passive_deletes=True, order_by="PostAttachment.sort_order", lazy="selectin",
    )
    audiences = relationship(
        "PostAudience", back_populates="post", cascade="all, delete-orphan",
        passive_deletes=True, lazy="selectin",
    )

    __table_args__ = (
        # Feed query: org_id + not deleted, newest first.
        Index("ix_feed_post_org_created", "org_id", "created_at"),
    )


class PostAttachment(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "feed_post_attachments"

    post_id = Column(String(36), ForeignKey("feed_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(20), nullable=False)              # one of ATTACHMENT_KINDS
    url = Column(String(1000), nullable=False)             # media URL (/uploads/…) or external link
    filename = Column(String(255), nullable=True)          # original name — the "View Document" label
    mime_type = Column(String(150), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    title = Column(String(300), nullable=True)             # link card title (or doc display name)
    sort_order = Column(Integer, nullable=False, default=0)

    post = relationship("Post", back_populates="attachments")

    __table_args__ = (
        Index("ix_feed_attachment_post", "post_id", "sort_order"),
    )


class PostAudience(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Who a post is targeted at. NO rows for a post = public (everyone in the
    org). Each row narrows the audience to a role (kind="role", ref=role slug) or
    a specific user (kind="user", ref=user id). The author always sees their own
    post regardless. Membership uses a user's ASSIGNED roles (not the active-role
    'View as' scope), so switching personas never changes who a post reached."""
    __tablename__ = "feed_post_audiences"

    post_id = Column(String(36), ForeignKey("feed_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(10), nullable=False)    # "role" | "user"
    ref = Column(String(100), nullable=False)     # role slug or user id

    post = relationship("Post", back_populates="audiences")

    __table_args__ = (
        Index("ix_feed_audience_post", "post_id"),
        UniqueConstraint("post_id", "kind", "ref", name="uq_post_audience_post_kind_ref"),
    )


class PostLike(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "feed_post_likes"

    post_id = Column(String(36), ForeignKey("feed_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    post = relationship("Post", back_populates="likes")

    __table_args__ = (
        # One like per user per post — the DB enforces idempotency.
        UniqueConstraint("post_id", "user_id", name="uq_post_like_post_user"),
    )


class PostComment(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "feed_post_comments"

    post_id = Column(String(36), ForeignKey("feed_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)

    user = relationship("User", lazy="joined")
    post = relationship("Post", back_populates="comments")

    __table_args__ = (
        Index("ix_feed_comment_post_created", "post_id", "created_at"),
    )
