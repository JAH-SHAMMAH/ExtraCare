"""
Tests for Phase 2 Commit 3 — usage tracking.

Covers:
  • track() + flush() upsert path (idempotent, delta-aggregating)
  • GET /organizations/{id}/usage returns by_module / by_event / daily
  • Cross-tenant usage reads are rejected (403)
  • user_created is recorded as a platform event when an invite happens
"""

from __future__ import annotations

from datetime import date, datetime, timezone

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
from app.models.user import User
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

    # Route the service's flush at the test engine too (normally it uses
    # AsyncSessionLocal from the global db module).
    usage_svc._buffer.clear()  # start with a clean slate per test

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac.session_factory = Session  # type: ignore[attr-defined]
            yield ac
    finally:
        app.dependency_overrides.clear()
        usage_svc._buffer.clear()
        await engine.dispose()


async def _register(client, slug, industry, email=None):
    r = await client.post("/api/v1/auth/register", json={
        "org_name": f"{slug} corp",
        "org_slug": slug,
        "industry": industry,
        "admin_name": "Admin",
        "admin_email": email or f"admin@{slug}.example.com",
        "password": "StrongPass123!",
    })
    assert r.status_code == 201, r.text
    return r.json()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_track_and_flush_upserts(client: AsyncClient):
    """Two tracks for the same (org, module, event, day) must land on ONE
    row with count=2 — the whole point of buffered aggregation."""
    Session = client.session_factory  # type: ignore[attr-defined]

    usage_svc.track("org-1", "school", "request", count=1)
    usage_svc.track("org-1", "school", "request", count=1)
    usage_svc.track("org-1", "school", "request", count=3)

    n = await usage_svc.flush(session_factory=Session)
    assert n == 1  # one unique bucket, three tracks collapsed

    async with Session() as db:
        rows = (await db.execute(
            select(UsageEvent).where(UsageEvent.org_id == "org-1")
        )).scalars().all()
        assert len(rows) == 1
        assert rows[0].count == 5
        assert rows[0].module == "school"
        assert rows[0].event_type == "request"
        # date_bucket is a UTC bucket (see services/usage.py) — compare against
        # UTC today, not local, or this flakes around UTC midnight.
        assert rows[0].date_bucket == datetime.now(timezone.utc).date()


@pytest.mark.asyncio
async def test_second_flush_accumulates(client: AsyncClient):
    """Running flush twice on separate tracks must UPDATE the existing row
    rather than insert a duplicate — proves the UPSERT path."""
    Session = client.session_factory  # type: ignore[attr-defined]

    usage_svc.track("org-2", "hospital", "request", count=2)
    await usage_svc.flush(session_factory=Session)
    usage_svc.track("org-2", "hospital", "request", count=5)
    await usage_svc.flush(session_factory=Session)

    async with Session() as db:
        rows = (await db.execute(
            select(UsageEvent).where(UsageEvent.org_id == "org-2")
        )).scalars().all()
        assert len(rows) == 1
        assert rows[0].count == 7


@pytest.mark.asyncio
async def test_usage_read_endpoint(client: AsyncClient):
    """After registering an org + invite, the usage endpoint should report
    the user_created platform event plus any request counts."""
    res = await _register(client, "use-school", "school")

    # Invite triggers user_created explicit tracking.
    await client.post(
        "/api/v1/users/invite",
        headers=_auth(res["access_token"]),
        json={"email": "new@use-school.example.com", "full_name": "New User", "role_ids": []},
    )

    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(select(Organization).where(Organization.slug == "use-school"))).scalar_one()
        org_id = org.id

    r = await client.get(f"/api/v1/organizations/{org_id}/usage", headers=_auth(res["access_token"]))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["org_id"] == org_id
    assert body["by_event"].get("user_created", 0) >= 1
    assert "platform" in body["by_module"]
    assert body["total"] >= 1


@pytest.mark.asyncio
async def test_cross_tenant_usage_blocked(client: AsyncClient):
    """A user must not be able to read another org's usage."""
    a = await _register(client, "use-a", "school")
    b = await _register(client, "use-b", "school")

    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        other = (await db.execute(select(Organization).where(Organization.slug == "use-b"))).scalar_one()
        other_id = other.id

    r = await client.get(f"/api/v1/organizations/{other_id}/usage", headers=_auth(a["access_token"]))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_module_from_path_mapping():
    from app.services.usage import module_from_path
    assert module_from_path("/api/v1/school/students") == "school"
    assert module_from_path("/api/v1/behaviour/summary") == "school"
    assert module_from_path("/api/v1/hospital/patients") == "hospital"
    assert module_from_path("/api/v1/business/payroll") == "business"
    assert module_from_path("/api/v1/auth/me") is None  # platform route, not module
    assert module_from_path("/api/v1/users") is None
    assert module_from_path("/health") is None
