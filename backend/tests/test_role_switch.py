"""My Roles — genuine active-role switch.

  • User.permissions / primary_role scope DOWN to an active role (never escalate).
  • POST /auth/switch-role: held role scopes the session, a not-held role is 403,
    null returns to full access — proven end-to-end through the real ASGI app so
    the token → get_current_user → scoped-permission round trip is exercised.
  • Audit entries are stamped with the acting role.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import user as _user, organization as _org, role as _role, audit as _audit  # noqa: F401
from app.models.modules import school as _school  # noqa: F401
from app.models.user import User, UserStatus
from app.models.role import Role
from app.models.audit import AuditLog, AuditAction
from app.services import notifications as notif_svc


pytestmark = pytest.mark.asyncio


# ── Unit: permission scoping ──────────────────────────────────────────────────────

def _user_with(roles) -> User:
    u = User(id=str(uuid.uuid4()), email=f"u-{uuid.uuid4().hex[:6]}@x.com", full_name="U",
             status=UserStatus.ACTIVE, org_id="o", is_superadmin=False)
    u.roles = roles
    return u


def test_permissions_scope_down_to_active_role():
    su = Role(id="r-su", name="Super User", slug="super_user", permissions=["*"], org_id="o")
    tch = Role(id="r-tch", name="Teacher", slug="teacher",
               permissions=["school:read", "school:write", "hr:read"], org_id="o")
    u = _user_with([su, tch])

    # Default (no scope) → union: full access.
    assert u.has_permission("finance_admin:post") and "*" in u.permissions
    assert u.primary_role == "super_user"

    # Scoped to Teacher → ONLY teacher perms; the `*` is gone.
    u._active_role_id = "r-tch"
    assert "*" not in u.permissions
    assert u.has_permission("school:read")
    assert not u.has_permission("finance_admin:post")
    assert not u.has_permission("users:write")
    assert u.primary_role == "teacher"

    # An unknown / no-longer-held active id is ignored → falls back to full union.
    u._active_role_id = "r-gone"
    assert u.has_permission("finance_admin:post") and "*" in u.permissions


# ── Unit: audit stamp ─────────────────────────────────────────────────────────────

async def test_audit_stamps_acting_role(db, org):
    from app.services.audit_service import log_action
    actor = _user_with([Role(id="r1", name="Teacher", slug="teacher", permissions=["school:read"], org_id=org.id)])
    actor.org_id = org.id
    actor._active_role_slug = "teacher"
    await log_action(db, AuditAction.USER_UPDATED, org.id, actor=actor,
                     resource_type="User", resource_id="x", metadata={"field": "y"})
    await db.commit()
    row = (await db.execute(select(AuditLog).where(AuditLog.org_id == org.id))).scalars().first()
    assert row is not None and row.metadata_.get("acting_role") == "teacher"
    assert row.metadata_.get("field") == "y"   # existing metadata preserved


# ── End-to-end: the switch-role endpoint through the real app ─────────────────────

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
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
        notif_svc.set_session_factory_override(None)
        await engine.dispose()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


async def test_switch_role_end_to_end(client: AsyncClient):
    # Register → owner is Super User (single role) with full access.
    reg = await client.post("/api/v1/auth/register", json={
        "org_name": "Fairview", "org_slug": f"fv-{uuid.uuid4().hex[:6]}", "industry": "school",
        "admin_name": "Owner", "admin_email": f"owner-{uuid.uuid4().hex[:6]}@x.com", "password": "StrongPass123!",
    })
    assert reg.status_code == 201, reg.text
    tok = reg.json()["access_token"]

    me = (await client.get("/api/v1/auth/me", headers=_auth(tok))).json()
    owner_id = me["id"]
    assert me["active_role_id"] is None and "*" in me["permissions"]

    # Give the owner a SECOND role (Teacher) — owner is Super User, so the
    # escalation guard allows it.
    roles = (await client.get("/api/v1/users/roles/available", headers=_auth(tok))).json()["items"]
    by_slug = {r["slug"]: r["id"] for r in roles}
    su_id, tch_id = by_slug["super_user"], by_slug["teacher"]
    r = await client.patch(f"/api/v1/users/{owner_id}/roles", headers=_auth(tok), json=[su_id, tch_id])
    assert r.status_code == 200, r.text

    me = (await client.get("/api/v1/auth/me", headers=_auth(tok))).json()
    assert len(me["roles"]) == 2 and "*" in me["permissions"]

    # Switch DOWN to Teacher → session scoped, `*` gone, new token carries it.
    sw = await client.post("/api/v1/auth/switch-role", headers=_auth(tok), json={"role_id": tch_id})
    assert sw.status_code == 200, sw.text
    body = sw.json()
    assert body["user"]["active_role_id"] == tch_id
    assert "*" not in body["user"]["permissions"] and "school:read" in body["user"]["permissions"]
    scoped_tok = body["access_token"]

    # The scoped token really is scoped on the next request.
    me2 = (await client.get("/api/v1/auth/me", headers=_auth(scoped_tok))).json()
    assert me2["active_role_id"] == tch_id and "*" not in me2["permissions"]
    assert me2["primary_role"] == "teacher"

    # A role the user does NOT hold → 403.
    bad = await client.post("/api/v1/auth/switch-role", headers=_auth(scoped_tok), json={"role_id": str(uuid.uuid4())})
    assert bad.status_code == 403

    # Back to full access (null).
    full = await client.post("/api/v1/auth/switch-role", headers=_auth(scoped_tok), json={"role_id": None})
    assert full.status_code == 200
    assert full.json()["user"]["active_role_id"] is None and "*" in full.json()["user"]["permissions"]
