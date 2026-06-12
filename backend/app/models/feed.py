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

from sqlalchemy import Column, String, Text, ForeignKey, Boolean, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


class Post(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "feed_posts"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=True)
    # Single URL for now — the frontend only attaches one at a time. Extend
    # to a JSON list when multi-image posts become a real requirement.
    media_url = Column(String(500), nullable=True)
    media_type = Column(String(20), nullable=True)  # "image" | "video"

    user = relationship("User", lazy="joined")
    likes = relationship("PostLike", back_populates="post", cascade="all, delete-orphan", passive_deletes=True)
    comments = relationship("PostComment", back_populates="post", cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        # Feed query: org_id + not deleted, newest first.
        Index("ix_feed_post_org_created", "org_id", "created_at"),
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
