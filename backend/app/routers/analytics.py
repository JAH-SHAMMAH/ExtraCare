"""
Analytics Router — org-level insights dashboard
"""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import date, timedelta, datetime, timezone

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User, UserStatus
from app.models.organization import Organization
from app.models.audit import AuditLog
from app.models.usage import UsageEvent
from app.models.modules.school import Student, AttendanceRecord, AttendanceStatus
from app.models.modules.hospital import Patient, Appointment, AppointmentStatus
from app.models.modules.business import Employee
from app.core.permissions import PermissionChecker
from app.core.workspace import effective_modules_for_org, workspace_for
from app.services.usage import flush as flush_usage

router = APIRouter(prefix="/analytics", tags=["Analytics"])

# Per-tenant in-memory TTL cache for /overview. The dashboard polls every
# 30s; a 10s TTL means the first poll hits the DB, the next two (and any
# concurrent tabs) are served from memory. Process-local — if we ever run
# multiple workers this gets replaced with Redis, but for now the win is
# worth the simplicity. Keyed by org_id so tenants never see each other.
_OVERVIEW_TTL_SECONDS = 10
_overview_cache: dict[str, tuple[float, dict]] = {}

# Cache hit/miss counters for observability. Logged per request so the
# operator can compute the real hit rate from access logs rather than
# guessing. Reset on process restart — fine for this scope.
_overview_cache_stats = {"hits": 0, "misses": 0}
_logger = logging.getLogger("extracare.analytics")

# Second router — mounted under /organizations/{id}/... for the headline
# dashboard summary introduced in Phase 3. Keeps the existing overview/
# activity-feed routes untouched while giving the dashboard a clean,
# tenant-scoped URL that matches the usage endpoint layout.
org_router = APIRouter(prefix="/organizations", tags=["Analytics"])

_can_read = Depends(PermissionChecker("analytics:read"))
# The immutable audit trail is more sensitive than the activity feed: it must
# require the dedicated audit scope (org_admin only), not the broad
# analytics:read that powers the dashboard activity widgets.
_can_audit = Depends(PermissionChecker("audit_logs:read"))


@router.get("/overview", dependencies=[_can_read])
async def get_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Main dashboard KPIs — adapts based on enabled modules."""
    org_id = current_user.org_id

    cached = _overview_cache.get(org_id)
    if cached and (time.monotonic() - cached[0]) < _OVERVIEW_TTL_SECONDS:
        _overview_cache_stats["hits"] += 1
        hits = _overview_cache_stats["hits"]
        misses = _overview_cache_stats["misses"]
        rate = hits / (hits + misses) if (hits + misses) else 0.0
        _logger.info(
            "overview_cache hit org=%s hits=%d misses=%d hit_rate=%.2f",
            org_id, hits, misses, rate,
        )
        return cached[1]

    _overview_cache_stats["misses"] += 1

    org = (await db.execute(
        select(Organization).where(Organization.id == current_user.org_id)
    )).scalar_one_or_none()
    effective_modules = set(effective_modules_for_org(org)) if org else set()
    workspace = workspace_for(org.industry.value if org and org.industry else None)

    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)

    # Seven COUNTs collapsed into one round-trip via scalar subqueries.
    # AsyncSession doesn't support concurrent use, so asyncio.gather on
    # the same session isn't an option — but every RDBMS we target can
    # evaluate independent scalar subselects in a single SELECT. The
    # dashboard polls this every 30s, so the round-trip savings compound.
    total_users_q = select(func.count()).select_from(User).where(
        User.org_id == org_id, User.is_deleted == False
    ).scalar_subquery()
    active_users_q = select(func.count()).select_from(User).where(
        User.org_id == org_id, User.status == UserStatus.ACTIVE, User.is_deleted == False
    ).scalar_subquery()
    recent_logins_q = select(func.count()).select_from(User).where(
        User.org_id == org_id, User.last_login_at >= one_day_ago
    ).scalar_subquery()
    total_students_q = (
        select(func.count()).select_from(Student).where(
            Student.org_id == org_id, Student.is_deleted == False
        ).scalar_subquery()
        if "school" in effective_modules else select(0).scalar_subquery()
    )
    today_attendance_q = (
        select(func.count()).select_from(AttendanceRecord).where(
            AttendanceRecord.org_id == org_id, AttendanceRecord.date == today
        ).scalar_subquery()
        if "school" in effective_modules else select(0).scalar_subquery()
    )
    total_patients_q = (
        select(func.count()).select_from(Patient).where(
            Patient.org_id == org_id, Patient.is_deleted == False
        ).scalar_subquery()
        if "hospital" in effective_modules else select(0).scalar_subquery()
    )
    todays_appointments_q = (
        select(func.count()).select_from(Appointment).where(
            Appointment.org_id == org_id,
            Appointment.appointment_date == today,
            Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]),
        ).scalar_subquery()
        if "hospital" in effective_modules else select(0).scalar_subquery()
    )
    total_employees_q = (
        select(func.count()).select_from(Employee).where(
            Employee.org_id == org_id, Employee.is_deleted == False
        ).scalar_subquery()
        if "business" in effective_modules else select(0).scalar_subquery()
    )

    row = (await db.execute(
        select(
            total_users_q.label("total_users"),
            active_users_q.label("active_users"),
            recent_logins_q.label("recent_logins"),
            total_students_q.label("total_students"),
            today_attendance_q.label("today_attendance"),
            total_patients_q.label("total_patients"),
            todays_appointments_q.label("todays_appointments"),
            total_employees_q.label("total_employees"),
        )
    )).one()

    payload = {
        "users": {
            "total": row.total_users,
            "active": row.active_users,
            "online_today": row.recent_logins,
        },
        "workspace": {
            "type": workspace.type.value,
            "label": workspace.label,
            "modules_enabled": sorted(effective_modules),
        },
        "school": {
            "total_students": row.total_students,
            "attendance_today": row.today_attendance,
        },
        "hospital": {
            "total_patients": row.total_patients,
            "appointments_today": row.todays_appointments,
        },
        "business": {
            "total_employees": row.total_employees,
        },
        "period": {
            "start": thirty_days_ago.isoformat(),
            "end": today.isoformat(),
        }
    }
    _overview_cache[org_id] = (time.monotonic(), payload)
    hits = _overview_cache_stats["hits"]
    misses = _overview_cache_stats["misses"]
    rate = hits / (hits + misses) if (hits + misses) else 0.0
    _logger.info(
        "overview_cache miss org=%s hits=%d misses=%d hit_rate=%.2f",
        org_id, hits, misses, rate,
    )
    return payload


@router.get("/activity-feed", dependencies=[_can_read])
async def get_activity_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Project only the columns the feed renders — AuditLog has heavy JSON
    # columns (old_values, new_values, metadata_, user_agent) that the
    # dashboard never touches. Pulling them wastes bytes on the wire and
    # adds real latency on rows with large diffs.
    result = await db.execute(
        select(
            AuditLog.id,
            AuditLog.action,
            AuditLog.resource_type,
            AuditLog.resource_label,
            AuditLog.actor_email,
            AuditLog.severity,
            AuditLog.created_at,
        )
        .where(AuditLog.org_id == current_user.org_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [
        {
            "id": row.id,
            "action": row.action.value if hasattr(row.action, "value") else row.action,
            "resource_type": row.resource_type,
            "resource_label": row.resource_label,
            "actor_email": row.actor_email,
            "severity": row.severity,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in result
    ]


@router.get("/audit-log", dependencies=[_can_audit])
async def get_audit_log(
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Immutable audit trail. Same projection as the activity feed but gated by
    `audit_logs:read` (org_admin), so the Audit Log page is not visible to roles
    that only hold the broader `analytics:read` (e.g. teachers/staff)."""
    result = await db.execute(
        select(
            AuditLog.id,
            AuditLog.action,
            AuditLog.resource_type,
            AuditLog.resource_label,
            AuditLog.actor_email,
            AuditLog.severity,
            AuditLog.created_at,
        )
        .where(AuditLog.org_id == current_user.org_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [
        {
            "id": row.id,
            "action": row.action.value if hasattr(row.action, "value") else row.action,
            "resource_type": row.resource_type,
            "resource_label": row.resource_label,
            "actor_email": row.actor_email,
            "severity": row.severity,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in result
    ]


# ── Per-tenant dashboard summary ────────────────────────────────────────────

def _authorize_usage(current_user: User, org_id: str) -> None:
    """Same permission contract as /organizations/{id}/usage — reuses the
    audit read scope rather than inventing an `analytics:read` split, so
    admins don't have to hand out a second permission for dashboards."""
    if current_user.org_id != org_id and not current_user.is_superadmin:
        raise HTTPException(status_code=403, detail="Cross-tenant analytics access denied.")
    if current_user.org_id == org_id and not current_user.has_permission("audit_logs:read"):
        raise HTTPException(status_code=403, detail="Permission denied. Required: 'audit_logs:read'")


async def _window_total(db: AsyncSession, org_id: str, since, until) -> int:
    return int((await db.execute(
        select(func.coalesce(func.sum(UsageEvent.count), 0)).where(
            UsageEvent.org_id == org_id,
            UsageEvent.date_bucket >= since,
            UsageEvent.date_bucket <= until,
        )
    )).scalar() or 0)


async def _event_total(db: AsyncSession, org_id: str, since, until, event_type: str) -> int:
    return int((await db.execute(
        select(func.coalesce(func.sum(UsageEvent.count), 0)).where(
            UsageEvent.org_id == org_id,
            UsageEvent.date_bucket >= since,
            UsageEvent.date_bucket <= until,
            UsageEvent.event_type == event_type,
        )
    )).scalar() or 0)


@org_router.get("/{org_id}/analytics/summary", summary="Headline metrics for the tenant dashboard")
async def analytics_summary(
    org_id: str,
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Rolled-up headline metrics for the dashboard shell. Everything is
    derived from `usage_events` — same aggregates /usage already produces,
    just reshaped for three cards + a top-module callout + growth %."""
    _authorize_usage(current_user, org_id)
    await flush_usage(session=db)

    today = datetime.now(timezone.utc).date()
    since = today - timedelta(days=days - 1)
    prev_until = since - timedelta(days=1)
    prev_since = prev_until - timedelta(days=days - 1)

    total_requests = await _event_total(db, org_id, since, today, "request")
    users_created = await _event_total(db, org_id, since, today, "user_created")
    onboarding_completed = await _event_total(db, org_id, since, today, "onboarding_completed")

    top_row = (await db.execute(
        select(UsageEvent.module, func.sum(UsageEvent.count).label("total"))
        .where(
            UsageEvent.org_id == org_id,
            UsageEvent.date_bucket >= since,
            UsageEvent.date_bucket <= today,
        )
        .group_by(UsageEvent.module)
        .order_by(func.sum(UsageEvent.count).desc())
        .limit(1)
    )).first()
    top_module = {"module": top_row[0], "count": int(top_row[1])} if top_row else None

    current_total = await _window_total(db, org_id, since, today)
    previous_total = await _window_total(db, org_id, prev_since, prev_until)
    # Growth is undefined when the prior window is empty — report None so
    # the dashboard renders "new" rather than dividing by zero.
    if previous_total == 0:
        growth_pct = None
    else:
        growth_pct = round(((current_total - previous_total) / previous_total) * 100, 2)

    return {
        "org_id": org_id,
        "window_days": days,
        "since": since.isoformat(),
        "until": today.isoformat(),
        "totals": {
            "requests": total_requests,
            "users_created": users_created,
            "onboarding_completed": onboarding_completed,
            "all_events": current_total,
        },
        "top_module": top_module,
        "growth": {
            "previous_total": previous_total,
            "current_total": current_total,
            "delta_pct": growth_pct,
        },
    }
