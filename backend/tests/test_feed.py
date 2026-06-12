"""Tests for the News Feed module.

Covers the REST surface — create/list/delete posts, idempotent likes, and
comments — plus tenant isolation. The router is a thin wrapper over
SQLAlchemy, so exercising the handlers directly (as the messenger suite
does) gives us full coverage without spinning up an HTTP client.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.organization import Organization, IndustryType
from app.routers.feed import (
    create_post, list_posts, get_post, delete_post,
    like_post, unlike_post,
    list_comments, create_comment, delete_comment,
)
from app.schemas.feed import PostCreate, CommentCreate


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def second_user(db, org) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email="peer@example.com",
        full_name="Peer Two",
        status=UserStatus.ACTIVE,
        org_id=org.id,
    )
    db.add(u)
    await db.commit()
    return u


@pytest_asyncio.fixture
async def other_org(db) -> Organization:
    o = Organization(
        id=str(uuid.uuid4()),
        name="Other Org",
        slug=f"other-{uuid.uuid4().hex[:8]}",
        industry=IndustryType.SCHOOL,
        modules_enabled=["school"],
    )
    db.add(o)
    await db.commit()
    return o


@pytest_asyncio.fixture
async def other_org_user(db, other_org) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email="outsider@example.com",
        full_name="Other Org User",
        status=UserStatus.ACTIVE,
        org_id=other_org.id,
    )
    db.add(u)
    await db.commit()
    return u


# ── Create / validate ─────────────────────────────────────────────────────────

async def test_create_text_post(db, teacher):
    post = await create_post(
        data=PostCreate(content="Welcome to the feed!"),
        db=db, current_user=teacher,
    )
    assert post.content == "Welcome to the feed!"
    assert post.user_id == teacher.id
    assert post.org_id == teacher.org_id
    assert post.like_count == 0
    assert post.comment_count == 0
    assert post.liked_by_me is False


async def test_create_media_post(db, teacher):
    post = await create_post(
        data=PostCreate(media_url="/uploads/org/a.png", media_type="image"),
        db=db, current_user=teacher,
    )
    assert post.media_url.endswith("a.png")
    assert post.media_type == "image"


async def test_post_requires_content_or_media(db, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_post(data=PostCreate(), db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_media_requires_media_type(db, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_post(
            data=PostCreate(media_url="/uploads/org/a.png"),
            db=db, current_user=teacher,
        )
    assert exc.value.status_code == 422


# ── Listing ───────────────────────────────────────────────────────────────────

async def test_list_returns_newest_first(db, teacher):
    a = await create_post(data=PostCreate(content="first"), db=db, current_user=teacher)
    b = await create_post(data=PostCreate(content="second"), db=db, current_user=teacher)
    rows = await list_posts(limit=20, before=None, db=db, current_user=teacher)
    assert [p.id for p in rows] == [b.id, a.id]


async def test_list_includes_counts_and_liked_by_me(db, teacher, second_user):
    post = await create_post(data=PostCreate(content="hi"), db=db, current_user=teacher)
    await like_post(post_id=post.id, db=db, current_user=teacher)
    await like_post(post_id=post.id, db=db, current_user=second_user)
    await create_comment(
        post_id=post.id,
        data=CommentCreate(content="nice"),
        db=db, current_user=second_user,
    )

    rows = await list_posts(limit=20, before=None, db=db, current_user=teacher)
    assert len(rows) == 1
    assert rows[0].like_count == 2
    assert rows[0].comment_count == 1
    assert rows[0].liked_by_me is True


# ── Like toggle ───────────────────────────────────────────────────────────────

async def test_like_is_idempotent(db, teacher):
    post = await create_post(data=PostCreate(content="x"), db=db, current_user=teacher)
    r1 = await like_post(post_id=post.id, db=db, current_user=teacher)
    r2 = await like_post(post_id=post.id, db=db, current_user=teacher)
    assert r1.liked is True and r2.liked is True
    assert r1.like_count == 1 and r2.like_count == 1


async def test_unlike_removes_like(db, teacher):
    post = await create_post(data=PostCreate(content="x"), db=db, current_user=teacher)
    await like_post(post_id=post.id, db=db, current_user=teacher)
    r = await unlike_post(post_id=post.id, db=db, current_user=teacher)
    assert r.liked is False
    assert r.like_count == 0


async def test_unlike_on_unliked_is_noop(db, teacher):
    post = await create_post(data=PostCreate(content="x"), db=db, current_user=teacher)
    r = await unlike_post(post_id=post.id, db=db, current_user=teacher)
    assert r.liked is False
    assert r.like_count == 0


# ── Comments ──────────────────────────────────────────────────────────────────

async def test_create_and_list_comments(db, teacher, second_user):
    post = await create_post(data=PostCreate(content="x"), db=db, current_user=teacher)
    c1 = await create_comment(
        post_id=post.id,
        data=CommentCreate(content="first!"),
        db=db, current_user=second_user,
    )
    c2 = await create_comment(
        post_id=post.id,
        data=CommentCreate(content="second"),
        db=db, current_user=teacher,
    )
    rows = await list_comments(post_id=post.id, limit=50, db=db, current_user=teacher)
    assert [c.id for c in rows] == [c1.id, c2.id]  # chronological
    assert [c.content for c in rows] == ["first!", "second"]


async def test_comment_author_can_delete(db, teacher, second_user):
    post = await create_post(data=PostCreate(content="x"), db=db, current_user=teacher)
    c = await create_comment(
        post_id=post.id,
        data=CommentCreate(content="rm me"),
        db=db, current_user=second_user,
    )
    await delete_comment(
        post_id=post.id, comment_id=c.id,
        db=db, current_user=second_user,
    )
    rows = await list_comments(post_id=post.id, limit=50, db=db, current_user=teacher)
    assert rows == []


async def test_non_author_cannot_delete_comment(db, teacher, second_user):
    post = await create_post(data=PostCreate(content="x"), db=db, current_user=teacher)
    c = await create_comment(
        post_id=post.id,
        data=CommentCreate(content="mine"),
        db=db, current_user=second_user,
    )
    with pytest.raises(HTTPException) as exc:
        await delete_comment(
            post_id=post.id, comment_id=c.id,
            db=db, current_user=teacher,
        )
    assert exc.value.status_code == 403


# ── Post delete ───────────────────────────────────────────────────────────────

async def test_post_author_can_soft_delete(db, teacher):
    post = await create_post(data=PostCreate(content="x"), db=db, current_user=teacher)
    await delete_post(post_id=post.id, db=db, current_user=teacher)
    # Soft-deleted posts drop out of list and detail lookups.
    rows = await list_posts(limit=20, before=None, db=db, current_user=teacher)
    assert rows == []
    with pytest.raises(HTTPException) as exc:
        await get_post(post_id=post.id, db=db, current_user=teacher)
    assert exc.value.status_code == 404


async def test_non_author_cannot_delete_post(db, teacher, second_user):
    post = await create_post(data=PostCreate(content="x"), db=db, current_user=teacher)
    with pytest.raises(HTTPException) as exc:
        await delete_post(post_id=post.id, db=db, current_user=second_user)
    assert exc.value.status_code == 403


# ── Tenant isolation ──────────────────────────────────────────────────────────

async def test_other_org_cannot_see_post(db, teacher, other_org_user):
    post = await create_post(data=PostCreate(content="secret"), db=db, current_user=teacher)
    # 404 — other tenants shouldn't even learn it exists.
    with pytest.raises(HTTPException) as exc:
        await get_post(post_id=post.id, db=db, current_user=other_org_user)
    assert exc.value.status_code == 404


async def test_list_is_org_scoped(db, teacher, other_org_user):
    await create_post(data=PostCreate(content="org-a"), db=db, current_user=teacher)
    rows_b = await list_posts(limit=20, before=None, db=db, current_user=other_org_user)
    assert rows_b == []
    rows_a = await list_posts(limit=20, before=None, db=db, current_user=teacher)
    assert len(rows_a) == 1
    assert rows_a[0].content == "org-a"


async def test_other_org_cannot_like(db, teacher, other_org_user):
    post = await create_post(data=PostCreate(content="x"), db=db, current_user=teacher)
    with pytest.raises(HTTPException) as exc:
        await like_post(post_id=post.id, db=db, current_user=other_org_user)
    assert exc.value.status_code == 404


async def test_other_org_cannot_comment(db, teacher, other_org_user):
    post = await create_post(data=PostCreate(content="x"), db=db, current_user=teacher)
    with pytest.raises(HTTPException) as exc:
        await create_comment(
            post_id=post.id,
            data=CommentCreate(content="hi"),
            db=db, current_user=other_org_user,
        )
    assert exc.value.status_code == 404
