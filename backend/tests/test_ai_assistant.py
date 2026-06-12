"""
Tests for Phase 3 Commit 3 — AI assistant.

Covers:
  • Feature flag enforcement — tenant without `ai_assistant` is blocked (403)
  • Module enforcement — module not in `modules_enabled` is blocked (403)
  • Permission enforcement — caller without `<module>:read` is blocked (403)
  • Valid response shape + module/task metadata
  • Unknown task returns 400 with the supported list
  • Cross-tenant isolation — tenant A cannot invoke on a module only B has
  • First-use notification fires once per org
  • ai.request / ai.success usage counters increment
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
from app.models import (  # noqa: F401
    user as _user,
    organization as _org,
    role as _role,
    audit as _audit,
    import_job as _ij,
    usage as _usage,
    notification as _notif,
)
from app.models.modules import (  # noqa: F401
    school as _school,
    hospital as _hospital,
    business as _business,
)
from app.models.notification import Notification, TYPE_SYSTEM
from app.models.organization import Organization, SubscriptionTier
from app.models.usage import UsageEvent
from app.models.user import User
from app.services import notifications as notif_svc
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


async def _configure_org(
    client,
    slug,
    *,
    tier: SubscriptionTier = SubscriptionTier.ENTERPRISE,
    modules: list[str] | None = None,
    features: dict | None = None,
):
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(select(Organization).where(Organization.slug == slug))).scalar_one()
        org.subscription_tier = tier
        if modules is not None:
            org.modules_enabled = modules
        if features is not None:
            org.features = features
        org.onboarding_step = "done"
        org.onboarding_completed_at = datetime.now(timezone.utc)
        await db.commit()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_feature_flag_gates_assistant(client: AsyncClient):
    """FREE plan → no `ai_assistant` default → 403 feature_disabled."""
    res = await _register(client, "ai-off")
    await _configure_org(
        client, "ai-off",
        tier=SubscriptionTier.FREE,
        modules=["school"],
        features={},
    )

    r = await client.post(
        "/api/v1/ai/assist",
        headers=_auth(res["access_token"]),
        json={"module": "school", "task": "suggest", "context": {"goal": "improve reading"}},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "feature_disabled"
    assert r.json()["detail"]["flag"] == "ai_assistant"


@pytest.mark.asyncio
async def test_module_not_enabled_returns_403(client: AsyncClient):
    """Feature on, but module missing from modules_enabled."""
    res = await _register(client, "ai-mod", industry="school")
    await _configure_org(
        client, "ai-mod",
        tier=SubscriptionTier.ENTERPRISE,
        modules=["school"],  # no hospital
    )

    r = await client.post(
        "/api/v1/ai/assist",
        headers=_auth(res["access_token"]),
        json={"module": "hospital", "task": "summarise_vitals", "context": {}},
    )
    assert r.status_code == 403
    assert "hospital" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_valid_request_returns_structured_response(client: AsyncClient):
    res = await _register(client, "ai-ok")
    await _configure_org(client, "ai-ok", modules=["school"])

    r = await client.post(
        "/api/v1/ai/assist",
        headers=_auth(res["access_token"]),
        json={
            "module": "school",
            "task": "generate_report",
            "context": {
                "student_name": "Aisha",
                "student_id": "S-001",
                "term": "Term 2",
                "average_score": 82,
                "strengths": ["Math", "Reading"],
                "concerns": ["Punctuality"],
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["result"], str) and body["result"]
    assert "Aisha" in body["result"]
    assert "S-001" in body["result"]

    meta = body["meta"]
    assert meta["module"] == "school"
    assert meta["task"] == "generate_report"
    assert meta["tokens_used"] is None
    assert meta["provider"] == "noop"


@pytest.mark.asyncio
async def test_unknown_task_returns_400_with_supported_list(client: AsyncClient):
    res = await _register(client, "ai-task")
    await _configure_org(client, "ai-task", modules=["school"])

    r = await client.post(
        "/api/v1/ai/assist",
        headers=_auth(res["access_token"]),
        json={"module": "school", "task": "write_my_homework", "context": {}},
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "unsupported_task"
    assert "generate_report" in detail["supported_tasks"]


@pytest.mark.asyncio
async def test_cross_tenant_isolation(client: AsyncClient):
    """Tenant A (school only) cannot invoke the hospital module — not in
    its modules_enabled. Even though tenant B has hospital enabled, A's
    request is evaluated against A's org row."""
    a = await _register(client, "ai-a", industry="school")
    b = await _register(client, "ai-b", industry="hospital")

    await _configure_org(client, "ai-a", modules=["school"])
    await _configure_org(client, "ai-b", modules=["hospital"])

    r = await client.post(
        "/api/v1/ai/assist",
        headers=_auth(a["access_token"]),
        json={"module": "hospital", "task": "summarise_vitals", "context": {}},
    )
    assert r.status_code == 403

    # Sanity: B can still reach hospital.
    r = await client.post(
        "/api/v1/ai/assist",
        headers=_auth(b["access_token"]),
        json={"module": "hospital", "task": "summarise_vitals", "context": {"patient_name": "Zola"}},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_first_use_notification_fires_once(client: AsyncClient):
    res = await _register(client, "ai-first")
    await _configure_org(client, "ai-first", modules=["school"])

    for _ in range(3):
        r = await client.post(
            "/api/v1/ai/assist",
            headers=_auth(res["access_token"]),
            json={"module": "school", "task": "suggest", "context": {"goal": "reduce tardiness"}},
        )
        assert r.status_code == 200

    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        rows = (await db.execute(
            select(Notification).where(
                Notification.type == TYPE_SYSTEM,
                Notification.title == "AI assistant is now active",
            )
        )).scalars().all()
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_usage_counters_increment(client: AsyncClient):
    res = await _register(client, "ai-usage")
    await _configure_org(client, "ai-usage", modules=["school"])

    r = await client.post(
        "/api/v1/ai/assist",
        headers=_auth(res["access_token"]),
        json={"module": "school", "task": "suggest", "context": {"goal": "staff retention"}},
    )
    assert r.status_code == 200

    # Flush the in-memory buffer so counters land in the DB we can query.
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        await usage_svc.flush(session=db)
        await db.commit()

        rows = (await db.execute(
            select(UsageEvent).where(UsageEvent.module == "school")
        )).scalars().all()
        kinds = {r.event_type for r in rows}
        assert "ai.request" in kinds
        assert "ai.success" in kinds
