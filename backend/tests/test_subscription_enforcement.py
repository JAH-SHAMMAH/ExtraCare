"""
Tests for Phase 2 Commit 1 — subscription enforcement.

Covers:
  • Free-plan org with a module outside its cap is blocked with 402
  • Pro-plan org with the same module passes
  • User creation past the plan cap returns 402
  • /auth/me surfaces the current plan caps
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import user as _user, organization as _org, role as _role, audit as _audit, import_job as _ij  # noqa: F401
from app.models.modules import school as _school, hospital as _hospital, business as _business  # noqa: F401
from app.models.organization import Organization, SubscriptionTier
from app.models.user import User


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
    await _complete_onboarding(client, slug)
    return r.json()


async def _complete_onboarding(client: AsyncClient, slug: str) -> None:
    from datetime import datetime, timezone as _tz
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(select(Organization).where(Organization.slug == slug))).scalar_one()
        org.onboarding_step = "done"
        org.onboarding_completed_at = datetime.now(_tz.utc)
        await db.commit()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _set_tier(client: AsyncClient, org_slug: str, tier: SubscriptionTier, modules: list[str] | None = None):
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(select(Organization).where(Organization.slug == org_slug))).scalar_one()
        org.subscription_tier = tier
        if modules is not None:
            org.modules_enabled = modules
        await db.commit()


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_free_plan_blocks_module_beyond_cap(client: AsyncClient):
    """Free plan allows 1 module. A school org with two IN-WORKSPACE modules
    enabled should be blocked with 402 when hitting a module route.

    NB: the cap counts *effective* (workspace-filtered) modules. Both modules
    must belong to the school workspace, otherwise the cross-vertical one is
    stripped before the cap check and the count never exceeds 1 (see
    test_cross_vertical_module_is_filtered_and_does_not_count_toward_cap)."""
    res = await _register(client, "free-school", "school")
    # Free plan allows 1 module. Enable a second school-workspace module
    # (attendance) so the EFFECTIVE module count (2) exceeds the cap.
    await _set_tier(client, "free-school", SubscriptionTier.FREE, modules=["school", "attendance"])

    r = await client.get("/api/v1/behaviour/summary", headers=_auth(res["access_token"]))
    assert r.status_code == 402, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "plan_limit_exceeded"
    assert detail["reason"] == "module_not_allowed"
    assert detail["current_plan"] == "free"
    assert detail["required_plan"] == "pro"
    assert "upgrade_url" in detail


@pytest.mark.asyncio
async def test_cross_vertical_module_is_filtered_and_does_not_count_toward_cap(client: AsyncClient):
    """Regression (documents the billing semantic): plan caps count *effective*
    modules, i.e. those valid for the org's workspace. A school org carrying a
    stray cross-vertical entry ("hospital") has it stripped by the workspace
    boundary BEFORE the cap check, so it does NOT count. Free plan (cap 1) +
    ["school", "hospital"] → effective ["school"] = 1 → allowed (200), not 402.

    This guards against someone "fixing" the filtering away and re-counting
    stray modules toward billing. Pair with
    test_free_plan_blocks_module_beyond_cap, which uses two in-workspace
    modules to legitimately trip the cap."""
    res = await _register(client, "filtered-school", "school")
    await _set_tier(client, "filtered-school", SubscriptionTier.FREE, modules=["school", "hospital"])

    r = await client.get("/api/v1/behaviour/summary", headers=_auth(res["access_token"]))
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_pro_plan_permits_same_module(client: AsyncClient):
    """Pro plan allows 2 modules. Trim to 2, then call the module route."""
    res = await _register(client, "pro-school", "school")
    await _set_tier(client, "pro-school", SubscriptionTier.PRO, modules=["school", "attendance"])

    r = await client.get("/api/v1/behaviour/summary", headers=_auth(res["access_token"]))
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_enterprise_plan_unlimited(client: AsyncClient):
    res = await _register(client, "ent-school", "school")
    await _set_tier(client, "ent-school", SubscriptionTier.ENTERPRISE)

    r = await client.get("/api/v1/behaviour/summary", headers=_auth(res["access_token"]))
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_user_cap_blocks_invite(client: AsyncClient):
    """Free plan caps at 10 users. Seed the org up to the cap, then invite
    the 11th — expect 402."""
    res = await _register(client, "cap-school", "school")
    await _set_tier(client, "cap-school", SubscriptionTier.FREE, modules=["school"])

    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org_id = (await db.execute(select(Organization).where(Organization.slug == "cap-school"))).scalar_one().id
        # Admin already counts as user #1 — add 9 more to hit the cap.
        for i in range(9):
            db.add(User(
                email=f"filler{i}@cap-school.example.com",
                full_name=f"Filler {i}",
                org_id=org_id,
                status="active",
            ))
        await db.commit()

    r = await client.post(
        "/api/v1/users/invite",
        headers=_auth(res["access_token"]),
        json={"email": "overflow@cap-school.example.com", "full_name": "Overflow", "role_ids": []},
    )
    assert r.status_code == 402, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "plan_limit_exceeded"
    assert detail["reason"] == "user_limit_exceeded"
    assert detail["current_plan"] == "free"
    assert detail["required_plan"] == "pro"


@pytest.mark.asyncio
async def test_me_exposes_plan_caps(client: AsyncClient):
    res = await _register(client, "me-plan", "school")
    await _set_tier(client, "me-plan", SubscriptionTier.PRO)

    r = await client.get("/api/v1/auth/me", headers=_auth(res["access_token"]))
    assert r.status_code == 200
    plan = r.json()["org"]["plan"]
    assert plan["tier"] == "pro"
    assert plan["max_modules"] == 2
    assert plan["max_users"] == 50
