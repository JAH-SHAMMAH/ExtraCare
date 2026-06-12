"""
Usage tracking — in-memory aggregation with periodic DB flush.

Design: every `track()` call increments a counter in a process-local dict.
A background task drains the dict into `usage_events` rows every
FLUSH_INTERVAL seconds, UPSERTing on (org, module, event_type, day). On
app shutdown we drain one last time so in-flight counts aren't lost.

This stays correct enough for billing inputs while keeping the hot path
allocation-free — tracking a request is one dict write under a lock.

Not safe across multiple processes yet. When we scale horizontally:
either (a) point the buffer at Redis, or (b) let every worker flush its
own slice and rely on UPSERT at the DB. The call sites don't change.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import date
from threading import Lock
from typing import Iterable

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.usage import UsageEvent


_logger = logging.getLogger("extracare.usage")

FLUSH_INTERVAL = 30.0  # seconds
BUFFER_MAX_KEYS = 10_000  # backpressure guard — trigger early flush above this

# Key: (org_id, module, event_type, date_bucket). Value: accumulated delta.
# We don't keep any timestamps — the bucket is the grain.
_buffer: dict[tuple[str, str, str, date], int] = defaultdict(int)
_lock = Lock()
_early_flush_event: asyncio.Event | None = None


def _init_early_flush_event() -> None:
    """Created lazily so `track()` stays import-safe in sync contexts."""
    global _early_flush_event
    if _early_flush_event is None:
        try:
            _early_flush_event = asyncio.Event()
        except RuntimeError:
            # No running loop — nothing to signal. Background flusher will
            # pick the buffer up on its next tick.
            pass


# ── URL → module mapping ────────────────────────────────────────────────────

# First path segment under /api/v1/ → module. Keys NOT listed here are
# treated as "platform" (e.g. /auth, /users, /analytics). Keeping this
# table explicit prevents a new router from silently being mis-attributed.
_PATH_MODULE_MAP: dict[str, str] = {
    "school": "school",
    "behaviour": "school",
    "cbt": "school",
    "classroom": "school",
    "clubs": "school",
    "feedback": "school",
    "journals": "school",
    "library": "school",
    "sms": "school",
    "transport": "school",
    "tuckshop": "school",
    "hospital": "hospital",
    "business": "business",
}


_unmapped_seen: set[str] = set()


def module_from_path(path: str) -> str | None:
    """Return the module key that owns `path`, or None if untracked."""
    parts = path.strip("/").split("/")
    # Expect /api/v1/<segment>/...
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
        seg = parts[2]
        module = _PATH_MODULE_MAP.get(seg)
        if module is None and seg not in _unmapped_seen:
            # First time we see an unmapped first-segment — log once so
            # ops notice a new router that should probably be attributed.
            # Subsequent hits stay silent (no per-request log spam).
            _unmapped_seen.add(seg)
            _logger.debug("usage: unmapped path segment '%s' (path=%s)", seg, path)
        return module
    return None


# ── Public API ──────────────────────────────────────────────────────────────

def track(org_id: str | None, module: str, event_type: str, count: int = 1) -> None:
    """Fire-and-forget. Safe to call from middleware, routes, or services.
    Silently no-ops for unauthenticated requests (org_id is None)."""
    if not org_id or count <= 0:
        return
    key = (org_id, module, event_type, _utc_today())
    over_threshold = False
    with _lock:
        _buffer[key] += count
        if len(_buffer) > BUFFER_MAX_KEYS:
            over_threshold = True
    # Under sustained burst we want the flusher to wake up, not wait for the
    # 30s tick. Signal outside the lock so track() stays O(1) on the hot path.
    if over_threshold and _early_flush_event is not None:
        _early_flush_event.set()


def _utc_today() -> date:
    """Single source of truth for the bucket grain. Forcing UTC keeps
    counters stable across deploys where server TZ may differ from DB."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).date()


def snapshot_and_clear() -> dict[tuple[str, str, str, date], int]:
    """Atomically swap the buffer out so a flush can work on a stable copy
    without blocking concurrent tracks."""
    with _lock:
        if not _buffer:
            return {}
        out = dict(_buffer)
        _buffer.clear()
        return out


async def _upsert_one(db: AsyncSession, org_id: str, module: str, event_type: str, bucket: date, delta: int) -> None:
    """UPDATE first; if nothing updated, INSERT. On race we catch the
    uniqueness violation and retry the UPDATE. Works on SQLite + MySQL
    without dialect-specific `ON CONFLICT` syntax."""
    res = await db.execute(
        update(UsageEvent)
        .where(
            UsageEvent.org_id == org_id,
            UsageEvent.module == module,
            UsageEvent.event_type == event_type,
            UsageEvent.date_bucket == bucket,
        )
        .values(count=UsageEvent.count + delta)
    )
    if (res.rowcount or 0) > 0:
        return

    db.add(UsageEvent(
        org_id=org_id, module=module, event_type=event_type,
        date_bucket=bucket, count=delta,
    ))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        await db.execute(
            update(UsageEvent)
            .where(
                UsageEvent.org_id == org_id,
                UsageEvent.module == module,
                UsageEvent.event_type == event_type,
                UsageEvent.date_bucket == bucket,
            )
            .values(count=UsageEvent.count + delta)
        )


async def flush(session_factory=None, session: AsyncSession | None = None) -> int:
    """Drain the buffer into the DB. Returns the number of rows touched.
    - `session` — write through an existing AsyncSession; caller commits.
      Used by the /usage read endpoint so tests & request-scoped overrides
      see the same transaction.
    - `session_factory` — open a dedicated session (used by the background
      flusher and tests that want an isolated write).
    - neither — fall back to the global AsyncSessionLocal."""
    batch = snapshot_and_clear()
    if not batch:
        return 0

    if session is not None:
        try:
            for (org_id, module, event_type, bucket), delta in batch.items():
                await _upsert_one(session, org_id, module, event_type, bucket, delta)
        except Exception:
            with _lock:
                for k, v in batch.items():
                    _buffer[k] += v
            raise
        return len(batch)

    factory = session_factory or AsyncSessionLocal
    async with factory() as db:
        try:
            for (org_id, module, event_type, bucket), delta in batch.items():
                await _upsert_one(db, org_id, module, event_type, bucket, delta)
            await db.commit()
        except Exception:
            await db.rollback()
            with _lock:
                for k, v in batch.items():
                    _buffer[k] += v
            raise
    return len(batch)


# ── Background flusher ──────────────────────────────────────────────────────

_flusher_task: asyncio.Task | None = None


async def _flusher_loop() -> None:
    assert _early_flush_event is not None
    while True:
        try:
            # Wake up either on the regular tick OR if track() tripped the
            # size guard — whichever happens first.
            try:
                await asyncio.wait_for(_early_flush_event.wait(), timeout=FLUSH_INTERVAL)
            except asyncio.TimeoutError:
                pass
            _early_flush_event.clear()
            await flush()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            _logger.exception("usage flush failed: %s", exc)


def start_flusher() -> None:
    """Call once on app startup. Idempotent."""
    global _flusher_task
    if _flusher_task is not None and not _flusher_task.done():
        return
    _init_early_flush_event()
    _flusher_task = asyncio.create_task(_flusher_loop(), name="usage-flusher")


async def stop_flusher() -> None:
    """Call once on app shutdown. Cancels the loop and performs a final flush."""
    global _flusher_task
    if _flusher_task is not None:
        _flusher_task.cancel()
        try:
            await _flusher_task
        except asyncio.CancelledError:
            pass
        _flusher_task = None
    try:
        await flush()
    except Exception:
        _logger.exception("final usage flush failed")
