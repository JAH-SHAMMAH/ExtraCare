"""
Tests for Phase 2 Commit 4 — guided onboarding.

Covers:
  • Fresh tenants start at step='users' (modules_enabled seeded at register)
  • Module routes 403 with `onboarding_incomplete` until completion
  • PATCH cannot skip ahead — must advance one step at a time
  • Auto-advance from DB state on /auth/me (invite a user → users→first_action)
  • Creating the primary record flips to `done` on the next /me
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import user as _user, organization as _org, role as _role, audit as _audit, import_job as _ij, usage as _usage  # noqa: F401
from app.models.modules import school as _school, hospital as _hospital, business as _business  # noqa: F401
from app.models.modules.school import Student
from app.models.organization import Organization
from app.models.user import User, UserStatus


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
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac.session_factory = Session  # type: ignore[attr-defined]
            yield ac
    finally:
        app.dependency_overrides.clear()
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
async def test_fresh_tenant_starts_at_users_step(client: AsyncClient):
    """Register seeds modules_enabled, so the auto-evaluate on /me pushes
    the tenant past 'modules' into 'users' immediately."""
    res = await _register(client, "ob-fresh")
    r = await client.get("/api/v1/auth/me", headers=_auth(res["access_token"]))
    assert r.status_code == 200
    org = r.json()["org"]
    assert org["onboarding_step"] == "users"
    assert org["onboarding_completed"] is False


@pytest.mark.asyncio
async def test_primary_module_soft_allowed_during_onboarding(client: AsyncClient):
    """Soft gate: the tenant's active vertical stays reachable so they can
    poke around while finishing setup. 'behaviour' is part of the school
    module group, so a school tenant mid-onboarding should get 200."""
    res = await _register(client, "ob-soft")
    r = await client.get("/api/v1/behaviour/summary", headers=_auth(res["access_token"]))
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_non_primary_module_blocked_by_onboarding(client: AsyncClient):
    """A hybrid tenant has hospital + business modules alongside school,
    but only the *first* (school) is in-scope during onboarding. Hitting a
    non-primary module must 403 with `onboarding_incomplete`."""
    res = await _register(client, "ob-hybrid", industry="hybrid")
    Session = client.session_factory  # type: ignore[attr-defined]
    # Hybrid seeds [school, hospital, business] modules. Cap the plan at
    # enterprise so the plan check doesn't 402 before the onboarding gate.
    async with Session() as db:
        from app.models.organization import SubscriptionTier
        org = (await db.execute(select(Organization).where(Organization.slug == "ob-hybrid"))).scalar_one()
        org.subscription_tier = SubscriptionTier.ENTERPRISE
        await db.commit()

    r = await client.get("/api/v1/hospital/patients", headers=_auth(res["access_token"]))
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["error"] == "onboarding_incomplete"


@pytest.mark.asyncio
async def test_diagnostic_endpoint_reports_requirement(client: AsyncClient):
    res = await _register(client, "ob-diag")
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org_id = (await db.execute(select(Organization).where(Organization.slug == "ob-diag"))).scalar_one().id

    r = await client.get(
        f"/api/v1/organizations/{org_id}/onboarding",
        headers=_auth(res["access_token"]),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["onboarding_completed"] is False
    assert body["onboarding_step"] == "users"  # auto-advanced past 'modules'
    assert "invite" in body["requirement"].lower()
    assert body["checks"]["modules_enabled_count"] >= 1
    assert body["checks"]["active_user_count"] == 1


@pytest.mark.asyncio
async def test_patch_cannot_skip_ahead(client: AsyncClient):
    """Requesting 'done' when the condition for 'first_action' is unmet
    must 400 — no skipping."""
    res = await _register(client, "ob-skip")
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org_id = (await db.execute(select(Organization).where(Organization.slug == "ob-skip"))).scalar_one().id

    r = await client.patch(
        f"/api/v1/organizations/{org_id}/onboarding",
        headers=_auth(res["access_token"]),
        json={"step": "done"},
    )
    assert r.status_code == 400
    assert "skip" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_auto_advance_through_flow(client: AsyncClient):
    """Invite a second user → /me should jump users→first_action. Then
    create a Student → /me should jump first_action→done."""
    res = await _register(client, "ob-flow")
    token = res["access_token"]

    # Invite a second user → now ≥2 users in the tenant.
    inv = await client.post(
        "/api/v1/users/invite",
        headers=_auth(token),
        json={"email": "two@ob-flow.example.com", "full_name": "Two", "role_ids": []},
    )
    assert inv.status_code in (200, 201), inv.text

    r = await client.get("/api/v1/auth/me", headers=_auth(token))
    assert r.json()["org"]["onboarding_step"] == "first_action"
    assert r.json()["org"]["onboarding_completed"] is False

    # Drop a primary record directly — simulates "admin added their first
    # student" without dragging in the whole student-create pipeline.
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(select(Organization).where(Organization.slug == "ob-flow"))).scalar_one()
        db.add(Student(
            student_id="S-001", first_name="A", last_name="B",
            org_id=org.id,
        ))
        await db.commit()

    r = await client.get("/api/v1/auth/me", headers=_auth(token))
    assert r.json()["org"]["onboarding_step"] == "done"
    assert r.json()["org"]["onboarding_completed"] is True


@pytest.mark.asyncio
async def test_module_route_unblocked_after_done(client: AsyncClient):
    """Once onboarding completes, the gate opens — no further drift."""
    res = await _register(client, "ob-done")
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(select(Organization).where(Organization.slug == "ob-done"))).scalar_one()
        org.onboarding_step = "done"
        org.onboarding_completed_at = datetime.now(timezone.utc)
        await db.commit()

    r = await client.get("/api/v1/behaviour/summary", headers=_auth(res["access_token"]))
    assert r.status_code == 200, r.text
