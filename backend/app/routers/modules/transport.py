"""
Transport Router (Phase 6.7)
============================

Operational, not just CRUD. Three layers:

  1. Fleet     — vehicles + drivers (CRUD)
  2. Routes    — routes, their stops, and student assignments
  3. Trips     — daily runs of a route. Lifecycle: planned → in_progress →
                 completed, with per-student boarding events that drive the
                 dashboard's "students on board now" + "delays/issues".

The dashboard endpoint pulls the operational summary in one call so the
admin lands on a live overview without 5 separate fetches.
"""

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.modules.school import Student
from app.models.modules.transport import (
    TransportVehicle, TransportDriver, TransportRoute, TransportStop,
    StudentRouteAssignment, TransportTrip, TripBoarding,
    VehicleStatus, TripDirection, TripStatus, BoardingStatus,
)
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker
from app.services.sms import normalise_phone_e164


router = APIRouter(
    prefix="/transport",
    tags=["Transport"],
    dependencies=[Depends(require_role_module("school"))],
)

_can_read = Depends(PermissionChecker("school:read"))
_can_write = Depends(PermissionChecker("school:write"))


# Transport is an operational/admin function: dispatching vehicles, assigning
# students to routes, marking boardings. Teachers technically have school:write
# (for grading/attendance) but should NOT touch transport — same shape as SMS.
ADMIN_SLUGS = {"org_admin", "manager", "super_admin"}


async def require_transport_admin(
    current_user: User = Depends(get_current_active_user),
):
    """Dependency: gate every write endpoint to admins/managers only.
    Teachers see read-only views via separate dashboard widgets if needed,
    but cannot edit fleet, routes, trips or boardings."""
    if current_user.is_superadmin:
        return
    if any(r.slug in ADMIN_SLUGS for r in current_user.roles):
        return
    raise HTTPException(403, detail="Only administrators can manage transport")


# ── Serialisation helpers ────────────────────────────────────────────────────


def _vehicle_dict(v: TransportVehicle) -> dict[str, Any]:
    return {
        "id": v.id,
        "registration_number": v.registration_number,
        "make": v.make,
        "model": v.model,
        "color": v.color,
        "capacity": v.capacity,
        "fuel_type": v.fuel_type,
        "status": v.status.value if hasattr(v.status, "value") else v.status,
        "last_serviced_at": v.last_serviced_at.isoformat() if v.last_serviced_at else None,
        "notes": v.notes,
    }


def _driver_dict(d: TransportDriver) -> dict[str, Any]:
    return {
        "id": d.id,
        "full_name": d.full_name,
        "phone": d.phone,
        "license_number": d.license_number,
        "license_expiry": d.license_expiry.isoformat() if d.license_expiry else None,
        "is_active": d.is_active,
        "notes": d.notes,
    }


def _stop_dict(s: TransportStop) -> dict[str, Any]:
    return {
        "id": s.id,
        "route_id": s.route_id,
        "sequence": s.sequence,
        "name": s.name,
        "address": s.address,
        "morning_pickup_time": s.morning_pickup_time,
        "afternoon_dropoff_time": s.afternoon_dropoff_time,
    }


def _route_dict(
    r: TransportRoute,
    *,
    vehicle: TransportVehicle | None = None,
    driver: TransportDriver | None = None,
    stops: list[TransportStop] | None = None,
    student_count: int | None = None,
) -> dict[str, Any]:
    return {
        "id": r.id,
        "name": r.name,
        "code": r.code,
        "description": r.description,
        "vehicle_id": r.vehicle_id,
        "vehicle": _vehicle_dict(vehicle) if vehicle else None,
        "driver_id": r.driver_id,
        "driver": _driver_dict(driver) if driver else None,
        "morning_start_time": r.morning_start_time,
        "afternoon_start_time": r.afternoon_start_time,
        "is_active": r.is_active,
        "stops": [_stop_dict(s) for s in (stops or [])],
        "student_count": student_count,
    }


def _trip_dict(
    t: TransportTrip,
    *,
    route: TransportRoute | None = None,
    driver: TransportDriver | None = None,
    vehicle: TransportVehicle | None = None,
    counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "id": t.id,
        "route_id": t.route_id,
        "route_name": route.name if route else None,
        "route_code": route.code if route else None,
        "trip_date": t.trip_date.isoformat() if t.trip_date else None,
        "direction": t.direction.value if hasattr(t.direction, "value") else t.direction,
        "status": t.status.value if hasattr(t.status, "value") else t.status,
        "vehicle_id": t.vehicle_id,
        "vehicle_registration": vehicle.registration_number if vehicle else None,
        "driver_id": t.driver_id,
        "driver_name": driver.full_name if driver else None,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "cancelled_reason": t.cancelled_reason,
        "notes": t.notes,
        "counts": counts or {},
    }


def _boarding_dict(b: TripBoarding, student: Student | None = None, stop: TransportStop | None = None) -> dict[str, Any]:
    return {
        "id": b.id,
        "trip_id": b.trip_id,
        "student_id": b.student_id,
        "student_name": f"{student.first_name} {student.last_name}" if student else None,
        "student_code": student.student_id if student else None,
        "pickup_stop_id": b.pickup_stop_id,
        "dropoff_stop_id": b.dropoff_stop_id,
        "stop_name": stop.name if stop else None,
        "status": b.status.value if hasattr(b.status, "value") else b.status,
        "event_at": b.event_at.isoformat() if b.event_at else None,
        "notes": b.notes,
    }


# ── Vehicles ────────────────────────────────────────────────────────────────


@router.get("/vehicles", dependencies=[_can_read])
async def list_vehicles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows = (await db.execute(
        select(TransportVehicle).where(
            TransportVehicle.org_id == current_user.org_id,
            TransportVehicle.is_deleted == False,
        ).order_by(TransportVehicle.registration_number.asc())
    )).scalars().all()
    return {"items": [_vehicle_dict(v) for v in rows]}


@router.post("/vehicles", status_code=201, dependencies=[_can_write, Depends(require_transport_admin)])
async def create_vehicle(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not (payload.get("registration_number") or "").strip():
        raise HTTPException(422, detail="registration_number is required")
    capacity = int(payload.get("capacity") or 20)
    if capacity < 1:
        raise HTTPException(422, detail="capacity must be at least 1")
    v = TransportVehicle(
        registration_number=str(payload["registration_number"]).strip().upper(),
        make=(payload.get("make") or None),
        model=(payload.get("model") or None),
        color=(payload.get("color") or None),
        capacity=capacity,
        fuel_type=(payload.get("fuel_type") or None),
        status=VehicleStatus(payload.get("status") or "active"),
        notes=(payload.get("notes") or None),
        org_id=current_user.org_id,
    )
    db.add(v)
    await db.flush()
    return _vehicle_dict(v)


@router.patch("/vehicles/{vehicle_id}", dependencies=[_can_write, Depends(require_transport_admin)])
async def update_vehicle(
    vehicle_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    v = (await db.execute(
        select(TransportVehicle).where(
            TransportVehicle.id == vehicle_id,
            TransportVehicle.org_id == current_user.org_id,
            TransportVehicle.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not v:
        raise HTTPException(404, detail="Vehicle not found")
    for key in ("registration_number", "make", "model", "color", "fuel_type", "notes"):
        if key in payload:
            setattr(v, key, payload[key] or None)
    if "capacity" in payload:
        v.capacity = int(payload["capacity"])
    if "status" in payload:
        v.status = VehicleStatus(payload["status"])
    await db.flush()
    return _vehicle_dict(v)


@router.delete("/vehicles/{vehicle_id}", status_code=204, dependencies=[_can_write, Depends(require_transport_admin)])
async def delete_vehicle(
    vehicle_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    v = (await db.execute(
        select(TransportVehicle).where(
            TransportVehicle.id == vehicle_id,
            TransportVehicle.org_id == current_user.org_id,
            TransportVehicle.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not v:
        raise HTTPException(404, detail="Vehicle not found")
    # Don't break running trips. Block delete if vehicle is on an active route.
    in_use = (await db.execute(
        select(func.count(TransportRoute.id)).where(
            TransportRoute.vehicle_id == v.id,
            TransportRoute.is_active == True,
        )
    )).scalar_one()
    if in_use:
        raise HTTPException(409, detail=f"Cannot remove: {in_use} active route(s) use this vehicle")
    v.is_deleted = True
    v.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Drivers ──────────────────────────────────────────────────────────────────


@router.get("/drivers", dependencies=[_can_read])
async def list_drivers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows = (await db.execute(
        select(TransportDriver).where(
            TransportDriver.org_id == current_user.org_id,
            TransportDriver.is_deleted == False,
        ).order_by(TransportDriver.full_name.asc())
    )).scalars().all()
    return {"items": [_driver_dict(d) for d in rows]}


@router.post("/drivers", status_code=201, dependencies=[_can_write, Depends(require_transport_admin)])
async def create_driver(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    name = str(payload.get("full_name") or "").strip()
    phone_raw = str(payload.get("phone") or "").strip()
    if not name or not phone_raw:
        raise HTTPException(422, detail="full_name and phone are required")
    phone = normalise_phone_e164(phone_raw)
    if not phone:
        raise HTTPException(422, detail="Invalid phone number")
    expiry = None
    if payload.get("license_expiry"):
        try:
            expiry = date.fromisoformat(str(payload["license_expiry"]))
        except (TypeError, ValueError):
            raise HTTPException(422, detail="license_expiry must be YYYY-MM-DD")
    d = TransportDriver(
        full_name=name,
        phone=phone,
        license_number=(payload.get("license_number") or None),
        license_expiry=expiry,
        is_active=bool(payload.get("is_active", True)),
        notes=(payload.get("notes") or None),
        org_id=current_user.org_id,
    )
    db.add(d)
    await db.flush()
    return _driver_dict(d)


@router.patch("/drivers/{driver_id}", dependencies=[_can_write, Depends(require_transport_admin)])
async def update_driver(
    driver_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    d = (await db.execute(
        select(TransportDriver).where(
            TransportDriver.id == driver_id,
            TransportDriver.org_id == current_user.org_id,
            TransportDriver.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not d:
        raise HTTPException(404, detail="Driver not found")
    if "full_name" in payload:
        d.full_name = str(payload["full_name"]).strip()
    if "phone" in payload:
        normalised = normalise_phone_e164(payload["phone"])
        if not normalised:
            raise HTTPException(422, detail="Invalid phone number")
        d.phone = normalised
    for key in ("license_number", "notes"):
        if key in payload:
            setattr(d, key, payload[key] or None)
    if "license_expiry" in payload:
        d.license_expiry = date.fromisoformat(payload["license_expiry"]) if payload["license_expiry"] else None
    if "is_active" in payload:
        d.is_active = bool(payload["is_active"])
    await db.flush()
    return _driver_dict(d)


@router.delete("/drivers/{driver_id}", status_code=204, dependencies=[_can_write, Depends(require_transport_admin)])
async def delete_driver(
    driver_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    d = (await db.execute(
        select(TransportDriver).where(
            TransportDriver.id == driver_id,
            TransportDriver.org_id == current_user.org_id,
            TransportDriver.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not d:
        raise HTTPException(404, detail="Driver not found")
    in_use = (await db.execute(
        select(func.count(TransportRoute.id)).where(
            TransportRoute.driver_id == d.id,
            TransportRoute.is_active == True,
        )
    )).scalar_one()
    if in_use:
        raise HTTPException(409, detail=f"Cannot remove: {in_use} active route(s) use this driver")
    d.is_deleted = True
    d.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Routes ───────────────────────────────────────────────────────────────────


async def _student_count_per_route(db: AsyncSession, org_id: str) -> dict[str, int]:
    rows = (await db.execute(
        select(StudentRouteAssignment.route_id, func.count(StudentRouteAssignment.id))
        .where(
            StudentRouteAssignment.org_id == org_id,
            StudentRouteAssignment.is_active == True,
        )
        .group_by(StudentRouteAssignment.route_id)
    )).all()
    return {rid: int(n) for (rid, n) in rows}


@router.get("/routes", dependencies=[_can_read])
async def list_routes(
    include_stops: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    routes = (await db.execute(
        select(TransportRoute).where(
            TransportRoute.org_id == current_user.org_id,
            TransportRoute.is_deleted == False,
        ).order_by(TransportRoute.code.asc(), TransportRoute.name.asc())
    )).scalars().all()

    vehicle_ids = {r.vehicle_id for r in routes if r.vehicle_id}
    driver_ids = {r.driver_id for r in routes if r.driver_id}

    vehicles_by_id: dict[str, TransportVehicle] = {}
    drivers_by_id: dict[str, TransportDriver] = {}
    if vehicle_ids:
        for v in (await db.execute(
            select(TransportVehicle).where(TransportVehicle.id.in_(vehicle_ids))
        )).scalars().all():
            vehicles_by_id[v.id] = v
    if driver_ids:
        for d in (await db.execute(
            select(TransportDriver).where(TransportDriver.id.in_(driver_ids))
        )).scalars().all():
            drivers_by_id[d.id] = d

    counts = await _student_count_per_route(db, current_user.org_id)

    stops_by_route: dict[str, list[TransportStop]] = {}
    if include_stops and routes:
        rows = (await db.execute(
            select(TransportStop).where(
                TransportStop.route_id.in_([r.id for r in routes]),
            ).order_by(TransportStop.route_id, TransportStop.sequence)
        )).scalars().all()
        for s in rows:
            stops_by_route.setdefault(s.route_id, []).append(s)

    return {
        "items": [
            _route_dict(
                r,
                vehicle=vehicles_by_id.get(r.vehicle_id) if r.vehicle_id else None,
                driver=drivers_by_id.get(r.driver_id) if r.driver_id else None,
                stops=stops_by_route.get(r.id, []) if include_stops else [],
                student_count=counts.get(r.id, 0),
            )
            for r in routes
        ],
    }


@router.get("/routes/{route_id}", dependencies=[_can_read])
async def get_route(
    route_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    r = (await db.execute(
        select(TransportRoute).where(
            TransportRoute.id == route_id,
            TransportRoute.org_id == current_user.org_id,
            TransportRoute.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(404, detail="Route not found")
    stops = (await db.execute(
        select(TransportStop).where(TransportStop.route_id == r.id).order_by(TransportStop.sequence)
    )).scalars().all()
    vehicle = None
    driver = None
    if r.vehicle_id:
        vehicle = (await db.execute(select(TransportVehicle).where(TransportVehicle.id == r.vehicle_id))).scalar_one_or_none()
    if r.driver_id:
        driver = (await db.execute(select(TransportDriver).where(TransportDriver.id == r.driver_id))).scalar_one_or_none()
    counts = await _student_count_per_route(db, current_user.org_id)

    # Roster
    roster_rows = (await db.execute(
        select(StudentRouteAssignment, Student)
        .join(Student, Student.id == StudentRouteAssignment.student_id)
        .where(
            StudentRouteAssignment.route_id == r.id,
            StudentRouteAssignment.org_id == current_user.org_id,
            StudentRouteAssignment.is_active == True,
        )
        .order_by(Student.first_name)
    )).all()
    roster = [
        {
            "assignment_id": a.id,
            "student_id": s.id,
            "student_code": s.student_id,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "pickup_stop_id": a.pickup_stop_id,
            "dropoff_stop_id": a.dropoff_stop_id,
        }
        for (a, s) in roster_rows
    ]

    return {
        "route": _route_dict(r, vehicle=vehicle, driver=driver, stops=stops, student_count=counts.get(r.id, 0)),
        "roster": roster,
    }


@router.post("/routes", status_code=201, dependencies=[_can_write, Depends(require_transport_admin)])
async def create_route(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(422, detail="name is required")
    r = TransportRoute(
        name=name,
        code=(payload.get("code") or None),
        description=(payload.get("description") or None),
        vehicle_id=(payload.get("vehicle_id") or None),
        driver_id=(payload.get("driver_id") or None),
        morning_start_time=(payload.get("morning_start_time") or None),
        afternoon_start_time=(payload.get("afternoon_start_time") or None),
        is_active=bool(payload.get("is_active", True)),
        org_id=current_user.org_id,
    )
    db.add(r)
    await db.flush()
    return _route_dict(r)


@router.patch("/routes/{route_id}", dependencies=[_can_write, Depends(require_transport_admin)])
async def update_route(
    route_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    r = (await db.execute(
        select(TransportRoute).where(
            TransportRoute.id == route_id,
            TransportRoute.org_id == current_user.org_id,
            TransportRoute.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(404, detail="Route not found")
    for key in ("name", "code", "description", "morning_start_time",
                "afternoon_start_time", "vehicle_id", "driver_id"):
        if key in payload:
            setattr(r, key, payload[key] or None)
    if "is_active" in payload:
        r.is_active = bool(payload["is_active"])
    await db.flush()
    return _route_dict(r)


@router.delete("/routes/{route_id}", status_code=204, dependencies=[_can_write, Depends(require_transport_admin)])
async def delete_route(
    route_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    r = (await db.execute(
        select(TransportRoute).where(
            TransportRoute.id == route_id,
            TransportRoute.org_id == current_user.org_id,
            TransportRoute.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(404, detail="Route not found")
    # Soft delete is fine — students stay assigned (grayed out), trips
    # historically intact.
    r.is_deleted = True
    r.is_active = False
    r.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Stops ────────────────────────────────────────────────────────────────────


@router.post("/routes/{route_id}/stops", status_code=201, dependencies=[_can_write, Depends(require_transport_admin)])
async def add_stop(
    route_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    r = (await db.execute(
        select(TransportRoute).where(
            TransportRoute.id == route_id,
            TransportRoute.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(404, detail="Route not found")
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(422, detail="name is required")
    # Default sequence to next available so the UI can omit it for the
    # common "add stop at end" flow.
    if "sequence" in payload and payload["sequence"]:
        seq = int(payload["sequence"])
    else:
        max_seq = (await db.execute(
            select(func.coalesce(func.max(TransportStop.sequence), 0)).where(TransportStop.route_id == r.id)
        )).scalar_one()
        seq = int(max_seq) + 1
    s = TransportStop(
        route_id=r.id,
        sequence=seq,
        name=name,
        address=(payload.get("address") or None),
        morning_pickup_time=(payload.get("morning_pickup_time") or None),
        afternoon_dropoff_time=(payload.get("afternoon_dropoff_time") or None),
        org_id=current_user.org_id,
    )
    db.add(s)
    await db.flush()
    return _stop_dict(s)


@router.patch("/stops/{stop_id}", dependencies=[_can_write, Depends(require_transport_admin)])
async def update_stop(
    stop_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    s = (await db.execute(
        select(TransportStop).where(
            TransportStop.id == stop_id,
            TransportStop.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()
    if not s:
        raise HTTPException(404, detail="Stop not found")
    for key in ("name", "address", "morning_pickup_time", "afternoon_dropoff_time"):
        if key in payload:
            setattr(s, key, payload[key] or None)
    if "sequence" in payload:
        s.sequence = int(payload["sequence"])
    await db.flush()
    return _stop_dict(s)


@router.delete("/stops/{stop_id}", status_code=204, dependencies=[_can_write, Depends(require_transport_admin)])
async def delete_stop(
    stop_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    s = (await db.execute(
        select(TransportStop).where(
            TransportStop.id == stop_id,
            TransportStop.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()
    if not s:
        raise HTTPException(404, detail="Stop not found")
    # Don't bother re-numbering the remaining stops — the UI sorts by
    # sequence, and gaps are fine. Re-numbering on every delete would
    # surprise frontend caches.
    await db.delete(s)
    await db.flush()


# ── Student assignments ──────────────────────────────────────────────────────


@router.post("/routes/{route_id}/students", status_code=201, dependencies=[_can_write, Depends(require_transport_admin)])
async def assign_student(
    route_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    student_id = str(payload.get("student_id") or "")
    if not student_id:
        raise HTTPException(422, detail="student_id is required")
    r = (await db.execute(
        select(TransportRoute).where(
            TransportRoute.id == route_id,
            TransportRoute.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(404, detail="Route not found")
    student = (await db.execute(
        select(Student).where(
            Student.id == student_id,
            Student.org_id == current_user.org_id,
            Student.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not student:
        raise HTTPException(404, detail="Student not found")

    existing = (await db.execute(
        select(StudentRouteAssignment).where(
            StudentRouteAssignment.student_id == student.id,
            StudentRouteAssignment.route_id == r.id,
        )
    )).scalar_one_or_none()
    if existing:
        # Re-assigning is a stop change, not a duplicate.
        existing.pickup_stop_id = payload.get("pickup_stop_id") or existing.pickup_stop_id
        existing.dropoff_stop_id = payload.get("dropoff_stop_id") or existing.dropoff_stop_id
        existing.is_active = True
        await db.flush()
        a = existing
    else:
        a = StudentRouteAssignment(
            student_id=student.id,
            route_id=r.id,
            pickup_stop_id=(payload.get("pickup_stop_id") or None),
            dropoff_stop_id=(payload.get("dropoff_stop_id") or None),
            is_active=True,
            org_id=current_user.org_id,
        )
        db.add(a)
        await db.flush()
    return {
        "assignment_id": a.id,
        "student_id": student.id,
        "route_id": r.id,
        "pickup_stop_id": a.pickup_stop_id,
        "dropoff_stop_id": a.dropoff_stop_id,
    }


@router.delete("/routes/{route_id}/students/{student_id}", status_code=204, dependencies=[_can_write, Depends(require_transport_admin)])
async def unassign_student(
    route_id: str,
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    a = (await db.execute(
        select(StudentRouteAssignment).where(
            StudentRouteAssignment.route_id == route_id,
            StudentRouteAssignment.student_id == student_id,
            StudentRouteAssignment.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()
    if not a:
        raise HTTPException(404, detail="Assignment not found")
    a.is_active = False
    await db.flush()


# ── Trips ────────────────────────────────────────────────────────────────────


def _direction(raw: str) -> TripDirection:
    try:
        return TripDirection(raw)
    except ValueError:
        raise HTTPException(422, detail=f"Invalid direction: {raw!r}")


@router.get("/trips", dependencies=[_can_read])
async def list_trips(
    trip_date: str | None = None,
    status: str | None = None,
    route_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(TransportTrip).where(TransportTrip.org_id == current_user.org_id)
    if trip_date:
        try:
            query = query.where(TransportTrip.trip_date == date.fromisoformat(trip_date))
        except ValueError:
            raise HTTPException(422, detail="trip_date must be YYYY-MM-DD")
    if status:
        try:
            query = query.where(TransportTrip.status == TripStatus(status))
        except ValueError:
            raise HTTPException(422, detail=f"Invalid status: {status}")
    if route_id:
        query = query.where(TransportTrip.route_id == route_id)
    query = query.order_by(TransportTrip.trip_date.desc(), TransportTrip.direction.asc())
    trips = (await db.execute(query)).scalars().all()

    # Hydrate route, driver, vehicle in batch for the list view.
    route_ids = {t.route_id for t in trips}
    routes_by_id = {
        r.id: r for r in (await db.execute(
            select(TransportRoute).where(TransportRoute.id.in_(route_ids))
        )).scalars().all()
    } if route_ids else {}
    driver_ids = {t.driver_id for t in trips if t.driver_id}
    drivers_by_id = {
        d.id: d for d in (await db.execute(
            select(TransportDriver).where(TransportDriver.id.in_(driver_ids))
        )).scalars().all()
    } if driver_ids else {}
    vehicle_ids = {t.vehicle_id for t in trips if t.vehicle_id}
    vehicles_by_id = {
        v.id: v for v in (await db.execute(
            select(TransportVehicle).where(TransportVehicle.id.in_(vehicle_ids))
        )).scalars().all()
    } if vehicle_ids else {}

    # Aggregate boarding counts per trip in one query.
    counts_rows = (await db.execute(
        select(TripBoarding.trip_id, TripBoarding.status, func.count(TripBoarding.id))
        .where(TripBoarding.trip_id.in_([t.id for t in trips]))
        .group_by(TripBoarding.trip_id, TripBoarding.status)
    )).all()
    counts_by_trip: dict[str, dict[str, int]] = {}
    for (tid, st, n) in counts_rows:
        key = st.value if hasattr(st, "value") else st
        counts_by_trip.setdefault(tid, {})[key] = int(n)

    return {
        "items": [
            _trip_dict(
                t,
                route=routes_by_id.get(t.route_id),
                driver=drivers_by_id.get(t.driver_id) if t.driver_id else None,
                vehicle=vehicles_by_id.get(t.vehicle_id) if t.vehicle_id else None,
                counts=counts_by_trip.get(t.id, {}),
            )
            for t in trips
        ],
    }


@router.post("/trips", status_code=201, dependencies=[_can_write, Depends(require_transport_admin)])
async def create_trip(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a trip (a daily run of a route in one direction). Auto-spawns
    a `TripBoarding` row for every active student assignment on that route
    so the driver lands on a pre-populated roster."""
    route_id = str(payload.get("route_id") or "")
    if not route_id:
        raise HTTPException(422, detail="route_id is required")
    direction = _direction(str(payload.get("direction") or ""))
    try:
        trip_date = date.fromisoformat(str(payload.get("trip_date") or date.today().isoformat()))
    except ValueError:
        raise HTTPException(422, detail="trip_date must be YYYY-MM-DD")

    r = (await db.execute(
        select(TransportRoute).where(
            TransportRoute.id == route_id,
            TransportRoute.org_id == current_user.org_id,
            TransportRoute.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not r:
        raise HTTPException(404, detail="Route not found")

    # UniqueConstraint enforces this at the DB level too, but a clean 409 is
    # nicer than a generic IntegrityError.
    existing = (await db.execute(
        select(TransportTrip).where(
            TransportTrip.route_id == r.id,
            TransportTrip.trip_date == trip_date,
            TransportTrip.direction == direction,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(409, detail="A trip already exists for this route, date and direction")

    trip = TransportTrip(
        route_id=r.id,
        trip_date=trip_date,
        direction=direction,
        status=TripStatus.PLANNED,
        vehicle_id=r.vehicle_id,
        driver_id=r.driver_id,
        org_id=current_user.org_id,
    )
    db.add(trip)
    await db.flush()

    # Pre-spawn boardings for every active assignment so the driver doesn't
    # have to manually pick students. Attendance app feel.
    assignments = (await db.execute(
        select(StudentRouteAssignment).where(
            StudentRouteAssignment.route_id == r.id,
            StudentRouteAssignment.is_active == True,
            StudentRouteAssignment.org_id == current_user.org_id,
        )
    )).scalars().all()
    for a in assignments:
        db.add(TripBoarding(
            trip_id=trip.id,
            student_id=a.student_id,
            pickup_stop_id=a.pickup_stop_id,
            dropoff_stop_id=a.dropoff_stop_id,
            status=BoardingStatus.EXPECTED,
            org_id=current_user.org_id,
        ))
    await db.flush()
    return _trip_dict(trip, route=r)


async def _load_trip_or_404(db: AsyncSession, trip_id: str, user: User) -> TransportTrip:
    trip = (await db.execute(
        select(TransportTrip).where(
            TransportTrip.id == trip_id,
            TransportTrip.org_id == user.org_id,
        )
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(404, detail="Trip not found")
    return trip


@router.get("/trips/{trip_id}", dependencies=[_can_read])
async def get_trip(
    trip_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    trip = await _load_trip_or_404(db, trip_id, current_user)
    route = (await db.execute(select(TransportRoute).where(TransportRoute.id == trip.route_id))).scalar_one_or_none()
    driver = (await db.execute(select(TransportDriver).where(TransportDriver.id == trip.driver_id))).scalar_one_or_none() if trip.driver_id else None
    vehicle = (await db.execute(select(TransportVehicle).where(TransportVehicle.id == trip.vehicle_id))).scalar_one_or_none() if trip.vehicle_id else None
    boardings = (await db.execute(
        select(TripBoarding).where(TripBoarding.trip_id == trip.id)
    )).scalars().all()
    student_ids = {b.student_id for b in boardings}
    students = {
        s.id: s for s in (await db.execute(
            select(Student).where(Student.id.in_(student_ids))
        )).scalars().all()
    } if student_ids else {}
    stop_ids = {b.pickup_stop_id for b in boardings if b.pickup_stop_id}
    stop_ids |= {b.dropoff_stop_id for b in boardings if b.dropoff_stop_id}
    stops_by_id = {
        s.id: s for s in (await db.execute(
            select(TransportStop).where(TransportStop.id.in_(stop_ids))
        )).scalars().all()
    } if stop_ids else {}

    counts: dict[str, int] = {}
    for b in boardings:
        key = b.status.value if hasattr(b.status, "value") else b.status
        counts[key] = counts.get(key, 0) + 1

    morning = trip.direction == TripDirection.MORNING
    items = [
        _boarding_dict(
            b,
            student=students.get(b.student_id),
            stop=stops_by_id.get(b.pickup_stop_id if morning else b.dropoff_stop_id),
        )
        for b in sorted(boardings, key=lambda x: students.get(x.student_id).first_name if students.get(x.student_id) else "")
    ]

    return {
        "trip": _trip_dict(trip, route=route, driver=driver, vehicle=vehicle, counts=counts),
        "boardings": items,
    }


@router.post("/trips/{trip_id}/start", dependencies=[_can_write, Depends(require_transport_admin)])
async def start_trip(
    trip_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    trip = await _load_trip_or_404(db, trip_id, current_user)
    if trip.status not in (TripStatus.PLANNED,):
        raise HTTPException(409, detail=f"Trip cannot be started from status '{trip.status.value}'")
    trip.status = TripStatus.IN_PROGRESS
    trip.started_at = datetime.now(timezone.utc)
    await db.flush()
    return _trip_dict(trip)


@router.post("/trips/{trip_id}/complete", dependencies=[_can_write, Depends(require_transport_admin)])
async def complete_trip(
    trip_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    trip = await _load_trip_or_404(db, trip_id, current_user)
    if trip.status != TripStatus.IN_PROGRESS:
        raise HTTPException(409, detail=f"Trip cannot be completed from status '{trip.status.value}'")
    trip.status = TripStatus.COMPLETED
    trip.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return _trip_dict(trip)


@router.post("/trips/{trip_id}/cancel", dependencies=[_can_write, Depends(require_transport_admin)])
async def cancel_trip(
    trip_id: str,
    payload: dict | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    trip = await _load_trip_or_404(db, trip_id, current_user)
    if trip.status == TripStatus.COMPLETED:
        raise HTTPException(409, detail="Cannot cancel a completed trip")
    trip.status = TripStatus.CANCELLED
    if payload:
        trip.cancelled_reason = payload.get("reason") or None
    await db.flush()
    return _trip_dict(trip)


@router.post("/trips/{trip_id}/board", dependencies=[_can_write, Depends(require_transport_admin)])
async def mark_boarding(
    trip_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Flip a single student's boarding status. The driver app will hit
    this once per student as the trip runs."""
    trip = await _load_trip_or_404(db, trip_id, current_user)
    student_id = str(payload.get("student_id") or "")
    new_status_raw = str(payload.get("status") or "")
    if not student_id or not new_status_raw:
        raise HTTPException(422, detail="student_id and status are required")
    try:
        new_status = BoardingStatus(new_status_raw)
    except ValueError:
        raise HTTPException(422, detail=f"Invalid status: {new_status_raw}")

    boarding = (await db.execute(
        select(TripBoarding).where(
            TripBoarding.trip_id == trip.id,
            TripBoarding.student_id == student_id,
        )
    )).scalar_one_or_none()
    if not boarding:
        raise HTTPException(404, detail="Boarding row not found for this student on this trip")

    boarding.status = new_status
    boarding.event_at = datetime.now(timezone.utc)
    boarding.recorded_by = current_user.id
    if "notes" in payload:
        boarding.notes = payload["notes"] or None
    await db.flush()
    return _boarding_dict(boarding)


# ── Operational dashboard ────────────────────────────────────────────────────


@router.get("/dashboard", dependencies=[_can_read])
async def dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Single-call operational summary: today's trips, on-board count,
    delays/issues. The page is admin-only — no extra gate beyond
    school:read because admins are the only role with a sidebar entry."""
    org_id = current_user.org_id
    today = date.today()

    # Active trips today
    today_trips = (await db.execute(
        select(TransportTrip).where(
            TransportTrip.org_id == org_id,
            TransportTrip.trip_date == today,
        ).order_by(TransportTrip.direction.asc())
    )).scalars().all()
    in_progress = [t for t in today_trips if t.status == TripStatus.IN_PROGRESS]
    completed = [t for t in today_trips if t.status == TripStatus.COMPLETED]
    planned = [t for t in today_trips if t.status == TripStatus.PLANNED]
    cancelled = [t for t in today_trips if t.status == TripStatus.CANCELLED]

    # Per-trip boarding counts
    if today_trips:
        rows = (await db.execute(
            select(TripBoarding.trip_id, TripBoarding.status, func.count(TripBoarding.id))
            .where(TripBoarding.trip_id.in_([t.id for t in today_trips]))
            .group_by(TripBoarding.trip_id, TripBoarding.status)
        )).all()
        per_trip: dict[str, dict[str, int]] = {}
        for (tid, st, n) in rows:
            key = st.value if hasattr(st, "value") else st
            per_trip.setdefault(tid, {})[key] = int(n)
    else:
        per_trip = {}

    # On-board now: BOARDED rows on currently-in-progress trips.
    on_board_now = sum(
        per_trip.get(t.id, {}).get(BoardingStatus.BOARDED.value, 0)
        for t in in_progress
    )

    # Issues: any trip with skipped boardings, or in_progress past 90 minutes.
    now = datetime.now(timezone.utc)
    issues: list[dict[str, Any]] = []
    for t in today_trips:
        skipped = per_trip.get(t.id, {}).get(BoardingStatus.SKIPPED.value, 0)
        if skipped:
            issues.append({"trip_id": t.id, "type": "skipped_students", "detail": f"{skipped} student(s) skipped"})
        if t.status == TripStatus.IN_PROGRESS and t.started_at:
            # SQLite stores naive datetimes — pin them to UTC before arithmetic
            # so we don't trip the offset-naive vs offset-aware error.
            started = t.started_at if t.started_at.tzinfo else t.started_at.replace(tzinfo=timezone.utc)
            elapsed_min = (now - started).total_seconds() / 60
            if elapsed_min > 90:
                issues.append({"trip_id": t.id, "type": "running_long", "detail": f"In progress {int(elapsed_min)} min"})
        if t.status == TripStatus.CANCELLED:
            issues.append({"trip_id": t.id, "type": "cancelled", "detail": t.cancelled_reason or "Cancelled"})

    # Hydrate routes for active trips so the dashboard can render route names.
    route_ids = {t.route_id for t in today_trips}
    routes_by_id = {
        r.id: r for r in (await db.execute(
            select(TransportRoute).where(TransportRoute.id.in_(route_ids))
        )).scalars().all()
    } if route_ids else {}
    driver_ids = {t.driver_id for t in today_trips if t.driver_id}
    drivers_by_id = {
        d.id: d for d in (await db.execute(
            select(TransportDriver).where(TransportDriver.id.in_(driver_ids))
        )).scalars().all()
    } if driver_ids else {}
    vehicle_ids = {t.vehicle_id for t in today_trips if t.vehicle_id}
    vehicles_by_id = {
        v.id: v for v in (await db.execute(
            select(TransportVehicle).where(TransportVehicle.id.in_(vehicle_ids))
        )).scalars().all()
    } if vehicle_ids else {}

    def _hydrate(t: TransportTrip) -> dict[str, Any]:
        return _trip_dict(
            t,
            route=routes_by_id.get(t.route_id),
            driver=drivers_by_id.get(t.driver_id) if t.driver_id else None,
            vehicle=vehicles_by_id.get(t.vehicle_id) if t.vehicle_id else None,
            counts=per_trip.get(t.id, {}),
        )

    # Roster + fleet summary
    total_routes = (await db.execute(
        select(func.count(TransportRoute.id)).where(
            TransportRoute.org_id == org_id,
            TransportRoute.is_deleted == False,
            TransportRoute.is_active == True,
        )
    )).scalar_one() or 0
    total_vehicles = (await db.execute(
        select(func.count(TransportVehicle.id)).where(
            TransportVehicle.org_id == org_id,
            TransportVehicle.is_deleted == False,
            TransportVehicle.status == VehicleStatus.ACTIVE,
        )
    )).scalar_one() or 0
    total_drivers = (await db.execute(
        select(func.count(TransportDriver.id)).where(
            TransportDriver.org_id == org_id,
            TransportDriver.is_deleted == False,
            TransportDriver.is_active == True,
        )
    )).scalar_one() or 0
    total_students = (await db.execute(
        select(func.count(StudentRouteAssignment.id)).where(
            StudentRouteAssignment.org_id == org_id,
            StudentRouteAssignment.is_active == True,
        )
    )).scalar_one() or 0

    return {
        "today": today.isoformat(),
        "summary": {
            "active_routes": int(total_routes),
            "active_vehicles": int(total_vehicles),
            "active_drivers": int(total_drivers),
            "students_on_routes": int(total_students),
            "trips_in_progress": len(in_progress),
            "trips_completed": len(completed),
            "trips_planned": len(planned),
            "trips_cancelled": len(cancelled),
            "on_board_now": on_board_now,
            "issue_count": len(issues),
        },
        "in_progress": [_hydrate(t) for t in in_progress],
        "planned": [_hydrate(t) for t in planned],
        "completed": [_hydrate(t) for t in completed],
        "cancelled": [_hydrate(t) for t in cancelled],
        "issues": issues,
    }
