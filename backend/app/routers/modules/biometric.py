"""Biometric Devices router (Batch 7), prefix ``/biometric``.

Registers ZKTeco-style terminals, maps biometric ids → students, and ingests
punches into the EXISTING attendance event layer. Key guarantees:

  • Idempotency — dedup is on the **device record id** (``external_ref``), NOT the
    timestamp, so a buffered re-push (even after a clock-drift correction) lands
    once. A synthetic ref is used only when the device exposes no record id.
  • Authoritative clock — the device punch time is used for ``event_time``; the
    server stamps receipt and surfaces ``clock_skew_seconds`` on the device
    (visible, never trusted to mint a new punch).
  • Unmapped punches — a punch from an unknown device or biometric id is
    QUARANTINED (never dropped, never auto-creates a student) and resolvable.

RBAC: all endpoints ``settings:write`` (admin / sync-service account).
NOTE: ``/biometric/ingest`` needs per-device token auth before production
hardware connects — tracked as a RELEASE BLOCKER in BUILD_PROGRESS.md.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.tenant import require_module
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.organization import Organization
from app.models.modules.school import Student, AttendanceEvent
from app.models.modules.platform import BiometricDevice, BiometricEnrollment, UnmappedPunch
from app.schemas.platform import (
    DeviceCreate, DeviceUpdate, DeviceResponse,
    EnrollmentCreate, EnrollmentResponse,
    PunchIn, IngestPunchesRequest, IngestSummary,
    UnmappedPunchResponse, ResolvePunchRequest,
)
from app.schemas.attendance import AttendanceEventIn
from app.services import attendance as attendance_service

router = APIRouter(prefix="/biometric", tags=["Biometric Devices"], dependencies=[Depends(require_module("school"))])

_read = Depends(PermissionChecker("settings:read"))
_write = Depends(PermissionChecker("settings:write"))

_VALID_DIR = {"check_in", "check_out"}


def _direction(d: str | None) -> str:
    if not d:
        return "check_in"
    d = d.lower()
    if d in _VALID_DIR:
        return d
    return "check_out" if "out" in d else "check_in"


def _external_ref(p: PunchIn, direction: str, event_time: datetime) -> str:
    if p.record_id:
        return p.record_id   # the device's own id — authoritative dedup key
    # Synthetic, deterministic ref (same punch → same ref) when no device id.
    raw = f"{p.device_id}:{p.biometric_user_id}:{event_time.replace(microsecond=0).isoformat()}:{direction}"
    return "syn-" + hashlib.sha1(raw.encode()).hexdigest()[:24]


async def _org(db, org_id) -> Organization:
    return (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one()


async def _student_name(db, org_id, sid) -> str | None:
    r = (await db.execute(select(Student.first_name, Student.last_name).where(Student.id == sid, Student.org_id == org_id))).first()
    return f"{r.first_name} {r.last_name}".strip() if r else None


# ── Devices ─────────────────────────────────────────────────────────────────────

def _device_response(d: BiometricDevice) -> DeviceResponse:
    return DeviceResponse(id=d.id, device_id=d.device_id, name=d.name, location=d.location, is_active=d.is_active,
                          last_seen_at=d.last_seen_at, clock_skew_seconds=d.clock_skew_seconds, notes=d.notes,
                          created_at=d.created_at, org_id=d.org_id)


@router.get("/devices", response_model=list[DeviceResponse], dependencies=[_read])
async def list_devices(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(BiometricDevice).where(BiometricDevice.org_id == current_user.org_id).order_by(BiometricDevice.name))).scalars().all()
    return [_device_response(d) for d in rows]


@router.post("/devices", response_model=DeviceResponse, status_code=201, dependencies=[_write])
async def register_device(payload: DeviceCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = BiometricDevice(device_id=payload.device_id, name=payload.name, location=payload.location, notes=payload.notes,
                        is_active=True, org_id=current_user.org_id)
    db.add(d)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Device '{payload.device_id}' is already registered.")
    return _device_response(d)


@router.patch("/devices/{device_pk}", response_model=DeviceResponse, dependencies=[_write])
async def update_device(device_pk: str, payload: DeviceUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = (await db.execute(select(BiometricDevice).where(BiometricDevice.id == device_pk, BiometricDevice.org_id == current_user.org_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Device not found.")
    for f, v in payload.model_dump(exclude_unset=True).items():
        setattr(d, f, v)
    await db.flush()
    return _device_response(d)


@router.delete("/devices/{device_pk}", status_code=204, dependencies=[_write])
async def delete_device(device_pk: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = (await db.execute(select(BiometricDevice).where(BiometricDevice.id == device_pk, BiometricDevice.org_id == current_user.org_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Device not found.")
    await db.delete(d)


# ── Enrollments ─────────────────────────────────────────────────────────────────

@router.get("/enrollments", response_model=list[EnrollmentResponse], dependencies=[_read])
async def list_enrollments(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(BiometricEnrollment).where(BiometricEnrollment.org_id == current_user.org_id))).scalars().all()
    return [EnrollmentResponse(id=e.id, biometric_user_id=e.biometric_user_id, student_id=e.student_id,
                               student_name=await _student_name(db, current_user.org_id, e.student_id), label=e.label,
                               created_at=e.created_at, org_id=e.org_id) for e in rows]


@router.post("/enrollments", response_model=EnrollmentResponse, status_code=201, dependencies=[_write])
async def create_enrollment(payload: EnrollmentCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = (await db.execute(select(Student).where(Student.id == payload.student_id, Student.org_id == current_user.org_id, Student.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not s:
        raise HTTPException(status_code=404, detail="student not found in your organisation.")
    e = BiometricEnrollment(biometric_user_id=payload.biometric_user_id, student_id=s.id, label=payload.label, org_id=current_user.org_id)
    db.add(e)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="That biometric id is already mapped.")
    return EnrollmentResponse(id=e.id, biometric_user_id=e.biometric_user_id, student_id=e.student_id,
                              student_name=f"{s.first_name} {s.last_name}".strip(), label=e.label, created_at=e.created_at, org_id=e.org_id)


@router.delete("/enrollments/{enrollment_id}", status_code=204, dependencies=[_write])
async def delete_enrollment(enrollment_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    e = (await db.execute(select(BiometricEnrollment).where(BiometricEnrollment.id == enrollment_id, BiometricEnrollment.org_id == current_user.org_id))).scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="Enrollment not found.")
    await db.delete(e)


# ── Ingest ──────────────────────────────────────────────────────────────────────

async def _quarantine(db, org_id, p: PunchIn, direction, event_time, reason, external_ref):
    db.add(UnmappedPunch(device_id=p.device_id, biometric_user_id=p.biometric_user_id, event_time=event_time,
                         direction=direction, external_ref=external_ref, raw_payload=p.raw, reason=reason,
                         status="pending", org_id=org_id))


@router.post("/ingest", response_model=IngestSummary, dependencies=[_write])
async def ingest_punches(payload: IngestPunchesRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    org = await _org(db, current_user.org_id)
    now = datetime.now(timezone.utc)
    devices = {d.device_id: d for d in (await db.execute(select(BiometricDevice).where(BiometricDevice.org_id == org.id))).scalars().all()}
    enrollments = {e.biometric_user_id: e for e in (await db.execute(select(BiometricEnrollment).where(BiometricEnrollment.org_id == org.id))).scalars().all()}

    mapped: list[AttendanceEventIn] = []
    quarantined = 0
    for p in payload.punches:
        direction = _direction(p.direction)
        event_time = p.event_time or now
        external_ref = _external_ref(p, direction, event_time)
        device = devices.get(p.device_id)
        if not device or not device.is_active:
            await _quarantine(db, org.id, p, direction, event_time, "unknown_device", external_ref)
            quarantined += 1
            continue
        # Surface clock skew (device vs server receipt) — never adjust the punch.
        device.last_seen_at = now
        if p.event_time:
            device.clock_skew_seconds = int((now - p.event_time).total_seconds())
        enr = enrollments.get(p.biometric_user_id)
        if not enr:
            await _quarantine(db, org.id, p, direction, event_time, "unknown_biometric_id", external_ref)
            quarantined += 1
            continue
        mapped.append(AttendanceEventIn(student_id=enr.student_id, event_type=direction, event_time=event_time,
                                        source="zkteco", external_ref=external_ref, device_id=p.device_id, raw_payload=p.raw))

    result = await attendance_service.ingest(db, org, mapped, recorded_by=None, notify_parents=True) if mapped else None
    await db.flush()
    return IngestSummary(ingested=result.created if result else 0,
                         duplicates=result.duplicates if result else 0,
                         quarantined=quarantined)


# ── Quarantine review ────────────────────────────────────────────────────────────

@router.get("/quarantine", response_model=list[UnmappedPunchResponse], dependencies=[_read])
async def list_quarantine(status: str = Query(default="pending"), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    base = select(UnmappedPunch).where(UnmappedPunch.org_id == current_user.org_id)
    if status:
        base = base.where(UnmappedPunch.status == status)
    rows = (await db.execute(base.order_by(UnmappedPunch.created_at.desc()))).scalars().all()
    return [UnmappedPunchResponse(id=u.id, device_id=u.device_id, biometric_user_id=u.biometric_user_id,
                                  event_time=u.event_time, direction=u.direction, reason=u.reason, status=u.status,
                                  created_at=u.created_at, org_id=u.org_id) for u in rows]


@router.post("/quarantine/{punch_id}/resolve", response_model=IngestSummary, dependencies=[_write])
async def resolve_punch(punch_id: str, payload: ResolvePunchRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    u = (await db.execute(select(UnmappedPunch).where(UnmappedPunch.id == punch_id, UnmappedPunch.org_id == current_user.org_id, UnmappedPunch.status == "pending"))).scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="Pending quarantined punch not found.")
    s = (await db.execute(select(Student).where(Student.id == payload.student_id, Student.org_id == current_user.org_id, Student.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not s:
        raise HTTPException(status_code=404, detail="student not found in your organisation.")
    org = await _org(db, current_user.org_id)
    # Optionally enroll the biometric id so future punches map automatically.
    if payload.enroll and u.biometric_user_id:
        exists = (await db.execute(select(BiometricEnrollment.id).where(BiometricEnrollment.org_id == org.id, BiometricEnrollment.biometric_user_id == u.biometric_user_id))).scalar_one_or_none()
        if not exists:
            db.add(BiometricEnrollment(biometric_user_id=u.biometric_user_id, student_id=s.id, org_id=org.id))
    # Replay the quarantined punch into a real attendance event (deduped).
    ev = AttendanceEventIn(student_id=s.id, event_type=_direction(u.direction), event_time=u.event_time or datetime.now(timezone.utc),
                           source="zkteco", external_ref=u.external_ref, device_id=u.device_id, raw_payload=u.raw_payload)
    result = await attendance_service.ingest(db, org, [ev], recorded_by=current_user.id, notify_parents=False)
    # Link the resulting event for the audit trail.
    row = (await db.execute(select(AttendanceEvent.id).where(AttendanceEvent.org_id == org.id, AttendanceEvent.source == "zkteco", AttendanceEvent.external_ref == u.external_ref))).scalar_one_or_none()
    u.status = "resolved"
    u.resolved_event_id = row
    u.resolved_by = current_user.id
    u.resolved_at = datetime.now(timezone.utc)
    await db.flush()
    return IngestSummary(ingested=result.created, duplicates=result.duplicates, quarantined=0)


@router.post("/quarantine/{punch_id}/discard", status_code=204, dependencies=[_write])
async def discard_punch(punch_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    u = (await db.execute(select(UnmappedPunch).where(UnmappedPunch.id == punch_id, UnmappedPunch.org_id == current_user.org_id, UnmappedPunch.status == "pending"))).scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="Pending quarantined punch not found.")
    u.status = "discarded"
    u.resolved_by = current_user.id
    u.resolved_at = datetime.now(timezone.utc)
    await db.flush()
