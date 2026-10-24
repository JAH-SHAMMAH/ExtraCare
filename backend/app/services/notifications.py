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
from app.models.notification import Notification, NotificationDismissal


_logger = logging.getLogger("extracare.notifications")

# Tests swap this in so fire-and-forget writes land on the same in-memory
# engine as the request's session. Production stays on AsyncSessionLocal.
_session_factory_override = None  # type: ignore[assignment]


def set_session_factory_override(factory) -> None:
    """Tests only — point fire-and-forget at a specific session factory."""
    global _session_factory_override
    _session_factory_override = factory


# notification `type` -> Super Settings event key (only types that have a switch).
_TYPE_EVENT = {"attendance": "class_attendance"}


async def _push_enabled(session: AsyncSession, org_id: str, type: str) -> bool:
    ev = _TYPE_EVENT.get(type)
    if not ev:
        return True
    try:
        from app.services import super_settings as _ss
        prefs = (await _ss.get_struct(session, org_id)).get("notification_prefs", {})
        return bool(prefs.get(ev, {}).get("push", True))
    except Exception:
        return True


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
        if not await _push_enabled(session, org_id, type):
            return None
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
        _push_later(org_id, user_id, title, message, (payload or {}).get("url"), type)
        return row
    except Exception as exc:
        _logger.warning("notify(inline) failed: %s", exc)
        return None


def _push_later(org_id: str, user_id: str | None, title: str, message: str | None, url: str | None = None, kind: str = "other") -> None:
    """Also pop the alert up on the person's phone, without making the caller wait."""
    if not user_id:
        return
    import asyncio

    async def _go():
        try:
            from app.services import webpush
            factory = _session_factory_override or AsyncSessionLocal
            async with factory() as db:
                from app.models.user import User
                u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
                chosen = ((u.preferences or {}).get("push_alerts") or {}) if u else {}
                if chosen.get(kind if kind in ("attendance", "report") else "other", True) is False:
                    return  # this person switched this kind of alert off
                await webpush.send_to_user(db, org_id, user_id, title=title, body=message or "", url=url or "/dashboard/notifications")
        except Exception as exc:
            _logger.debug("push skipped: %s", exc)
    try:
        asyncio.get_running_loop().create_task(_go())
    except RuntimeError:
        pass


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


# Platform/plan chatter nobody at the school should be shown. The school has no
# plans, so these are never created any more; the filter also hides any left over.
_HIDDEN_TYPES = ("plan_limit", "onboarding_step")


def _visible(org_id: str, user_id: str):
    """WHERE clauses for what one user's inbox contains."""
    return [
        Notification.org_id == org_id,
        (Notification.user_id == user_id) | (Notification.user_id.is_(None)),
        Notification.type.notin_(_HIDDEN_TYPES),
        ~Notification.id.in_(select(NotificationDismissal.notification_id).where(
            NotificationDismissal.user_id == user_id)),
    ]


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
    q = select(Notification).where(*_visible(org_id, user_id))
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
            *_visible(org_id, user_id),
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
            *_visible(org_id, user_id),
            Notification.read == False,  # noqa: E712
        )
        .values(read=True)
    )
    return int(res.rowcount or 0)


async def clear_all(db: AsyncSession, *, org_id: str, user_id: str) -> int:
    """Clear this user's whole inbox. Their own rows are deleted; org-wide rows are
    hidden for them alone (a dismissal), so nobody else's inbox changes."""
    from sqlalchemy import delete
    rows = (await db.execute(select(Notification.id, Notification.user_id).where(*_visible(org_id, user_id)))).all()
    own = [i for i, uid in rows if uid == user_id]
    shared = [i for i, uid in rows if uid is None]
    if own:
        await db.execute(delete(Notification).where(Notification.id.in_(own), Notification.user_id == user_id))
    for nid in shared:
        db.add(NotificationDismissal(org_id=org_id, user_id=user_id, notification_id=nid))
    return len(rows)


async def clear_one(db: AsyncSession, *, org_id: str, user_id: str, notification_id: str) -> bool:
    from sqlalchemy import delete
    row = (await db.execute(select(Notification).where(
        Notification.id == notification_id, *_visible(org_id, user_id)))).scalar_one_or_none()
    if row is None:
        return False
    if row.user_id == user_id:
        await db.execute(delete(Notification).where(Notification.id == row.id))
    else:
        db.add(NotificationDismissal(org_id=org_id, user_id=user_id, notification_id=row.id))
    return True
