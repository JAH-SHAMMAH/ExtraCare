"""
Cookie authentication (Priority 2) — dual-mode, flag-gated, CSRF-protected.

Runs the real app via AsyncClient. The `cookie_on` fixture flips
COOKIE_AUTH_ENABLED (and COOKIE_SECURE off, so cookies flow over the http test
transport). Covers: flag-off behaviour unchanged, cookie issuance (httpOnly),
cookie-only auth, Bearer still works, refresh via cookie AND via body, logout
clears cookies, and CSRF (double-submit) for cookie-authenticated mutations.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.config import get_settings
from app.models import user as _user, organization as _org, role as _role, audit as _audit, import_job as _ij  # noqa: F401
from app.models.modules import school as _school, hospital as _hospital, business as _business  # noqa: F401

pytestmark = pytest.mark.asyncio


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
            yield ac
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


@pytest.fixture
def cookie_on(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "COOKIE_AUTH_ENABLED", True)
    monkeypatch.setattr(s, "COOKIE_SECURE", False)  # http test transport
    return s


async def _register(client, slug):
    r = await client.post("/api/v1/auth/register", json={
        "org_name": f"{slug} corp", "org_slug": slug, "industry": "school",
        "admin_name": "Admin", "admin_email": f"admin@{slug}.example.com",
        "password": "StrongPass123!",
    })
    assert r.status_code == 201, r.text
    return r


async def _login(client, slug):
    # org_slug is required in multi-tenant mode (tests force SINGLE_SCHOOL_MODE
    # off); it is ignored when single-school mode is on.
    return await client.post("/api/v1/auth/login", json={
        "email": f"admin@{slug}.example.com", "password": "StrongPass123!",
        "org_slug": slug,
    })


# ── Flag off: behaviour unchanged ─────────────────────────────────────────────

async def test_login_sets_no_cookies_when_flag_off(client):
    await _register(client, "off1")
    r = await _login(client, "off1")
    assert r.status_code == 200
    assert r.cookies.get("access_token") is None
    assert r.json()["access_token"]  # body token still returned


async def test_refresh_via_body_still_works(client):
    reg = await _register(client, "body1")
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": reg.json()["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["access_token"]


# ── Flag on: cookie issuance + dual-mode ──────────────────────────────────────

async def test_login_issues_httponly_cookies_when_flag_on(client, cookie_on):
    await _register(client, "on1")
    r = await _login(client, "on1")
    assert r.status_code == 200
    assert r.cookies.get("access_token")
    assert r.cookies.get("refresh_token")
    assert r.cookies.get("csrf_token")
    raw = " ".join(r.headers.get_list("set-cookie")).lower()
    assert "httponly" in raw                 # access + refresh are httpOnly
    assert r.json()["access_token"]          # dual-mode: body token still returned


async def test_cookie_auth_allows_me_without_bearer(client, cookie_on):
    await _register(client, "on2")
    await _login(client, "on2")              # cookie jar now holds the session
    r = await client.get("/api/v1/auth/me")  # NO Authorization header
    assert r.status_code == 200


async def test_bearer_still_works_when_flag_on(client, cookie_on):
    reg = await _register(client, "on3")
    token = reg.json()["access_token"]
    client.cookies.clear()                   # prove it's the Bearer header working
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


async def test_refresh_via_cookie(client, cookie_on):
    await _register(client, "on4")
    await _login(client, "on4")
    r = await client.post("/api/v1/auth/refresh")  # no body — refresh rides in cookie
    assert r.status_code == 200
    assert r.json()["access_token"]
    assert r.cookies.get("access_token")          # rotated cookie re-issued


async def test_logout_clears_cookies(client, cookie_on):
    await _register(client, "on5")
    await _login(client, "on5")
    r = await client.post("/api/v1/auth/logout")
    assert r.status_code == 200
    raw = " ".join(r.headers.get_list("set-cookie")).lower()
    assert "access_token=" in raw                  # deletion header present


# ── CSRF (double-submit) for cookie-authenticated mutations ───────────────────

async def test_csrf_blocks_cookie_mutation_without_token(client, cookie_on):
    await _register(client, "on6")
    await _login(client, "on6")
    r = await client.post("/api/v1/messenger/conversations", json={})  # no X-CSRF-Token
    assert r.status_code == 403
    assert "csrf" in r.json()["detail"].lower()


async def test_csrf_allows_cookie_mutation_with_token(client, cookie_on):
    await _register(client, "on7")
    await _login(client, "on7")
    csrf = client.cookies.get("csrf_token")
    r = await client.post("/api/v1/messenger/conversations", json={}, headers={"X-CSRF-Token": csrf})
    # CSRF passes → request reaches the handler (422 bad body etc.), never a CSRF 403.
    assert not (r.status_code == 403 and "csrf" in r.json().get("detail", "").lower())


async def test_csrf_exempts_bearer_clients(client, cookie_on):
    reg = await _register(client, "on8")
    token = reg.json()["access_token"]
    client.cookies.clear()
    r = await client.post(
        "/api/v1/messenger/conversations", json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert not (r.status_code == 403 and "csrf" in r.json().get("detail", "").lower())
