"""
Unified rate limiter (Priority 3).

One dependency family, one sliding-window store behind a small interface so
Redis can be dropped in later WITHOUT touching endpoint code. Rules are
centralised and env-overridable — no magic numbers live at call sites.

Design guarantees for school operations:
  • Authenticated endpoints key on USER / ORG, never raw IP — so a whole class
    behind one school NAT never shares a bucket. CBT attempts, attendance
    marking, grade submission, report-card generation and timetable ops are
    NOT limited at all (no dependency attached).
  • Unauthenticated auth endpoints (login / register / refresh) key on IP —
    the correct key for pre-auth abuse, where one school's volume is low.
  • Every breach is recorded (endpoint, user_id, org_id, ip, timestamp,
    limiter key, threshold) to the security log AND the denial counters,
    whether the rule is enforced or monitoring-only.

Modes:
  • RATE_LIMITS_ENABLED=false  → limiter is a no-op (default in tests).
  • RATE_LIMIT_MONITOR_ONLY=true → every rule logs + counts but never 429s.
  • Per-rule enforce=False       → that rule logs + counts but never 429s.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Deque, Optional, Protocol, runtime_checkable

from fastapi import Depends, HTTPException, Request, status

from app.config import get_settings

_logger = logging.getLogger("extracare.security")


# ── Rules ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RateRule:
    limit: int
    window: int          # seconds
    scope: str = "ip"    # "ip" | "user" | "org" | "user_org"
    enforce: bool = True  # False → monitoring-only (log + count, never 429)


# Central rule table. Auth + SMS ENFORCE (clear-cut security / cost). The new
# authenticated app limits start in MONITORING-ONLY so we observe real traffic
# before blocking — flip via env (RATE_LIMIT_OVERRIDES) or by editing here.
DEFAULT_RULES: dict[str, RateRule] = {
    # Unauthenticated — per IP, enforced.
    "login":          RateRule(20, 60, "ip", enforce=True),
    "register":       RateRule(5, 3600, "ip", enforce=True),
    "refresh":        RateRule(60, 60, "ip", enforce=True),
    # Authenticated, org-scoped — enforced (outbound SMS cost control).
    "sms_send":       RateRule(5, 60, "org", enforce=True),
    # Authenticated admin action — enforced (kept from the pre-Priority-3 limit).
    "org_industry":   RateRule(10, 60, "user", enforce=True),
    # Authenticated app actions — MONITORING-ONLY initially (observe first).
    "ai_assist":      RateRule(20, 60, "user_org", enforce=False),
    "imports":        RateRule(10, 60, "org", enforce=False),
    "upload":         RateRule(30, 300, "user", enforce=False),
    "messenger_send": RateRule(60, 60, "user", enforce=False),
    "messenger_new":  RateRule(20, 60, "user", enforce=False),
    "feed_post":      RateRule(40, 300, "user", enforce=False),
}


def _parse_overrides(raw: str) -> dict[str, RateRule]:
    """Merge env overrides onto DEFAULT_RULES. Format per entry:
    `bucket=limit/window[/scope][/monitor]` (comma-separated)."""
    rules: dict[str, RateRule] = dict(DEFAULT_RULES)
    for part in (raw or "").split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, spec = part.split("=", 1)
        name = name.strip()
        bits = [b.strip() for b in spec.split("/") if b.strip()]
        if len(bits) < 2:
            continue
        try:
            limit, window = int(bits[0]), int(bits[1])
        except ValueError:
            continue
        base = rules.get(name, RateRule(limit, window))
        scope = bits[2] if len(bits) > 2 and bits[2] in ("ip", "user", "org", "user_org") else base.scope
        enforce = base.enforce
        if any(b.lower() == "monitor" for b in bits[2:]):
            enforce = False
        elif any(b.lower() == "enforce" for b in bits[2:]):
            enforce = True
        rules[name] = RateRule(limit, window, scope, enforce)
    return rules


_RULES: Optional[dict[str, RateRule]] = None


def _rules() -> dict[str, RateRule]:
    global _RULES
    if _RULES is None:
        _RULES = _parse_overrides(get_settings().RATE_LIMIT_OVERRIDES)
    return _RULES


def reload_rules() -> None:
    """Drop the cached rule table so the next call rebuilds from settings.
    Used by tests that tweak RATE_LIMIT_OVERRIDES at runtime."""
    global _RULES
    _RULES = None


# ── Store (Redis-ready) ───────────────────────────────────────────────────────

@runtime_checkable
class RateLimitStore(Protocol):
    """Pluggable backing store. A future RedisStore implements the same
    `hit()` contract; endpoints never see the store, so swapping it in needs
    zero endpoint changes."""

    def hit(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """Record one hit against `key`. Returns (allowed, retry_after_secs)."""
        ...

    def reset(self) -> None:
        ...


class InMemoryStore:
    """Single-process sliding-window counter. Correct for one app instance;
    swap for RedisStore when scaling horizontally."""

    def __init__(self) -> None:
        self._hits: dict[str, Deque[float]] = {}
        self._lock = Lock()

    def hit(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - window
        with self._lock:
            q = self._hits.get(key)
            if q is None:
                q = deque()
                self._hits[key] = q
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= limit:
                retry_in = max(1, int(window - (now - q[0])) + 1)
                return False, retry_in
            q.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


_store: Optional[RateLimitStore] = None


def get_store() -> RateLimitStore:
    global _store
    if _store is None:
        # Future: `if get_settings().REDIS_ENABLED: _store = RedisStore(...)`.
        # The in-memory store is the only implementation today.
        _store = InMemoryStore()
    return _store


def reset_store() -> None:
    """Clear all counters. Used by the per-test fixture so limiter state never
    leaks across tests (the store is process-global)."""
    get_store().reset()


# ── Core ──────────────────────────────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _record_breach(
    request: Request, bucket: str, rule: RateRule, key: str,
    user_id: Optional[str], org_id: Optional[str], retry_in: int, enforced: bool,
) -> None:
    """Observability: every breach (enforced OR monitored) lands in the
    security log with the full field set, and bumps the denial counters that
    /admin/metrics surfaces."""
    _logger.warning(
        "rate_limit_exceeded",
        extra={
            "event": "rate_limit_exceeded",
            "endpoint": request.url.path,
            "bucket": bucket,
            "limiter_key": key,
            "threshold": f"{rule.limit}/{rule.window}s",
            "scope": rule.scope,
            "enforced": enforced,
            "user_id": user_id,
            "org_id": org_id,
            "ip": _client_ip(request),
            "retry_after": retry_in,
        },
    )
    try:
        from app.core.tenant import bump_denial
        bump_denial("rate_limit_exceeded", org_id or "_", bucket)
    except Exception:  # pragma: no cover - counters are best-effort
        pass


def _apply(request: Request, bucket: str, user=None) -> None:
    settings = get_settings()
    if not settings.RATE_LIMITS_ENABLED:
        return
    rule = _rules().get(bucket)
    if rule is None:
        return

    user_id = getattr(user, "id", None)
    org_id = getattr(user, "org_id", None)

    if rule.scope == "user":
        key_val = user_id or _client_ip(request)
    elif rule.scope == "org":
        key_val = org_id or _client_ip(request)
    elif rule.scope == "user_org":
        key_val = f"{user_id}:{org_id}" if user_id else _client_ip(request)
    else:  # "ip"
        key_val = _client_ip(request)
    key = f"{bucket}:{key_val}"

    allowed, retry_in = get_store().hit(key, rule.limit, rule.window)
    if allowed:
        return

    # Breach. Monitoring-only (per-rule OR global switch) logs + counts but
    # never blocks — the request proceeds.
    enforced = rule.enforce and not settings.RATE_LIMIT_MONITOR_ONLY
    _record_breach(request, bucket, rule, key, user_id, org_id, retry_in, enforced)
    if not enforced:
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Too many requests. Retry in ~{retry_in}s.",
        headers={"Retry-After": str(retry_in)},
    )


# ── Dependencies ──────────────────────────────────────────────────────────────

def rate_limit_ip(bucket: str):
    """Limiter for UNAUTHENTICATED endpoints — keys on client IP.
    Usage: `dependencies=[Depends(rate_limit_ip("login"))]`."""

    async def _check(request: Request):
        _apply(request, bucket, user=None)

    return _check


def rate_limit_auth(bucket: str):
    """Limiter for AUTHENTICATED endpoints — keys on user/org per the rule's
    scope (never raw IP, to survive school NAT).
    Usage: `dependencies=[Depends(rate_limit_auth("ai_assist"))]`."""

    from app.deps import get_current_active_user

    async def _check(request: Request, current_user=Depends(get_current_active_user)):
        _apply(request, bucket, user=current_user)

    return _check
