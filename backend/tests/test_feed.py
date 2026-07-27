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
from app.models.role import Role
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
    u.roles = []   # loaded (mirrors get_current_user's selectinload) so audience checks don't lazy-load
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
    u.roles = []   # loaded (mirrors get_current_user's selectinload) so audience checks don't lazy-load
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


async def test_create_post_with_document_attachment(db, teacher):
    """Documents attach via the PostAttachment model and round-trip through the feed."""
    from app.schemas.feed import AttachmentIn
    post = await create_post(
        data=PostCreate(
            content="Please review the attached policy.",
            attachments=[AttachmentIn(
                kind="file", url="/uploads/org/documents/x.pdf",
                filename="Policy 2026.pdf", mime_type="application/pdf", size_bytes=12345)],
        ),
        db=db, current_user=teacher,
    )
    assert len(post.attachments) == 1
    a = post.attachments[0]
    assert a.id and a.kind == "file" and a.filename == "Policy 2026.pdf" and a.url.endswith("x.pdf")

    # Selectin-loaded on the listing.
    rows = await list_posts(limit=20, before=None, db=db, current_user=teacher)
    mine = next(p for p in rows if p.id == post.id)
    assert len(mine.attachments) == 1 and mine.attachments[0].kind == "file"

    # A post with ONLY an attachment (no text/media) is valid.
    doc_only = await create_post(
        data=PostCreate(attachments=[AttachmentIn(kind="file", url="/uploads/o/d.docx", filename="d.docx")]),
        db=db, current_user=teacher,
    )
    assert doc_only.content is None and len(doc_only.attachments) == 1


async def test_link_attachment_and_xss_scheme_guard(db, teacher):
    from pydantic import ValidationError
    from app.schemas.feed import AttachmentIn
    post = await create_post(
        data=PostCreate(content="Resource", attachments=[
            AttachmentIn(kind="link", url="https://example.com/policy", title="Policy")]),
        db=db, current_user=teacher,
    )
    assert post.attachments[0].kind == "link"
    assert post.attachments[0].url == "https://example.com/policy" and post.attachments[0].title == "Policy"

    # Non-http(s) link schemes (javascript:/data:) are rejected at validation.
    for bad in ("javascript:alert(1)", "data:text/html,<script>1</script>", "/uploads/x"):
        with pytest.raises(ValidationError):
            AttachmentIn(kind="link", url=bad)


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


# ── Audience targeting (Publish-To) ─────────────────────────────────────────────

async def _user_with_roles(db, org, *slugs, name="U") -> User:
    u = User(id=str(uuid.uuid4()), email=f"{uuid.uuid4().hex[:8]}@x.com", full_name=name,
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [Role(id=str(uuid.uuid4()), name=s, slug=s, permissions=[], org_id=org.id, is_system=True) for s in slugs]
    db.add(u)
    await db.commit()
    return u


def _ids(rows):
    return {p.id for p in rows}


async def test_audience_targeting_roles_and_users(db, org):
    author = await _user_with_roles(db, org, "org_admin", name="Author")
    teacher_u = await _user_with_roles(db, org, "teacher", name="Teach")
    parent_u = await _user_with_roles(db, org, "parent", name="Parent")

    async def feed_for(u):
        return await list_posts(limit=20, before=None, db=db, current_user=u)

    # Public (no audience) → everyone.
    pub = await create_post(data=PostCreate(content="hello all"), db=db, current_user=author)
    assert pub.audience_roles == [] and pub.audience_user_ids == []
    assert pub.id in _ids(await feed_for(parent_u))

    # Role-targeted (teacher): teacher sees; parent doesn't; author sees own even
    # though org_admin is not "teacher".
    tp = await create_post(data=PostCreate(content="staff only", audience_roles=["teacher"]), db=db, current_user=author)
    assert tp.audience_roles == ["teacher"]
    assert tp.id in _ids(await feed_for(teacher_u))
    assert tp.id not in _ids(await feed_for(parent_u))
    assert tp.id in _ids(await feed_for(author))

    # User-targeted (parent): parent sees; teacher doesn't.
    up = await create_post(data=PostCreate(content="hi parent", audience_user_ids=[parent_u.id]), db=db, current_user=author)
    assert up.audience_user_ids == [parent_u.id]
    assert up.id in _ids(await feed_for(parent_u))
    assert up.id not in _ids(await feed_for(teacher_u))

    # Single-post fetch enforces audience too (404 for non-audience; author/target OK).
    with pytest.raises(HTTPException) as exc:
        await get_post(post_id=tp.id, db=db, current_user=parent_u)
    assert exc.value.status_code == 404
    assert (await get_post(post_id=tp.id, db=db, current_user=teacher_u)).id == tp.id

    # Can't like a post that wasn't shared with you.
    with pytest.raises(HTTPException) as exc:
        await like_post(post_id=tp.id, db=db, current_user=parent_u)
    assert exc.value.status_code == 404


async def test_moderator_settings_read_sees_all(db, org):
    """Admin-tier moderators (settings:read) bypass targeting and see every post."""
    mod = User(id=str(uuid.uuid4()), email=f"{uuid.uuid4().hex[:8]}@x.com", full_name="Mod",
               status=UserStatus.ACTIVE, org_id=org.id)
    mod.roles = [Role(id=str(uuid.uuid4()), name="Admin", slug="org_admin",
                      permissions=["settings:read"], org_id=org.id, is_system=True)]
    db.add(mod)
    await db.commit()

    author = await _user_with_roles(db, org, "teacher", name="Author")
    tp = await create_post(data=PostCreate(content="parents only", audience_roles=["parent"]), db=db, current_user=author)

    # Mod is not a parent, but sees the post in the feed AND via single-fetch.
    assert tp.id in {p.id for p in await list_posts(limit=20, before=None, db=db, current_user=mod)}
    assert (await get_post(post_id=tp.id, db=db, current_user=mod)).id == tp.id


async def test_audience_drops_cross_org_user(db, org, other_org):
    author = await _user_with_roles(db, org, "org_admin")
    outsider = await _user_with_roles(db, other_org, "teacher")
    p = await create_post(
        data=PostCreate(content="x", audience_user_ids=[outsider.id]),
        db=db, current_user=author,
    )
    # A cross-tenant user id is silently dropped — it can never target another org.
    assert p.audience_user_ids == []


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
