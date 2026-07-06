"""
Attendance Router
=================
Event-sourced attendance for the school: timestamped check-in/check-out events
that derive the daily roll-call record and fire instant parent notifications.

RBAC (reuses the school namespace so existing roles work unchanged):
  - school:read   → view daily/monthly summaries and student history
  - school:write  → record manual attendance + bulk-ingest device events

Visibility: admins/teachers/HR (school:write) see all students; parents and
students see only their own children/record (guardian-scoped).

ZKTeco extension point: ``POST /attendance/events/ingest`` is the HTTP target a
future ZKTeco adapter (or sync worker) pushes device punches to. It maps each
punch to an ``AttendanceEventIn`` and posts the batch — dedup, daily-record
derivation, audit, and notifications all happen server-side. A device-token
auth scheme can be layered on this route later without touching the service.
"""

from datetime import date as date_type, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.organization import Organization
from app.models.modules.school import (
    AttendanceEvent,
    AttendanceRecord,
    AttendanceStatus,
    ParentGuardian,
    Student,
)
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker
from app.schemas.attendance import (
    AttendanceEventIn,
    AttendanceEventOut,
    AttendanceIngestRequest,
    DailyAttendanceRow,
    DailyAttendanceSummary,
    IngestResultOut,
    ManualAttendanceIn,
    MonthlyAttendanceSummary,
)
from app.services import attendance as attendance_service

router = APIRouter(
    prefix="/attendance",
    tags=["Attendance"],
    dependencies=[Depends(require_role_module("school"))],
)

_can_read = Depends(PermissionChecker("school:attendance:read"))
_can_write = Depends(PermissionChecker("school:attendance:write"))


async def _load_org(db: AsyncSession, current_user: User) -> Organization:
    org = (
        await db.execute(select(Organization).where(Organization.id == current_user.org_id))
    ).scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=400, detail="Organization not found.")
    return org


def _local_day_bounds(target: date_type, tz_name: str | None) -> tuple[datetime, datetime]:
    """UTC [start, end) instants covering the school-local calendar day."""
    if attendance_service.ZoneInfo is not None:
        try:
            tz = attendance_service.ZoneInfo(tz_name or "Africa/Lagos")
        except Exception:
            tz = timezone.utc
    else:  # pragma: no cover
        tz = timezone.utc
    start_local = datetime.combine(target, time.min).replace(tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _today_local(tz_name: str | None) -> date_type:
    return attendance_service.to_local(datetime.now(timezone.utc), tz_name).date()


async def _assert_can_view_student(
    db: AsyncSession, current_user: User, org: Organization, student_id: str
) -> None:
    """Staff (school:write) see everyone; otherwise the caller must be a
    guardian of the student or the student themselves."""
    if current_user.is_superadmin or current_user.has_permission("school:write"):
        return
    is_guardian = (
        await db.execute(
            select(ParentGuardian.id).where(
                ParentGuardian.org_id == org.id,
                ParentGuardian.student_id == student_id,
                ParentGuardian.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if is_guardian:
        return
    is_self = (
        await db.execute(
            select(Student.id).where(
                Student.id == student_id,
                Student.org_id == org.id,
                Student.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if is_self:
        return
    raise HTTPException(
        status_code=403,
        detail="You can only view attendance for your own children.",
    )


# ── Ingestion ────────────────────────────────────────────────────────────────


@router.post("/events/ingest", response_model=IngestResultOut, dependencies=[_can_write])
async def ingest_events(
    payload: AttendanceIngestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Bulk-ingest attendance events. The target for a future ZKTeco adapter.
    Idempotent on (source, external_ref) — re-pushing a punch is a no-op."""
    org = await _load_org(db, current_user)
    result = await attendance_service.ingest(
        db, org, payload.events, recorded_by=current_user.id
    )
    return IngestResultOut(**result.as_dict())


@router.post("/manual", response_model=IngestResultOut, status_code=201, dependencies=[_can_write])
async def record_manual(
    payload: ManualAttendanceIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Staff records a single check-in/out from the portal (triggers the same
    daily-record derivation + parent notification as a device punch)."""
    org = await _load_org(db, current_user)
    event = AttendanceEventIn(
        student_id=payload.student_id,
        event_type=payload.event_type,
        event_time=payload.event_time,
        source="manual",
        notes=payload.notes,
    )
    result = await attendance_service.ingest(db, org, [event], recorded_by=current_user.id)
    if result.errors:
        raise HTTPException(status_code=400, detail=result.errors[0]["reason"])
    return IngestResultOut(**result.as_dict())


# ── Reads ────────────────────────────────────────────────────────────────────


@router.get("/daily", response_model=DailyAttendanceSummary, dependencies=[_can_read])
async def daily_summary(
    date: date_type | None = None,
    class_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Present/late/absent breakdown for one day, with per-student rows and
    first check-in / last check-out times."""
    org = await _load_org(db, current_user)
    # This view exposes EVERY student's name + status for the day, so it is
    # staff-only. Guardians/students use /student/{id}/history for their own.
    if not current_user.has_permission("school:students:read"):
        raise HTTPException(status_code=403, detail="School-wide attendance is staff-only.")
    target = date or _today_local(getattr(org, "timezone", None))

    student_q = select(Student).where(
        Student.org_id == org.id,
        Student.is_deleted == False,  # noqa: E712
        Student.is_active == True,  # noqa: E712
    )
    if class_id:
        student_q = student_q.where(Student.class_id == class_id)
    students = (await db.execute(student_q)).scalars().all()

    record_q = select(AttendanceRecord).where(
        AttendanceRecord.org_id == org.id,
        AttendanceRecord.date == target,
    )
    if class_id:
        record_q = record_q.where(AttendanceRecord.class_id == class_id)
    records = (await db.execute(record_q)).scalars().all()
    rec_by_student = {r.student_id: r for r in records}

    # First check-in / last check-out per student for the local day.
    start_utc, end_utc = _local_day_bounds(target, getattr(org, "timezone", None))
    events = (
        await db.execute(
            select(AttendanceEvent).where(
                AttendanceEvent.org_id == org.id,
                AttendanceEvent.event_time >= start_utc,
                AttendanceEvent.event_time < end_utc,
            )
        )
    ).scalars().all()
    first_in: dict[str, datetime] = {}
    last_out: dict[str, datetime] = {}
    from app.models.modules.school import AttendanceEventType
    for e in events:
        if e.event_type == AttendanceEventType.CHECK_IN:
            if e.student_id not in first_in or e.event_time < first_in[e.student_id]:
                first_in[e.student_id] = e.event_time
        else:
            if e.student_id not in last_out or e.event_time > last_out[e.student_id]:
                last_out[e.student_id] = e.event_time

    present = late = excused = 0
    rows: list[DailyAttendanceRow] = []
    for s in students:
        rec = rec_by_student.get(s.id)
        status = rec.status.value if rec else None
        if rec and rec.status == AttendanceStatus.PRESENT:
            present += 1
        elif rec and rec.status == AttendanceStatus.LATE:
            late += 1
        elif rec and rec.status == AttendanceStatus.EXCUSED:
            excused += 1
        rows.append(
            DailyAttendanceRow(
                student_id=s.id,
                student_name=f"{s.first_name} {s.last_name}",
                status=status,
                first_check_in=first_in.get(s.id),
                last_check_out=last_out.get(s.id),
            )
        )

    total = len(students)
    absent = total - present - late - excused
    return DailyAttendanceSummary(
        date=target,
        present=present,
        late=late,
        excused=excused,
        absent=max(absent, 0),
        total_students=total,
        rows=rows,
    )


@router.get(
    "/student/{student_id}/history",
    response_model=list[AttendanceEventOut],
    dependencies=[_can_read],
)
async def student_history(
    student_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Recent check-in/out events for one student. Guardian-scoped: parents and
    students only see their own."""
    org = await _load_org(db, current_user)
    await _assert_can_view_student(db, current_user, org, student_id)
    rows = (
        await db.execute(
            select(AttendanceEvent)
            .where(
                AttendanceEvent.org_id == org.id,
                AttendanceEvent.student_id == student_id,
            )
            .order_by(AttendanceEvent.event_time.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [AttendanceEventOut.model_validate(r) for r in rows]


@router.get("/monthly", response_model=MonthlyAttendanceSummary, dependencies=[_can_read])
async def monthly_summary(
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
    student_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Status totals across a month. Scoped to one student when ``student_id``
    is supplied (guardian-checked); otherwise school-wide."""
    org = await _load_org(db, current_user)
    if student_id:
        await _assert_can_view_student(db, current_user, org, student_id)
    elif not current_user.has_permission("school:students:read"):
        # No student filter → school-wide totals, which is staff-only. A
        # guardian must scope the query to a child they're linked to.
        raise HTTPException(
            status_code=403,
            detail="Provide a student_id; school-wide attendance is staff-only.",
        )

    start = date_type(year, month, 1)
    end = date_type(year + 1, 1, 1) if month == 12 else date_type(year, month + 1, 1)

    q = (
        select(AttendanceRecord.status, func.count())
        .where(
            AttendanceRecord.org_id == org.id,
            AttendanceRecord.date >= start,
            AttendanceRecord.date < end,
        )
        .group_by(AttendanceRecord.status)
    )
    if student_id:
        q = q.where(AttendanceRecord.student_id == student_id)
    counts = {status: n for status, n in (await db.execute(q)).all()}

    days_q = select(func.count(func.distinct(AttendanceRecord.date))).where(
        AttendanceRecord.org_id == org.id,
        AttendanceRecord.date >= start,
        AttendanceRecord.date < end,
    )
    if student_id:
        days_q = days_q.where(AttendanceRecord.student_id == student_id)
    days_recorded = int((await db.execute(days_q)).scalar() or 0)

    return MonthlyAttendanceSummary(
        year=year,
        month=month,
        present=counts.get(AttendanceStatus.PRESENT, 0),
        late=counts.get(AttendanceStatus.LATE, 0),
        absent=counts.get(AttendanceStatus.ABSENT, 0),
        excused=counts.get(AttendanceStatus.EXCUSED, 0),
        days_recorded=days_recorded,
    )
