"""News Feed router — posts, likes, comments.

Endpoints
---------
  POST   /feed/posts                         — create a post
  GET    /feed/posts                         — cursor-paginated feed for caller's org
  GET    /feed/posts/{id}                    — single post
  DELETE /feed/posts/{id}                    — author-only soft delete
  POST   /feed/posts/{id}/like               — idempotent toggle (body optional)
  DELETE /feed/posts/{id}/like               — remove like
  GET    /feed/posts/{id}/comments           — list comments
  POST   /feed/posts/{id}/comments           — add comment
  DELETE /feed/posts/{id}/comments/{cid}     — author-only soft delete

Media uploads go through the shared ``/messenger/upload`` endpoint — both
modules write to the same ``/uploads/<org_id>/`` folder.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.ratelimit import rate_limit_auth
from app.models.user import User
from app.models.feed import Post, PostLike, PostComment
from app.schemas.feed import (
    PostCreate, PostResponse,
    CommentCreate, CommentResponse,
    LikeToggleResponse,
)

logger = logging.getLogger("extracare.feed")
router = APIRouter(prefix="/feed", tags=["News Feed"])


# ── Helpers ────────────────────────────────────────────────────────────────

async def _load_post(db: AsyncSession, post_id: str, org_id: str) -> Post:
    row = (await db.execute(
        select(Post).where(
            Post.id == post_id,
            Post.org_id == org_id,
            Post.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"Post not found for id: {post_id}")
    return row


async def _counts_for(db: AsyncSession, post_id: str, user_id: str) -> tuple[int, int, bool]:
    """Return (like_count, comment_count, liked_by_me) for a single post.

    Three cheap queries; acceptable at current scale. Feed listings batch
    this via subqueries to avoid N+1 — see ``list_posts`` below.
    """
    like_count = int((await db.execute(
        select(func.count()).select_from(PostLike).where(PostLike.post_id == post_id)
    )).scalar() or 0)
    comment_count = int((await db.execute(
        select(func.count()).select_from(PostComment).where(
            PostComment.post_id == post_id,
            PostComment.is_deleted == False,
        )
    )).scalar() or 0)
    liked = (await db.execute(
        select(PostLike.id).where(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id,
        ).limit(1)
    )).scalar_one_or_none() is not None
    return (like_count, comment_count, liked)


def _to_post_response(p: Post, *, like_count: int, comment_count: int, liked_by_me: bool) -> PostResponse:
    return PostResponse(
        id=p.id,
        org_id=p.org_id,
        user_id=p.user_id,
        author_name=(p.user.full_name if p.user else None),
        author_avatar_url=(getattr(p.user, "avatar_url", None) if p.user else None),
        content=p.content,
        media_url=p.media_url,
        media_type=p.media_type,
        like_count=like_count,
        comment_count=comment_count,
        liked_by_me=liked_by_me,
        created_at=p.created_at,
    )


def _to_comment_response(c: PostComment) -> CommentResponse:
    return CommentResponse(
        id=c.id,
        post_id=c.post_id,
        user_id=c.user_id,
        author_name=(c.user.full_name if c.user else None),
        author_avatar_url=(getattr(c.user, "avatar_url", None) if c.user else None),
        content=c.content,
        created_at=c.created_at,
    )


# ── Posts ──────────────────────────────────────────────────────────────────

@router.post("/posts", response_model=PostResponse, status_code=201, dependencies=[Depends(rate_limit_auth("feed_post"))])
async def create_post(
    data: PostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not data.content and not data.media_url:
        raise HTTPException(status_code=422, detail="content: post must have text or media")
    if data.media_url and not data.media_type:
        raise HTTPException(status_code=422, detail="media_type: required when media_url is set")

    post = Post(
        org_id=current_user.org_id,
        user_id=current_user.id,
        content=data.content,
        media_url=data.media_url,
        media_type=data.media_type,
    )
    db.add(post)
    await db.flush()
    await db.refresh(post)
    logger.info("feed.post.create user=%s org=%s has_media=%s", current_user.id, current_user.org_id, bool(data.media_url))
    return _to_post_response(post, like_count=0, comment_count=0, liked_by_me=False)


@router.get("/posts", response_model=list[PostResponse])
async def list_posts(
    limit: int = Query(default=20, ge=1, le=50),
    before: Optional[datetime] = Query(default=None, description="Return posts strictly older than this ISO timestamp."),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Reverse-chronological feed for the caller's org.

    Batched counts (subquery per aggregate) keep this O(posts) — no N+1.
    """
    q = select(Post).where(
        Post.org_id == current_user.org_id,
        Post.is_deleted == False,
    )
    if before:
        q = q.where(Post.created_at < before)
    q = q.order_by(desc(Post.created_at)).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    if not rows:
        return []

    post_ids = [p.id for p in rows]

    # Three batched queries for counts / liked-by-me; avoids one query per post.
    like_rows = (await db.execute(
        select(PostLike.post_id, func.count())
        .where(PostLike.post_id.in_(post_ids))
        .group_by(PostLike.post_id)
    )).all()
    likes: dict[str, int] = {pid: c for pid, c in like_rows}

    comment_rows = (await db.execute(
        select(PostComment.post_id, func.count())
        .where(
            PostComment.post_id.in_(post_ids),
            PostComment.is_deleted == False,
        )
        .group_by(PostComment.post_id)
    )).all()
    comments: dict[str, int] = {pid: c for pid, c in comment_rows}

    mine_rows = (await db.execute(
        select(PostLike.post_id).where(
            PostLike.post_id.in_(post_ids),
            PostLike.user_id == current_user.id,
        )
    )).scalars().all()
    mine: set[str] = set(mine_rows)

    return [
        _to_post_response(
            p,
            like_count=likes.get(p.id, 0),
            comment_count=comments.get(p.id, 0),
            liked_by_me=p.id in mine,
        )
        for p in rows
    ]


@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    post = await _load_post(db, post_id, current_user.org_id)
    like_count, comment_count, liked = await _counts_for(db, post.id, current_user.id)
    return _to_post_response(post, like_count=like_count, comment_count=comment_count, liked_by_me=liked)


@router.delete("/posts/{post_id}", status_code=204)
async def delete_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    post = await _load_post(db, post_id, current_user.org_id)
    if post.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the author can delete this post.")
    post.is_deleted = True
    post.deleted_at = datetime.utcnow()
    await db.flush()


# ── Likes ──────────────────────────────────────────────────────────────────

@router.post("/posts/{post_id}/like", response_model=LikeToggleResponse)
async def like_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Idempotent like — calling twice leaves the post liked exactly once."""
    post = await _load_post(db, post_id, current_user.org_id)

    existing = (await db.execute(
        select(PostLike).where(
            PostLike.post_id == post.id,
            PostLike.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not existing:
        db.add(PostLike(post_id=post.id, user_id=current_user.id))
        await db.flush()

    count = int((await db.execute(
        select(func.count()).select_from(PostLike).where(PostLike.post_id == post.id)
    )).scalar() or 0)
    return LikeToggleResponse(liked=True, like_count=count)


@router.delete("/posts/{post_id}/like", response_model=LikeToggleResponse)
async def unlike_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    post = await _load_post(db, post_id, current_user.org_id)

    existing = (await db.execute(
        select(PostLike).where(
            PostLike.post_id == post.id,
            PostLike.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.flush()

    count = int((await db.execute(
        select(func.count()).select_from(PostLike).where(PostLike.post_id == post.id)
    )).scalar() or 0)
    return LikeToggleResponse(liked=False, like_count=count)


# ── Comments ───────────────────────────────────────────────────────────────

@router.get("/posts/{post_id}/comments", response_model=list[CommentResponse])
async def list_comments(
    post_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _load_post(db, post_id, current_user.org_id)
    rows = (await db.execute(
        select(PostComment).where(
            PostComment.post_id == post_id,
            PostComment.is_deleted == False,
        ).order_by(PostComment.created_at.asc()).limit(limit)
    )).scalars().all()
    return [_to_comment_response(c) for c in rows]


@router.post("/posts/{post_id}/comments", response_model=CommentResponse, status_code=201, dependencies=[Depends(rate_limit_auth("feed_post"))])
async def create_comment(
    post_id: str,
    data: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    post = await _load_post(db, post_id, current_user.org_id)
    c = PostComment(
        org_id=current_user.org_id,
        post_id=post.id,
        user_id=current_user.id,
        content=data.content,
    )
    db.add(c)
    await db.flush()
    await db.refresh(c)
    return _to_comment_response(c)


@router.delete("/posts/{post_id}/comments/{comment_id}", status_code=204)
async def delete_comment(
    post_id: str,
    comment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _load_post(db, post_id, current_user.org_id)
    c = (await db.execute(
        select(PostComment).where(
            PostComment.id == comment_id,
            PostComment.post_id == post_id,
            PostComment.org_id == current_user.org_id,
            PostComment.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Comment not found.")
    if c.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the author can delete this comment.")
    c.is_deleted = True
    c.deleted_at = datetime.utcnow()
    await db.flush()
