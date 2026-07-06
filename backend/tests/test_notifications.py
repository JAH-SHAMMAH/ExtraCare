"""
Tests for Phase 3 Commit 2 — notifications.

Covers:
  • Inviting a user fires a `user_invited` notification (org-wide)
  • Hitting a plan cap fires a `plan_limit` notification
  • GET /notifications returns {items, unread_count} for the caller
  • PATCH /{id}/read flips read=True; read-all bulk-flips
  • Cross-tenant isolation on the inbox
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import user as _user, organization as _org, role as _role, audit as _audit, import_job as _ij, usage as _usage, notification as _notif  # noqa: F401
from app.models.modules import school as _school, hospital as _hospital, business as _business  # noqa: F401
from app.models.notification import (
    Notification, TYPE_USER_INVITED, TYPE_PLAN_LIMIT,
)
from app.models.organization import Organization, SubscriptionTier
from app.services import notifications as notif_svc


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_db():
        async with Session() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[get_db] = _get_db
    # Fire-and-forget notifications need to land on the test engine, not
    # the real AsyncSessionLocal. Point the override at the test factory.
    notif_svc.set_session_factory_override(Session)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac.session_factory = Session  # type: ignore[attr-defined]
            yield ac
    finally:
        app.dependency_overrides.clear()
        notif_svc.set_session_factory_override(None)
        await engine.dispose()


async def _register(client, slug, industry="school"):
    r = await client.post("/api/v1/auth/register", json={
        "org_name": f"{slug} corp",
        "org_slug": slug,
        "industry": industry,
        "admin_name": "Admin",
        "admin_email": f"admin@{slug}.example.com",
        "password": "StrongPass123!",
    })
    assert r.status_code == 201, r.text
    return r.json()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_invite_fires_user_invited_notification(client: AsyncClient):
    res = await _register(client, "notif-inv")
    r = await client.post(
        "/api/v1/users/invite",
        headers=_auth(res["access_token"]),
        json={"email": "new@notif-inv.example.com", "full_name": "New Joiner", "role_ids": []},
    )
    assert r.status_code in (200, 201), r.text

    inbox = await client.get("/api/v1/notifications", headers=_auth(res["access_token"]))
    assert inbox.status_code == 200
    items = inbox.json()["items"]
    match = [n for n in items if n["type"] == TYPE_USER_INVITED]
    assert len(match) == 1
    assert "new@notif-inv.example.com" in match[0]["message"]
    assert match[0]["read"] is False
    assert inbox.json()["unread_count"] >= 1


@pytest.mark.asyncio
async def test_plan_limit_fires_notification(client: AsyncClient):
    """Forcing a school org over the free-plan module cap triggers a 402
    and drops a plan_limit row in the inbox."""
    res = await _register(client, "notif-plan")
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(select(Organization).where(Organization.slug == "notif-plan"))).scalar_one()
        org.subscription_tier = SubscriptionTier.FREE
        # Two IN-WORKSPACE modules (both school) exceed the free cap of 1. A
        # cross-vertical entry would be stripped by the workspace filter before
        # the cap check, so it must be a school-workspace module to count.
        org.modules_enabled = ["school", "attendance"]  # effective count 2 > free cap 1
        org.onboarding_step = "done"
        from datetime import datetime, timezone
        org.onboarding_completed_at = datetime.now(timezone.utc)
        await db.commit()

    r = await client.get("/api/v1/behaviour/summary", headers=_auth(res["access_token"]))
    assert r.status_code == 402

    inbox = await client.get("/api/v1/notifications", headers=_auth(res["access_token"]))
    items = inbox.json()["items"]
    match = [n for n in items if n["type"] == TYPE_PLAN_LIMIT]
    assert len(match) >= 1
    assert match[0]["payload"]["reason"] == "module_not_allowed"


@pytest.mark.asyncio
async def test_mark_read_flips_flag(client: AsyncClient):
    res = await _register(client, "notif-read")
    # Create a direct notification row for the admin user.
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        from app.models.user import User
        user = (await db.execute(select(User).where(User.email == "admin@notif-read.example.com"))).scalar_one()
        n = Notification(
            org_id=user.org_id, user_id=user.id, type="system",
            title="Hello", message="World",
        )
        db.add(n)
        await db.commit()
        notif_id = n.id

    r = await client.patch(
        f"/api/v1/notifications/{notif_id}/read",
        headers=_auth(res["access_token"]),
    )
    assert r.status_code == 200, r.text

    async with Session() as db:
        row = (await db.execute(select(Notification).where(Notification.id == notif_id))).scalar_one()
        assert row.read is True


@pytest.mark.asyncio
async def test_mark_all_read_bulk_flips(client: AsyncClient):
    res = await _register(client, "notif-all")
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        from app.models.user import User
        user = (await db.execute(select(User).where(User.email == "admin@notif-all.example.com"))).scalar_one()
        for i in range(3):
            db.add(Notification(
                org_id=user.org_id, user_id=user.id, type="system",
                title=f"n{i}", message=None,
            ))
        await db.commit()

    r = await client.patch("/api/v1/notifications/read-all", headers=_auth(res["access_token"]))
    assert r.status_code == 200
    assert r.json()["marked"] >= 3

    inbox = await client.get(
        "/api/v1/notifications?unread_only=true",
        headers=_auth(res["access_token"]),
    )
    assert inbox.json()["items"] == []


@pytest.mark.asyncio
async def test_cross_tenant_notification_isolated(client: AsyncClient):
    a = await _register(client, "notif-a")
    b = await _register(client, "notif-b")

    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        from app.models.user import User
        user_b = (await db.execute(select(User).where(User.email == "admin@notif-b.example.com"))).scalar_one()
        db.add(Notification(
            org_id=user_b.org_id, user_id=user_b.id, type="system",
            title="B-only", message="should never leak",
        ))
        await db.commit()

    r = await client.get("/api/v1/notifications", headers=_auth(a["access_token"]))
    titles = [n["title"] for n in r.json()["items"]]
    assert "B-only" not in titles
