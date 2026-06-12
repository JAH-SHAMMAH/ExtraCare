"""
Tests for Phase 2 Commit 2 — feature flags.

Covers:
  • Plan default_features land in /me.org.features
  • Org-level overrides can enable a flag the plan doesn't ship
  • Org-level False overrides a plan-default True (clawback)
  • Null clears the override → reverts to the plan default
  • require_feature returns 403 with the {error, flag} detail shape
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import APIRouter, Depends
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.features import require_feature
from app.database import Base, get_db
from app.main import app
from app.models import user as _user, organization as _org, role as _role, audit as _audit, import_job as _ij  # noqa: F401
from app.models.modules import school as _school, hospital as _hospital, business as _business  # noqa: F401
from app.models.organization import Organization, SubscriptionTier
from app.models.user import User


# Mount a throwaway route guarded by require_feature so we can exercise the
# dep without depending on whether any real router has adopted it yet.
_probe = APIRouter(prefix="/api/v1/_test", tags=["test"])


@_probe.get("/ai", dependencies=[Depends(require_feature("ai_assistant"))])
async def _probe_ai():
    return {"ok": True}


app.include_router(_probe)


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


async def _mutate_org(client, slug, **fields):
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(select(Organization).where(Organization.slug == slug))).scalar_one()
        for k, v in fields.items():
            setattr(org, k, v)
        await db.commit()


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_plan_defaults_surface_in_me(client: AsyncClient):
    res = await _register(client, "ff-pro", "school")
    await _mutate_org(client, "ff-pro", subscription_tier=SubscriptionTier.PRO)

    r = await client.get("/api/v1/auth/me", headers=_auth(res["access_token"]))
    assert r.status_code == 200
    features = r.json()["org"]["features"]
    # Pro's default_features = ("advanced_reports",)
    assert features.get("advanced_reports") is True
    assert features.get("ai_assistant", False) is False


@pytest.mark.asyncio
async def test_override_enables_beta_on_free(client: AsyncClient):
    """Free plan has no default features, but super-admin can beta-toggle
    ai_assistant on for a specific tenant."""
    res = await _register(client, "ff-beta", "school")
    await _mutate_org(
        client, "ff-beta",
        subscription_tier=SubscriptionTier.FREE,
        features={"ai_assistant": True},
    )

    r = await client.get("/api/v1/auth/me", headers=_auth(res["access_token"]))
    assert r.json()["org"]["features"]["ai_assistant"] is True

    # And the guarded route actually opens up.
    r = await client.get("/api/v1/_test/ai", headers=_auth(res["access_token"]))
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_override_false_clawsback_plan_default(client: AsyncClient):
    """Enterprise ships ai_assistant=True by default, but an org can be
    explicitly clawed back (e.g. compliance opt-out)."""
    res = await _register(client, "ff-clawback", "school")
    await _mutate_org(
        client, "ff-clawback",
        subscription_tier=SubscriptionTier.ENTERPRISE,
        features={"ai_assistant": False},
    )

    r = await client.get("/api/v1/_test/ai", headers=_auth(res["access_token"]))
    assert r.status_code == 403, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "feature_disabled"
    assert detail["flag"] == "ai_assistant"


@pytest.mark.asyncio
async def test_require_feature_403_for_missing_flag(client: AsyncClient):
    """Free plan doesn't have ai_assistant and org hasn't overridden."""
    res = await _register(client, "ff-free", "school")
    await _mutate_org(client, "ff-free", subscription_tier=SubscriptionTier.FREE, features={})

    r = await client.get("/api/v1/_test/ai", headers=_auth(res["access_token"]))
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "feature_disabled"


@pytest.mark.asyncio
async def test_patch_features_endpoint_and_null_clears(client: AsyncClient):
    """Super-admin PATCH toggles, null clears the override."""
    res = await _register(client, "ff-patch", "school")

    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(select(Organization).where(Organization.slug == "ff-patch"))).scalar_one()
        user = (await db.execute(select(User).where(User.org_id == org.id))).scalar_one()
        user.is_superadmin = True
        org_id = org.id
        await db.commit()

    # Re-login to ensure fresh token identity.
    login = await client.post("/api/v1/auth/login", json={
        "email": "admin@ff-patch.example.com",
        "password": "StrongPass123!",
        "org_slug": "ff-patch",
    })
    tok = login.json()["access_token"]

    # Turn beta on.
    r = await client.patch(
        f"/api/v1/organizations/{org_id}/features",
        headers=_auth(tok),
        json={"features": {"ai_assistant": True}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["features_overrides"]["ai_assistant"] is True
    assert r.json()["features_effective"]["ai_assistant"] is True

    # Null clears → back to plan default (free → off).
    r = await client.patch(
        f"/api/v1/organizations/{org_id}/features",
        headers=_auth(tok),
        json={"features": {"ai_assistant": None}},
    )
    assert r.status_code == 200
    assert "ai_assistant" not in r.json()["features_overrides"]
    assert r.json()["features_effective"].get("ai_assistant", False) is False
