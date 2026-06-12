"""
Notification service.

Two write modes:
  • `notify(..., session=db)` — inline in a request that already has a
    session; caller commits.
  • `notify_fire_and_forget(...)` — opens its own AsyncSessionLocal,
    commits, swallows exceptions. Used from code that can't share the
    caller's session (e.g. a dep that's about to raise 402 — the caller's
    transaction rolls back, which would wipe the notification with it).

Never raise out of notifications — they're a UX nicety, not a correctness
dependency. A failed insert must not break an otherwise-successful flow.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.notification import Notification


_logger = logging.getLogger("extracare.notifications")

# Tests swap this in so fire-and-forget writes land on the same in-memory
# engine as the request's session. Production stays on AsyncSessionLocal.
_session_factory_override = None  # type: ignore[assignment]


def set_session_factory_override(factory) -> None:
    """Tests only — point fire-and-forget at a specific session factory."""
    global _session_factory_override
    _session_factory_override = factory


async def notify(
    *,
    org_id: str,
    user_id: str | None,
    type: str,
    title: str,
    message: str | None = None,
    payload: dict[str, Any] | None = None,
    session: AsyncSession,
) -> Notification | None:
    """Inline notification. Caller owns the commit."""
    try:
        row = Notification(
            org_id=org_id,
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            payload=payload,
        )
        session.add(row)
        await session.flush()
        return row
    except Exception as exc:
        _logger.warning("notify(inline) failed: %s", exc)
        return None


async def notify_fire_and_forget(
    *,
    org_id: str,
    user_id: str | None,
    type: str,
    title: str,
    message: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Isolated-session write. Use when the caller is about to raise an
    HTTPException (its transaction would rollback) or otherwise can't
    share a session. Swallows all errors."""
    factory = _session_factory_override or AsyncSessionLocal
    try:
        async with factory() as db:
            db.add(Notification(
                org_id=org_id,
                user_id=user_id,
                type=type,
                title=title,
                message=message,
                payload=payload,
            ))
            await db.commit()
    except Exception as exc:
        _logger.warning("notify(fire-and-forget) failed: %s", exc)


async def list_for(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    unread_only: bool = False,
    notif_type: str | None = None,
    limit: int = 50,
) -> list[Notification]:
    """User's inbox = notifications addressed to them directly OR org-wide
    (user_id IS NULL). Ordered newest-first."""
    q = select(Notification).where(
        Notification.org_id == org_id,
        (Notification.user_id == user_id) | (Notification.user_id.is_(None)),
    )
    if unread_only:
        q = q.where(Notification.read == False)  # noqa: E712
    if notif_type is not None:
        q = q.where(Notification.type == notif_type)
    q = q.order_by(Notification.created_at.desc()).limit(limit)
    return (await db.execute(q)).scalars().all()


async def unread_count(db: AsyncSession, *, org_id: str, user_id: str) -> int:
    from sqlalchemy import func
    return int((await db.execute(
        select(func.count(Notification.id)).where(
            Notification.org_id == org_id,
            (Notification.user_id == user_id) | (Notification.user_id.is_(None)),
            Notification.read == False,  # noqa: E712
        )
    )).scalar() or 0)


async def mark_read(db: AsyncSession, *, org_id: str, user_id: str, notification_id: str) -> bool:
    """Returns True if the row was owned by this user (or org-wide) and flipped."""
    row = (await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.org_id == org_id,
        )
    )).scalar_one_or_none()
    if row is None:
        return False
    # Org-wide rows are visible to everyone in the tenant; marking them
    # read only affects the requester by flipping the shared flag. That's
    # a deliberate simplification — we don't track per-user read state to
    # keep the schema flat. If that matters later, add a join table.
    if row.user_id is not None and row.user_id != user_id:
        return False
    row.read = True
    return True


async def mark_all_read(db: AsyncSession, *, org_id: str, user_id: str) -> int:
    """Bulk-flip every unread notification visible to the user."""
    res = await db.execute(
        update(Notification)
        .where(
            Notification.org_id == org_id,
            (Notification.user_id == user_id) | (Notification.user_id.is_(None)),
            Notification.read == False,  # noqa: E712
        )
        .values(read=True)
    )
    return int(res.rowcount or 0)
