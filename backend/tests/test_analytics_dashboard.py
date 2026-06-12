"""
Tests for Phase 3 Commit 1 — analytics dashboard.

Covers:
  • /usage group_by=module|event|day returns a single-bucket projection
  • /usage compare_previous=true attaches delta_pct vs prior window
  • /analytics/summary rolls totals + top_module + growth %
  • growth_pct is None when the prior window is empty (no divide-by-zero)
  • Cross-tenant analytics reads are rejected (403)
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import user as _user, organization as _org, role as _role, audit as _audit, import_job as _ij, usage as _usage  # noqa: F401
from app.models.modules import school as _school, hospital as _hospital, business as _business  # noqa: F401
from app.models.organization import Organization
from app.models.usage import UsageEvent
from app.services import usage as usage_svc


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
    usage_svc._buffer.clear()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac.session_factory = Session  # type: ignore[attr-defined]
            yield ac
    finally:
        app.dependency_overrides.clear()
        usage_svc._buffer.clear()
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


async def _seed_events(session_factory, org_id: str, *, today_count: int, prior_count: int):
    """Drop rows directly into usage_events so we can exercise the read
    path without driving traffic through middleware. The read API only
    cares about aggregated rows, not how they got there."""
    today = date.today()
    prior = today - timedelta(days=45)  # outside the 30-day default window
    async with session_factory() as db:
        if today_count > 0:
            db.add(UsageEvent(
                org_id=org_id, module="school", event_type="request",
                date_bucket=today, count=today_count,
            ))
        if prior_count > 0:
            db.add(UsageEvent(
                org_id=org_id, module="hospital", event_type="request",
                date_bucket=prior, count=prior_count,
            ))
        await db.commit()


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_usage_group_by_module_returns_single_bucket(client: AsyncClient):
    res = await _register(client, "ana-grp")
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(select(Organization).where(Organization.slug == "ana-grp"))).scalar_one()
    await _seed_events(Session, org.id, today_count=5, prior_count=0)

    r = await client.get(
        f"/api/v1/organizations/{org.id}/usage?group_by=module",
        headers=_auth(res["access_token"]),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "series" in body
    assert "by_event" not in body  # single-bucket projection only
    assert any(row["key"] == "school" and row["count"] == 5 for row in body["series"])
    # Register also emits platform-scoped events (onboarding_started); the
    # total covers every module in the window, not just 'school'.
    assert body["total"] >= 5


@pytest.mark.asyncio
async def test_usage_compare_previous_emits_delta(client: AsyncClient):
    res = await _register(client, "ana-cmp")
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(select(Organization).where(Organization.slug == "ana-cmp"))).scalar_one()

    # 90-day window makes the "previous" window absorb the prior-count seed.
    today = date.today()
    async with Session() as db:
        db.add(UsageEvent(org_id=org.id, module="school", event_type="request",
                          date_bucket=today, count=20))
        db.add(UsageEvent(org_id=org.id, module="school", event_type="request",
                          date_bucket=today - timedelta(days=95), count=10))
        await db.commit()

    r = await client.get(
        f"/api/v1/organizations/{org.id}/usage?days=90&compare_previous=true",
        headers=_auth(res["access_token"]),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Current window absorbs the seeded 20 + any platform events from register.
    assert body["total"] >= 20
    # Prior window contains only the seeded 10 (pre-registration).
    assert body["compare"]["previous_total"] == 10
    assert body["compare"]["delta_pct"] is not None
    assert body["compare"]["delta_pct"] > 0


@pytest.mark.asyncio
async def test_analytics_summary_shape(client: AsyncClient):
    res = await _register(client, "ana-sum")
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(select(Organization).where(Organization.slug == "ana-sum"))).scalar_one()
    await _seed_events(Session, org.id, today_count=7, prior_count=0)

    r = await client.get(
        f"/api/v1/organizations/{org.id}/analytics/summary",
        headers=_auth(res["access_token"]),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Register emits one onboarding_started (platform); seed adds 7 requests (school).
    assert body["totals"]["requests"] == 7
    assert body["top_module"]["module"] == "school"
    assert body["totals"]["all_events"] >= 7
    # Prior window is empty → delta_pct must be None (no divide-by-zero).
    assert body["growth"]["previous_total"] == 0
    assert body["growth"]["delta_pct"] is None


@pytest.mark.asyncio
async def test_analytics_summary_cross_tenant_blocked(client: AsyncClient):
    a = await _register(client, "ana-a")
    b = await _register(client, "ana-b")
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        other = (await db.execute(select(Organization).where(Organization.slug == "ana-b"))).scalar_one()

    r = await client.get(
        f"/api/v1/organizations/{other.id}/analytics/summary",
        headers=_auth(a["access_token"]),
    )
    assert r.status_code == 403
