"""
Rate limiter tests (Priority 3).

The suite runs with RATE_LIMITS_ENABLED=false (conftest), so these tests flip
it on locally via the `rl` fixture and drive the limiter dependencies directly
with fake Request/user objects — no HTTP stack needed. Covers:
  • enforcement (429 past the limit)
  • monitor-only mode (per-rule + global switch) — never blocks, still records
  • disabled mode — never blocks
  • scope isolation — ip vs ip, user vs user, org vs org
  • SMS protection — per-org enforcement + cross-org isolation
  • observability — denial counters bumped on every breach path
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.config import get_settings
from app.core import ratelimit
from app.core.ratelimit import RateRule, rate_limit_ip, rate_limit_auth
from app.core.tenant import denial_counters_snapshot

pytestmark = pytest.mark.asyncio


def _req(ip: str = "9.9.9.9", path: str = "/test"):
    return type("R", (), {
        "headers": {},
        "client": type("C", (), {"host": ip})(),
        "url": type("U", (), {"path": path})(),
    })()


def _user(uid: str = "u1", org: str = "o1"):
    return type("U", (), {"id": uid, "org_id": org})()


@pytest.fixture
def rl(monkeypatch):
    """Enable enforcement, isolate the store + rules, restore on teardown."""
    s = get_settings()
    monkeypatch.setattr(s, "RATE_LIMITS_ENABLED", True)
    monkeypatch.setattr(s, "RATE_LIMIT_MONITOR_ONLY", False)
    ratelimit.reset_store()
    ratelimit._RULES = {}
    yield ratelimit
    ratelimit._RULES = None
    ratelimit.reset_store()


# ── Enforcement ───────────────────────────────────────────────────────────────

async def test_enforce_returns_429_past_limit(rl):
    rl._RULES = {"b": RateRule(2, 60, "ip", enforce=True)}
    check = rate_limit_ip("b")
    await check(_req(ip="1.1.1.1"))
    await check(_req(ip="1.1.1.1"))
    with pytest.raises(HTTPException) as ei:
        await check(_req(ip="1.1.1.1"))
    assert ei.value.status_code == 429
    assert "Retry-After" in ei.value.headers


# ── Scope isolation ───────────────────────────────────────────────────────────

async def test_ip_scope_isolated_between_ips(rl):
    rl._RULES = {"b": RateRule(1, 60, "ip", enforce=True)}
    check = rate_limit_ip("b")
    await check(_req(ip="1.1.1.1"))          # uses IP1's budget
    await check(_req(ip="2.2.2.2"))          # different IP → allowed
    with pytest.raises(HTTPException):
        await check(_req(ip="1.1.1.1"))      # IP1 over budget


async def test_user_scope_isolated_between_users(rl):
    rl._RULES = {"b": RateRule(1, 60, "user", enforce=True)}
    check = rate_limit_auth("b")
    await check(_req(), current_user=_user("alice", "o1"))
    await check(_req(), current_user=_user("bob", "o1"))   # different user → allowed
    with pytest.raises(HTTPException):
        await check(_req(), current_user=_user("alice", "o1"))


# ── Monitor-only ──────────────────────────────────────────────────────────────

async def test_per_rule_monitor_only_never_blocks(rl):
    rl._RULES = {"b": RateRule(1, 60, "ip", enforce=False)}
    check = rate_limit_ip("b")
    for _ in range(5):
        await check(_req(ip="3.3.3.3"))      # well past limit, never raises


async def test_global_monitor_only_overrides_enforce(rl, monkeypatch):
    monkeypatch.setattr(get_settings(), "RATE_LIMIT_MONITOR_ONLY", True)
    rl._RULES = {"b": RateRule(1, 60, "ip", enforce=True)}
    check = rate_limit_ip("b")
    for _ in range(5):
        await check(_req(ip="4.4.4.4"))      # enforce=True but global monitor → no 429


async def test_monitor_only_still_records_breach(rl):
    rl._RULES = {"mon": RateRule(1, 60, "org", enforce=False)}
    check = rate_limit_auth("mon")
    await check(_req(), current_user=_user("u", "orgM"))
    await check(_req(), current_user=_user("u", "orgM"))   # breach (no raise)
    snap = denial_counters_snapshot()
    assert any(e["bucket"] == "mon" and e["org_id"] == "orgM" for e in snap)


# ── Disabled ──────────────────────────────────────────────────────────────────

async def test_disabled_mode_never_blocks(rl, monkeypatch):
    monkeypatch.setattr(get_settings(), "RATE_LIMITS_ENABLED", False)
    rl._RULES = {"b": RateRule(1, 60, "ip", enforce=True)}
    check = rate_limit_ip("b")
    for _ in range(5):
        await check(_req(ip="5.5.5.5"))      # disabled → no 429


# ── SMS protection (per-org) ──────────────────────────────────────────────────

async def test_sms_send_enforced_per_org(rl):
    rl._RULES = {"sms_send": RateRule(2, 60, "org", enforce=True)}
    check = rate_limit_auth("sms_send")
    # Same org: two different admins share the ORG bucket.
    await check(_req(), current_user=_user("admin", "schoolA"))
    await check(_req(), current_user=_user("teacher", "schoolA"))
    with pytest.raises(HTTPException) as ei:
        await check(_req(), current_user=_user("admin", "schoolA"))
    assert ei.value.status_code == 429
    # Different org is isolated — must NOT be limited by schoolA's usage.
    await check(_req(), current_user=_user("admin", "schoolB"))


# ── Observability ─────────────────────────────────────────────────────────────

async def test_breach_bumps_denial_counter(rl):
    rl._RULES = {"obs": RateRule(1, 60, "org", enforce=True)}
    check = rate_limit_auth("obs")
    await check(_req(), current_user=_user("u", "orgX"))
    with pytest.raises(HTTPException):
        await check(_req(), current_user=_user("u", "orgX"))
    snap = denial_counters_snapshot()
    assert any(
        e["event"] == "rate_limit_exceeded" and e["org_id"] == "orgX" and e["bucket"] == "obs"
        for e in snap
    )
