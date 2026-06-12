"""
High-signal tests for the industry/module isolation system.

Covers:
  • JWT carries `industry` + `modules` claims on every access token
  • A school org cannot reach hospital routes (module enforcement)
  • A user without `<module>:read` is rejected even if the module is enabled
  • /auth/me always returns the org summary with modules_enabled
  • Super-admin industry change writes a correct from→to audit row
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from jose import jwt as jose_jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import user as _user, organization as _org, role as _role, audit as _audit, import_job as _ij  # noqa: F401
from app.models.modules import school as _school, hospital as _hospital, business as _business  # noqa: F401
from app.models.audit import AuditAction, AuditLog
from app.models.organization import Organization
from app.models.role import Role
from app.models.user import User


SETTINGS = get_settings()


@pytest_asyncio.fixture
async def client():
    """An httpx.AsyncClient bound to the real FastAPI app with get_db
    overridden to point at an in-memory SQLite."""
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


async def _register(client: AsyncClient, slug: str, industry: str, email: str | None = None) -> dict:
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "org_name": f"{slug} corp",
            "org_slug": slug,
            "industry": industry,
            "admin_name": "Admin",
            "admin_email": email or f"admin@{slug}.example.com",
            "password": "StrongPass123!",
        },
    )
    assert r.status_code == 201, r.text
    # These tests predate onboarding — force-complete it so module routes
    # stay reachable. Onboarding enforcement is exercised in its own suite.
    await _complete_onboarding(client, slug)
    return r.json()


async def _complete_onboarding(client: AsyncClient, slug: str) -> None:
    from datetime import datetime, timezone as _tz
    from app.models.organization import Organization

    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(select(Organization).where(Organization.slug == slug))).scalar_one()
        org.onboarding_step = "done"
        org.onboarding_completed_at = datetime.now(_tz.utc)
        await db.commit()


async def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jwt_carries_industry_and_modules(client: AsyncClient):
    res = await _register(client, "jwt-school", "school")
    claims = jose_jwt.get_unverified_claims(res["access_token"])
    assert claims["industry"] == "school"
    assert "school" in claims["modules"]
    # Industry-scoped only — no cross-vertical leakage into the claim set.
    assert "hospital" not in claims["modules"]
    assert "business" not in claims["modules"]


@pytest.mark.asyncio
async def test_school_org_rejected_from_hospital_route(client: AsyncClient):
    res = await _register(client, "iso-school", "school")
    r = await client.get("/api/v1/hospital/patients", headers=await _auth(res["access_token"]))
    assert r.status_code == 403
    assert "hospital" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_school_org_allowed_on_school_route(client: AsyncClient):
    res = await _register(client, "ok-school", "school")
    r = await client.get("/api/v1/behaviour/summary", headers=await _auth(res["access_token"]))
    # 200 with the aggregate payload — critically, NOT 403.
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_permission_denied_without_module_read(client: AsyncClient):
    """Module is enabled but the user's role has no school:read — 403."""
    res = await _register(client, "perm-school", "school")
    Session = client.session_factory  # type: ignore[attr-defined]
    # Strip the admin's permissions down to something that does NOT include school:read.
    async with Session() as db:
        user = (await db.execute(select(User).where(User.email == "admin@perm-school.example.com"))).scalar_one()
        # Swap roles for a bare role with no module permissions.
        from app.models.role import Role
        bare = Role(name="Bare", slug="bare", permissions=["users:read"], org_id=user.org_id, is_system=False)
        db.add(bare)
        await db.flush()
        user.roles = [bare]
        await db.commit()

    r = await client.get("/api/v1/behaviour/summary", headers=await _auth(res["access_token"]))
    assert r.status_code == 403
    assert "school:read" in r.json()["detail"]


@pytest.mark.asyncio
async def test_me_returns_org_with_modules_enabled(client: AsyncClient):
    res = await _register(client, "me-school", "school")
    r = await client.get("/api/v1/auth/me", headers=await _auth(res["access_token"]))
    assert r.status_code == 200
    body = r.json()
    assert body["org"]["industry"] == "school"
    assert "school" in body["org"]["modules_enabled"]
    assert body["org"]["workspace"]["type"] == "school"


@pytest.mark.asyncio
async def test_business_registration_is_scoped_to_business_workspace(client: AsyncClient):
    res = await _register(client, "iso-business", "business")
    claims = jose_jwt.get_unverified_claims(res["access_token"])
    assert claims["industry"] == "business"
    assert claims["modules"] == ["business"]

    r = await client.get("/api/v1/auth/me", headers=await _auth(res["access_token"]))
    assert r.status_code == 200
    body = r.json()
    assert body["org"]["workspace"]["type"] == "business"
    assert body["org"]["modules_enabled"] == ["business"]
    assert "school" not in body["org"]["modules_enabled"]
    assert "hospital" not in body["org"]["modules_enabled"]

    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        roles = (
            await db.execute(
                select(Role)
                .join(Organization, Organization.id == Role.org_id)
                .where(Organization.slug == "iso-business")
            )
        ).scalars().all()
        assert roles
        for role in roles:
            assert not any(permission.startswith("school:") for permission in (role.permissions or []))
            assert not any(permission.startswith("hospital:") for permission in (role.permissions or []))


@pytest.mark.asyncio
async def test_business_org_with_legacy_school_module_does_not_leak_school(client: AsyncClient):
    res = await _register(client, "legacy-business", "business")
    Session = client.session_factory  # type: ignore[attr-defined]

    async with Session() as db:
        org = (await db.execute(select(Organization).where(Organization.slug == "legacy-business"))).scalar_one()
        org.modules_enabled = ["business", "school", "hospital"]
        await db.commit()

    me = await client.get("/api/v1/auth/me", headers=await _auth(res["access_token"]))
    assert me.status_code == 200
    assert me.json()["org"]["modules_enabled"] == ["business"]
    assert me.json()["org"]["modules_configured"] == ["business", "school", "hospital"]

    school = await client.get("/api/v1/behaviour/summary", headers=await _auth(res["access_token"]))
    assert school.status_code == 403


@pytest.mark.asyncio
async def test_workspace_overview_returns_business_only_contract(client: AsyncClient):
    res = await _register(client, "overview-business", "business")

    r = await client.get("/api/v1/dashboard/workspace-overview", headers=await _auth(res["access_token"]))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["workspace"]["type"] == "business"
    assert body["workspace"]["modules_enabled"] == ["business"]

    hrefs = [item["href"] for item in body["cards"] + body["quick_actions"]]
    assert hrefs
    assert all("/dashboard/modules/business" in href or href == "/dashboard/hrm" for href in hrefs)
    assert not any("/dashboard/modules/school" in href for href in hrefs)
    assert not any("/dashboard/modules/hospital" in href for href in hrefs)


@pytest.mark.asyncio
async def test_superadmin_industry_change_writes_audit(client: AsyncClient):
    res = await _register(client, "audit-school", "school")
    Session = client.session_factory  # type: ignore[attr-defined]

    # Promote admin to platform super-admin so PATCH is allowed.
    async with Session() as db:
        user = (await db.execute(select(User).where(User.email == "admin@audit-school.example.com"))).scalar_one()
        user.is_superadmin = True
        org_id = user.org_id
        await db.commit()

    # Re-login so the fresh JWT reflects the elevated identity (not strictly
    # required — is_superadmin is re-read from DB by require_superadmin — but
    # we keep the flow realistic.)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@audit-school.example.com", "password": "StrongPass123!", "org_slug": "audit-school"},
    )
    token = login.json()["access_token"]

    r = await client.patch(
        f"/api/v1/organizations/{org_id}/industry",
        headers=await _auth(token),
        json={"industry": "hospital"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["industry"] == "hospital"

    async with Session() as db:
        logs = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.org_id == org_id,
                    AuditLog.action == AuditAction.ORG_INDUSTRY_CHANGED,
                )
            )
        ).scalars().all()
        assert len(logs) == 1
        entry = logs[0]
        assert entry.old_values["industry"] == "school"
        assert entry.new_values["industry"] == "hospital"
        assert entry.actor_email == "admin@audit-school.example.com"
