"""Leave module router.

Endpoints
---------
  POST   /leave/applications              — employee creates own request
  GET    /leave/applications              — list (mine=true for self)
  GET    /leave/applications/{id}         — single row, self or admin
  PATCH  /leave/applications/{id}/approve — HR/admin (users:write)
  PATCH  /leave/applications/{id}/reject  — HR/admin (users:write)
  GET    /leave/analytics                 — dashboard aggregations

Authorisation
-------------
* Any authenticated user can **create** their own request and **read** their
  own rows.
* Listing without ``mine=true`` and admin actions (approve/reject, analytics)
  require the existing ``users:read``/``users:write`` scopes so HR roles
  already provisioned with /users admin get this for free.

Rules
-----
* ``end_date`` ≥ ``start_date``.
* An application, once decided, cannot be re-decided — idempotent 409 on
  re-approval/rejection protects the audit log from silent overwrites.
* No self-approval — approvers cannot rubber-stamp their own request.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, extract, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.role import Role, user_roles
from app.models.leave import LeaveApplication, LeaveType, LeaveStatus
from app.schemas.leave import (
    LeaveApplicationCreate, LeaveApplicationResponse,
    LeaveDecision, LeaveAnalytics,
    StatusCount, MonthCount, TypeCount,
)

logger = logging.getLogger("extracare.leave")
router = APIRouter(prefix="/leave", tags=["Leave"])

_can_admin_read = Depends(PermissionChecker("users:read"))
_can_admin_write = Depends(PermissionChecker("users:write"))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _inclusive_days(start: date, end: date) -> int:
    return (end - start).days + 1


def _to_response(app: LeaveApplication) -> LeaveApplicationResponse:
    return LeaveApplicationResponse(
        id=app.id,
        user_id=app.user_id,
        org_id=app.org_id,
        applicant_name=(app.user.full_name if app.user else None),
        applicant_email=(app.user.email if app.user else None),
        leave_type=app.leave_type,
        start_date=app.start_date,
        end_date=app.end_date,
        days=_inclusive_days(app.start_date, app.end_date),
        reason=app.reason,
        status=app.status,
        approver_id=app.approver_id,
        approver_name=(app.approver.full_name if app.approver else None),
        decided_at=app.decided_at,
        decision_note=app.decision_note,
        created_at=app.created_at,
    )


async def _load_application(db: AsyncSession, app_id: str, org_id: str) -> LeaveApplication:
    row = (await db.execute(
        select(LeaveApplication).where(
            LeaveApplication.id == app_id,
            LeaveApplication.org_id == org_id,
            LeaveApplication.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"Leave application not found for id: {app_id}")
    return row


# ── Create ───────────────────────────────────────────────────────────────────

@router.post("/applications", response_model=LeaveApplicationResponse, status_code=201)
async def create_application(
    data: LeaveApplicationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if data.end_date < data.start_date:
        raise HTTPException(status_code=422, detail="end_date: must be on or after start_date")

    app = LeaveApplication(
        org_id=current_user.org_id,
        user_id=current_user.id,
        leave_type=data.leave_type,
        start_date=data.start_date,
        end_date=data.end_date,
        reason=data.reason,
        status=LeaveStatus.PENDING,
    )
    db.add(app)
    await db.flush()
    await db.refresh(app)
    logger.info(
        "leave.create user=%s org=%s type=%s days=%s",
        current_user.id, current_user.org_id, data.leave_type.value,
        _inclusive_days(data.start_date, data.end_date),
    )
    return _to_response(app)


# ── List ─────────────────────────────────────────────────────────────────────

@router.get("/applications", response_model=list[LeaveApplicationResponse])
async def list_applications(
    mine: bool = Query(default=False, description="Restrict to the caller's own rows."),
    status_filter: Optional[LeaveStatus] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List leave applications.

    * ``mine=true`` scopes to the caller — available to any authenticated user.
    * ``mine=false`` returns the full org list — requires ``users:read``.
      Unauthorized callers get 403.
    """
    if not mine:
        # Soft-gate instead of a decorator dependency so self-service users
        # aren't 403'd before we even look at the `mine` flag.
        await _require_admin_read(db, current_user)

    query = select(LeaveApplication).where(
        LeaveApplication.org_id == current_user.org_id,
        LeaveApplication.is_deleted == False,
    )
    if mine:
        query = query.where(LeaveApplication.user_id == current_user.id)
    if status_filter:
        query = query.where(LeaveApplication.status == status_filter)

    query = query.order_by(LeaveApplication.created_at.desc()).limit(limit)
    rows = (await db.execute(query)).scalars().all()
    return [_to_response(r) for r in rows]


async def _permissions_for(db: AsyncSession, user: User) -> set[str]:
    """Flatten every permission on every role the user holds.

    Querying the join table directly avoids a lazy-load on ``user.roles``
    that would require a greenlet context (awkward when a helper is
    called mid-handler after other awaits have already committed).
    """
    rows = (await db.execute(
        select(Role.permissions)
        .join(user_roles, user_roles.c.role_id == Role.id)
        .where(user_roles.c.user_id == user.id)
    )).scalars().all()
    out: set[str] = set()
    for perms in rows:
        if perms:
            out.update(perms)
    return out


def _has_scope(perms: set[str], scope: str) -> bool:
    # '*' is a super-admin wildcard; 'users:*' matches any users:sub scope.
    if "*" in perms or scope in perms:
        return True
    namespace = scope.split(":", 1)[0]
    return f"{namespace}:*" in perms


async def _require_admin_read(db: AsyncSession, user: User) -> None:
    """Inline the permission check so /applications?mine=true stays open."""
    perms = await _permissions_for(db, user)
    if not _has_scope(perms, "users:read"):
        raise HTTPException(status_code=403, detail="users:read required to list all applications")


async def _require_admin_write(db: AsyncSession, user: User) -> None:
    perms = await _permissions_for(db, user)
    if not _has_scope(perms, "users:write"):
        raise HTTPException(status_code=403, detail="users:write required to decide on leave")


# ── Single ───────────────────────────────────────────────────────────────────

@router.get("/applications/{app_id}", response_model=LeaveApplicationResponse)
async def get_application(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    app = await _load_application(db, app_id, current_user.org_id)
    # Applicants can read their own row; otherwise require admin read.
    if app.user_id != current_user.id:
        await _require_admin_read(db, current_user)
    return _to_response(app)


# ── Decide ───────────────────────────────────────────────────────────────────

@router.patch("/applications/{app_id}/approve", response_model=LeaveApplicationResponse)
async def approve_application(
    app_id: str,
    data: Optional[LeaveDecision] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _require_admin_write(db, current_user)
    return await _decide(db, app_id, current_user, LeaveStatus.APPROVED, data.decision_note if data else None)


@router.patch("/applications/{app_id}/reject", response_model=LeaveApplicationResponse)
async def reject_application(
    app_id: str,
    data: Optional[LeaveDecision] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _require_admin_write(db, current_user)
    return await _decide(db, app_id, current_user, LeaveStatus.REJECTED, data.decision_note if data else None)


async def _decide(
    db: AsyncSession, app_id: str, approver: User,
    new_status: LeaveStatus, note: Optional[str],
) -> LeaveApplicationResponse:
    app = await _load_application(db, app_id, approver.org_id)
    if app.status != LeaveStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Leave already {app.status.value}; cannot change.",
        )
    if app.user_id == approver.id:
        # Rubber-stamping your own request defeats the point of the workflow.
        raise HTTPException(status_code=403, detail="You cannot decide on your own leave request.")

    app.status = new_status
    app.approver_id = approver.id
    app.decided_at = datetime.now(timezone.utc)
    app.decision_note = note
    await db.flush()
    await db.refresh(app)
    logger.info(
        "leave.%s app=%s approver=%s org=%s",
        new_status.value, app.id, approver.id, approver.org_id,
    )
    return _to_response(app)


# ── Analytics (HR dashboard) ─────────────────────────────────────────────────

@router.get("/analytics", response_model=LeaveAnalytics, dependencies=[_can_admin_read])
async def leave_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Counts for the HR dashboard.

    * by_status — full lifecycle totals (includes zero buckets so the chart
      renders stable labels).
    * by_month — last 12 calendar months of application creation, chronological.
    * by_type  — distribution across leave types (zero buckets included).
    """
    org_id = current_user.org_id

    total = int((await db.execute(
        select(func.count()).select_from(LeaveApplication).where(
            LeaveApplication.org_id == org_id,
            LeaveApplication.is_deleted == False,
        )
    )).scalar() or 0)

    status_rows = (await db.execute(
        select(LeaveApplication.status, func.count())
        .where(
            LeaveApplication.org_id == org_id,
            LeaveApplication.is_deleted == False,
        )
        .group_by(LeaveApplication.status)
    )).all()
    status_map = {s: c for s, c in status_rows}
    by_status = [StatusCount(status=s, count=status_map.get(s, 0)) for s in LeaveStatus]

    type_rows = (await db.execute(
        select(LeaveApplication.leave_type, func.count())
        .where(
            LeaveApplication.org_id == org_id,
            LeaveApplication.is_deleted == False,
        )
        .group_by(LeaveApplication.leave_type)
    )).all()
    type_map = {t: c for t, c in type_rows}
    by_type = [TypeCount(leave_type=t, count=type_map.get(t, 0)) for t in LeaveType]

    # Last 12 months (inclusive of current), computed in Python for portability.
    today = date.today()
    months: list[str] = []
    y, m = today.year, today.month
    for _ in range(12):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months.reverse()
    window_start = date(*map(int, months[0].split("-")), 1)

    month_rows = (await db.execute(
        select(
            extract("year", LeaveApplication.created_at).label("y"),
            extract("month", LeaveApplication.created_at).label("m"),
            func.count(),
        )
        .where(
            LeaveApplication.org_id == org_id,
            LeaveApplication.is_deleted == False,
            LeaveApplication.created_at >= window_start,
        )
        .group_by("y", "m")
    )).all()
    month_counts = {f"{int(y):04d}-{int(m):02d}": c for y, m, c in month_rows}
    by_month = [MonthCount(month=mo, count=month_counts.get(mo, 0)) for mo in months]

    pending_count = status_map.get(LeaveStatus.PENDING, 0)

    return LeaveAnalytics(
        total=total,
        by_status=by_status,
        by_month=by_month,
        by_type=by_type,
        pending_count=pending_count,
    )
