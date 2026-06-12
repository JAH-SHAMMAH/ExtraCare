"""
Usage read API.

Aggregation happens at read time, not write time — rows in `usage_events`
are already daily-bucketed, so totals are cheap GROUP BYs. Write path is
middleware + explicit `track()` calls; see services/usage.py.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.usage import UsageEvent
from app.models.user import User
from app.services.usage import flush


router = APIRouter(prefix="/organizations", tags=["Usage"])


def _authorize(current_user: User, org_id: str) -> None:
    if current_user.org_id != org_id and not current_user.is_superadmin:
        raise HTTPException(status_code=403, detail="Cross-tenant usage access denied.")
    if current_user.org_id == org_id and not current_user.has_permission("audit_logs:read"):
        # Reuse the audit permission — "operational data" gate without
        # inventing a new scope for one endpoint.
        raise HTTPException(status_code=403, detail="Permission denied. Required: 'audit_logs:read'")


async def _sum_in_window(
    db: AsyncSession, org_id: str, since, until, group_col=None
):
    """Helper: SUM(count) over a window, optionally grouped by a column."""
    q = select(func.coalesce(func.sum(UsageEvent.count), 0)).where(
        UsageEvent.org_id == org_id,
        UsageEvent.date_bucket >= since,
        UsageEvent.date_bucket <= until,
    )
    if group_col is not None:
        q = select(group_col, func.sum(UsageEvent.count)).where(
            UsageEvent.org_id == org_id,
            UsageEvent.date_bucket >= since,
            UsageEvent.date_bucket <= until,
        ).group_by(group_col)
        return (await db.execute(q)).all()
    return int((await db.execute(q)).scalar() or 0)


@router.get("/{org_id}/usage", summary="Per-tenant usage totals")
async def get_usage(
    org_id: str,
    days: int = Query(30, ge=1, le=90),
    group_by: Literal["module", "event", "day"] | None = Query(
        None,
        description="Return only one bucket instead of all three. Omit for full payload.",
    ),
    compare_previous: bool = Query(
        False,
        description="Also return totals for the immediately-preceding window of the same length, with a growth delta.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return usage for the last `days`. Org admins see their own tenant;
    super-admins can query any tenant."""
    _authorize(current_user, org_id)

    # Flush the in-memory buffer through the request's own session so the
    # caller sees up-to-the-second counts. Passing `session=db` keeps us
    # inside the active transaction (important for the test overrides).
    await flush(session=db)

    today = datetime.now(timezone.utc).date()
    since = today - timedelta(days=days - 1)

    # Column for the optional single-bucket projection.
    group_col_map = {
        "module": UsageEvent.module,
        "event": UsageEvent.event_type,
        "day": UsageEvent.date_bucket,
    }

    payload: dict = {
        "org_id": org_id,
        "window_days": days,
        "since": since.isoformat(),
        "until": today.isoformat(),
    }

    if group_by is not None:
        # Single-bucket projection — cheaper response for dashboard widgets
        # that only need one dimension.
        col = group_col_map[group_by]
        rows = await _sum_in_window(db, org_id, since, today, group_col=col)
        if group_by == "day":
            payload["series"] = [
                {"date": d.isoformat(), "count": int(n)} for d, n in rows
            ]
        else:
            payload["series"] = [
                {"key": str(k), "count": int(n)} for k, n in rows
            ]
        total = sum(int(n) for _, n in rows)
    else:
        # Full payload (backwards-compatible with Phase 2 shape).
        by_module_rows = await _sum_in_window(db, org_id, since, today, group_col=UsageEvent.module)
        by_event_rows = await _sum_in_window(db, org_id, since, today, group_col=UsageEvent.event_type)
        daily_rows = (await db.execute(
            select(UsageEvent.date_bucket, func.sum(UsageEvent.count))
            .where(UsageEvent.org_id == org_id, UsageEvent.date_bucket >= since)
            .group_by(UsageEvent.date_bucket)
            .order_by(UsageEvent.date_bucket.asc())
        )).all()
        total = sum(int(n) for _, n in by_module_rows) if by_module_rows else 0
        payload["by_module"] = {m: int(n) for m, n in by_module_rows}
        payload["by_event"] = {e: int(n) for e, n in by_event_rows}
        payload["daily"] = [{"date": d.isoformat(), "count": int(n)} for d, n in daily_rows]

    payload["total"] = total

    if compare_previous:
        # Mirror window: same length, immediately preceding. We purposely
        # DON'T overlap with the current window so deltas are clean.
        prev_until = since - timedelta(days=1)
        prev_since = prev_until - timedelta(days=days - 1)
        prev_total = await _sum_in_window(db, org_id, prev_since, prev_until)
        # Growth % — undefined when prior is 0, so treat that as "new" and
        # report None rather than dividing. Frontends render a dash.
        if prev_total == 0:
            delta_pct = None
        else:
            delta_pct = round(((total - prev_total) / prev_total) * 100, 2)
        payload["compare"] = {
            "previous_since": prev_since.isoformat(),
            "previous_until": prev_until.isoformat(),
            "previous_total": prev_total,
            "delta_pct": delta_pct,
        }

    return payload
