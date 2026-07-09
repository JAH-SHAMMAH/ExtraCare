"""
Attendance ingestion service
============================
The single entry point for getting check-in/check-out events INTO the portal,
regardless of where they came from (staff UI, CSV import, or a future ZKTeco
biometric device). This is the extension point the brief calls for:

    ZKTeco device ──▶ ZKTecoAdapter ──▶ ingest(events) ──▶ portal
                       (future)          (this service)

The adapter is the only new code a real ZKTeco integration needs — it just
translates raw device punches into ``AttendanceEventIn`` and calls ``ingest``.
Everything downstream (dedup, daily-record derivation, audit, parent
notifications) already lives here, so the integration stays a thin shim.

Guarantees:
  • Idempotent — a punch with the same (source, external_ref) lands once.
  • Non-destructive — derives/updates the existing daily ``AttendanceRecord``;
    never deletes or rewrites history.
  • Safe notifications — a failed parent alert never fails the ingest.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timezone

try:  # Python 3.9+ stdlib; guarded so the module never hard-fails on import.
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.audit import AuditAction
from app.models.notification import TYPE_ATTENDANCE
from app.models.modules.school import (
    AttendanceEvent,
    AttendanceEventSource,
    AttendanceEventType,
    AttendanceRecord,
    AttendanceSettings,
    AttendanceStatus,
    ParentGuardian,
    Student,
)
from app.services import notifications as _notif
from app.services.audit_service import log_action

logger = logging.getLogger("extracare.attendance")
settings = get_settings()


# ── Time helpers ─────────────────────────────────────────────────────────────

def to_local(dt: datetime, tz_name: str | None) -> datetime:
    """Render an instant in the school's local timezone. Naive datetimes are
    assumed UTC. Falls back to UTC if the zone is unknown."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if ZoneInfo is None:
        return dt.astimezone(timezone.utc)
    try:
        return dt.astimezone(ZoneInfo(tz_name or "Africa/Lagos"))
    except Exception:
        return dt.astimezone(timezone.utc)


def format_clock(local_dt: datetime) -> str:
    """'7:32 AM' — cross-platform (no %-I), strips the leading hour zero."""
    return local_dt.strftime("%I:%M %p").lstrip("0")


def _parse_hhmm(value: str, default: time) -> time:
    try:
        hh, mm = value.split(":")
        return time(int(hh), int(mm))
    except Exception:
        return default


def default_late_after() -> time:
    """Global fallback late cutoff from the ``SCHOOL_LATE_AFTER`` env constant,
    used when a school hasn't configured its own in Attendance Setup."""
    return _parse_hhmm(settings.SCHOOL_LATE_AFTER, time(8, 0))


async def _late_after_for_org(db: AsyncSession, org) -> time:
    """Per-org late cutoff (Attendance Setup) with the env value as fallback.
    Read-only — never creates a settings row from the ingestion path."""
    row = (
        await db.execute(
            select(AttendanceSettings.late_after_time).where(AttendanceSettings.org_id == org.id)
        )
    ).scalar_one_or_none()
    return row if row is not None else default_late_after()


# ── Result type ──────────────────────────────────────────────────────────────

@dataclass
class IngestResult:
    created: int = 0
    duplicates: int = 0
    notified: int = 0
    errors: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "created": self.created,
            "duplicates": self.duplicates,
            "notified": self.notified,
            "errors": self.errors,
        }


# ── Service ──────────────────────────────────────────────────────────────────

async def ingest(
    db: AsyncSession,
    org,
    events,
    *,
    recorded_by: str | None = None,
    notify_parents: bool = True,
) -> IngestResult:
    """Ingest a batch of attendance events for one organisation.

    ``events`` is a list of ``AttendanceEventIn`` (or any object exposing the
    same attributes). The caller owns the transaction/commit. Returns a summary
    of what happened so callers (and adapters) can log/report.
    """
    result = IngestResult()
    late_after = await _late_after_for_org(db, org)

    for idx, ev in enumerate(events):
        try:
            source = AttendanceEventSource(getattr(ev, "source", None) or "manual")
            event_type = AttendanceEventType(ev.event_type)
            event_time = ev.event_time or datetime.now(timezone.utc)
            external_ref = getattr(ev, "external_ref", None)

            student = (
                await db.execute(
                    select(Student).where(
                        Student.id == ev.student_id,
                        Student.org_id == org.id,
                        Student.is_deleted == False,  # noqa: E712
                    )
                )
            ).scalar_one_or_none()
            if student is None:
                result.errors.append(
                    {"index": idx, "student_id": ev.student_id, "reason": "student_not_found"}
                )
                continue

            # Idempotent dedup on the device-side reference.
            if external_ref:
                dup = (
                    await db.execute(
                        select(AttendanceEvent.id).where(
                            AttendanceEvent.org_id == org.id,
                            AttendanceEvent.source == source,
                            AttendanceEvent.external_ref == external_ref,
                        )
                    )
                ).scalar_one_or_none()
                if dup is not None:
                    result.duplicates += 1
                    continue

            row = AttendanceEvent(
                org_id=org.id,
                student_id=student.id,
                event_type=event_type,
                event_time=event_time,
                source=source,
                external_ref=external_ref,
                device_id=getattr(ev, "device_id", None),
                raw_payload=getattr(ev, "raw_payload", None),
                recorded_by=recorded_by,
                notes=getattr(ev, "notes", None),
            )
            db.add(row)
            await db.flush()
            result.created += 1

            # Derive/refresh the daily roll-call record (non-destructive).
            await _upsert_daily_record(db, org, student, event_type, event_time, late_after)

            # Immutable audit trail. Reuse RECORD_CREATED to avoid an enum
            # migration; resource_type distinguishes attendance events.
            await log_action(
                db,
                AuditAction.RECORD_CREATED,
                org.id,
                resource_type="AttendanceEvent",
                resource_id=row.id,
                resource_label=f"{student.first_name} {student.last_name}",
                metadata={
                    "event_type": event_type.value,
                    "source": source.value,
                    "device_id": getattr(ev, "device_id", None),
                    "external_ref": external_ref,
                },
            )

            if notify_parents:
                sent = await _notify_guardians(db, org, student, event_type, event_time)
                result.notified += sent
        except Exception as exc:  # one bad event must not abort the batch
            logger.warning("attendance ingest failed at index %s: %s", idx, exc)
            result.errors.append(
                {"index": idx, "student_id": getattr(ev, "student_id", None), "reason": str(exc)}
            )

    return result


async def _upsert_daily_record(
    db: AsyncSession,
    org,
    student: Student,
    event_type: AttendanceEventType,
    event_time: datetime,
    late_after: time,
) -> None:
    """Fold an event into the once-per-day ``AttendanceRecord``.

    Check-in sets present/late from the local arrival time. Check-out only
    ensures a record exists (so a child who checked out is never counted
    absent) without overriding a status already set by check-in/roll-call.
    Skipped when the student has no class — ``AttendanceRecord.class_id`` is
    NOT NULL — leaving the event captured for history regardless.
    """
    if student.class_id is None:
        return

    local_dt = to_local(event_time, getattr(org, "timezone", None))
    rec_date = local_dt.date()

    existing = (
        await db.execute(
            select(AttendanceRecord)
            .where(
                AttendanceRecord.student_id == student.id,
                AttendanceRecord.date == rec_date,
                AttendanceRecord.org_id == org.id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    if event_type == AttendanceEventType.CHECK_IN:
        status = (
            AttendanceStatus.LATE if local_dt.time() > late_after else AttendanceStatus.PRESENT
        )
        if existing is None:
            db.add(
                AttendanceRecord(
                    org_id=org.id,
                    student_id=student.id,
                    class_id=student.class_id,
                    date=rec_date,
                    status=status,
                    notes="Auto-derived from check-in event",
                )
            )
        else:
            existing.status = status
    else:  # CHECK_OUT — ensure presence, don't downgrade a set status
        if existing is None:
            db.add(
                AttendanceRecord(
                    org_id=org.id,
                    student_id=student.id,
                    class_id=student.class_id,
                    date=rec_date,
                    status=AttendanceStatus.PRESENT,
                    notes="Auto-derived from check-out event",
                )
            )


async def _notify_guardians(
    db: AsyncSession,
    org,
    student: Student,
    event_type: AttendanceEventType,
    event_time: datetime,
) -> int:
    """In-app alert to every guardian of the student. Returns the count sent.

    Copy matches the brief exactly:
      "Ferdinand has successfully checked into Fairview School at 7:32 AM."
      "Ferdinand has successfully checked out of Fairview School at 3:15 PM."

    Channel is in-app only for v1; the payload carries everything an SMS/push
    fan-out worker would need to deliver the same alert later (outbox-ready).
    """
    school_name = getattr(org, "name", None) or settings.SCHOOL_NAME
    clock = format_clock(to_local(event_time, getattr(org, "timezone", None)))
    if event_type == AttendanceEventType.CHECK_IN:
        title = "Arrival confirmed"
        message = f"{student.first_name} has successfully checked into {school_name} at {clock}."
    else:
        title = "Departure confirmed"
        message = f"{student.first_name} has successfully checked out of {school_name} at {clock}."

    guardian_user_ids = (
        await db.execute(
            select(ParentGuardian.user_id).where(
                ParentGuardian.student_id == student.id,
                ParentGuardian.org_id == org.id,
            )
        )
    ).scalars().all()

    payload = {
        "student_id": student.id,
        "student_name": f"{student.first_name} {student.last_name}",
        "event_type": event_type.value,
        "event_time": event_time.isoformat(),
        "clock": clock,
    }

    sent = 0
    for user_id in guardian_user_ids:
        await _notif.notify(
            org_id=org.id,
            user_id=user_id,
            type=TYPE_ATTENDANCE,
            title=title,
            message=message,
            payload=payload,
            session=db,
        )
        sent += 1
    return sent
