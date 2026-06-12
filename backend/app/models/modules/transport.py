"""
Transport Models (Phase 6.7)

Designed for operational use, not just CRUD:

  Route ── has many ──> Stop (sequence-ordered)
  Route ── assigned to ──> Vehicle + Driver (one each at a time)
  Student ── assigned to ──> Route (with chosen pickup/dropoff stops)

  Trip = a single run of a Route on a given date in a given direction
         (morning pickup or afternoon dropoff). Created per day.
  Boarding = one row per assigned student per trip; flips between
             expected → boarded → dropped_off | absent | skipped as the
             trip runs. This is the data shape that feeds the parent-app
             "where is my child right now?" lookup later — schema is ready
             for it even though the UI hook isn't built yet.
"""

import enum

from sqlalchemy import (
    Column, String, Integer, DateTime, Date, Text, Enum, ForeignKey, Boolean,
    Index, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


# ── Enums ────────────────────────────────────────────────────────────────────


class VehicleStatus(str, enum.Enum):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"


class TripDirection(str, enum.Enum):
    MORNING = "morning"   # home → school
    AFTERNOON = "afternoon"  # school → home


class TripStatus(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class BoardingStatus(str, enum.Enum):
    EXPECTED = "expected"     # default state at trip start
    BOARDED = "boarded"        # student pickup confirmed
    DROPPED_OFF = "dropped_off"  # student delivered (afternoon trip)
    ABSENT = "absent"          # student not at the stop / school informed
    SKIPPED = "skipped"        # driver bypassed (issue) — drives the "delays/issues" count


# ── Vehicle ──────────────────────────────────────────────────────────────────


class TransportVehicle(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "transport_vehicles"

    registration_number = Column(String(40), nullable=False, index=True)
    make = Column(String(60), nullable=True)
    model = Column(String(60), nullable=True)
    color = Column(String(30), nullable=True)
    capacity = Column(Integer, default=20, nullable=False)
    fuel_type = Column(String(20), nullable=True)  # diesel, petrol, electric
    status = Column(Enum(VehicleStatus), default=VehicleStatus.ACTIVE, nullable=False, index=True)
    last_serviced_at = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


# ── Driver ───────────────────────────────────────────────────────────────────


class TransportDriver(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Standalone driver record (not tied to User on purpose — a school's
    driver is rarely a system login). Phone is required so SMS dispatches
    can reach them when we wire that up."""
    __tablename__ = "transport_drivers"

    full_name = Column(String(150), nullable=False)
    phone = Column(String(30), nullable=False)
    license_number = Column(String(50), nullable=True)
    license_expiry = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


# ── Route + stops ────────────────────────────────────────────────────────────


class TransportRoute(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "transport_routes"

    name = Column(String(150), nullable=False)
    code = Column(String(20), nullable=True, index=True)  # RT-01, RT-02
    description = Column(Text, nullable=True)
    # Vehicle + driver assignments are nullable so a route can exist before
    # the school has decided who runs it.
    vehicle_id = Column(String(36), ForeignKey("transport_vehicles.id", ondelete="SET NULL"), nullable=True, index=True)
    driver_id = Column(String(36), ForeignKey("transport_drivers.id", ondelete="SET NULL"), nullable=True, index=True)
    # Schedule shorthand — actual times live on each stop, but route-level
    # times help the dashboard tell "morning trips begin at 06:30".
    morning_start_time = Column(String(5), nullable=True)   # "06:30"
    afternoon_start_time = Column(String(5), nullable=True)  # "15:15"
    is_active = Column(Boolean, default=True, nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    stops = relationship(
        "TransportStop",
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="TransportStop.sequence",
    )

    __table_args__ = (
        Index("ix_transport_routes_org_active", "org_id", "is_active"),
    )


class TransportStop(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "transport_stops"

    route_id = Column(String(36), ForeignKey("transport_routes.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)  # 1..N along the route
    name = Column(String(150), nullable=False)
    address = Column(String(255), nullable=True)
    # Per-stop times — UI populates these from a base time + offset, but we
    # store the resolved string so the parent-facing display is direct.
    morning_pickup_time = Column(String(5), nullable=True)
    afternoon_dropoff_time = Column(String(5), nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    route = relationship("TransportRoute", back_populates="stops")

    __table_args__ = (
        UniqueConstraint("route_id", "sequence", name="uq_route_stop_sequence"),
    )


# ── Student assignment ───────────────────────────────────────────────────────


class StudentRouteAssignment(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "student_route_assignments"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    route_id = Column(String(36), ForeignKey("transport_routes.id", ondelete="CASCADE"), nullable=False, index=True)
    pickup_stop_id = Column(String(36), ForeignKey("transport_stops.id", ondelete="SET NULL"), nullable=True)
    dropoff_stop_id = Column(String(36), ForeignKey("transport_stops.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        # One active assignment per student per route — re-assigning to same
        # route should update existing, not duplicate.
        UniqueConstraint("student_id", "route_id", name="uq_student_route"),
        # Roster lookup: "all students on route X".
        Index("ix_student_route_route_org", "route_id", "org_id"),
    )


# ── Trip + boarding events ───────────────────────────────────────────────────


class TransportTrip(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "transport_trips"

    route_id = Column(String(36), ForeignKey("transport_routes.id"), nullable=False, index=True)
    trip_date = Column(Date, nullable=False, index=True)
    direction = Column(Enum(TripDirection), nullable=False)
    status = Column(Enum(TripStatus), default=TripStatus.PLANNED, nullable=False, index=True)
    # Snapshots — keeping vehicle/driver here lets a trip's audit row survive
    # a route's vehicle reassignment without losing the historical record.
    vehicle_id = Column(String(36), ForeignKey("transport_vehicles.id"), nullable=True)
    driver_id = Column(String(36), ForeignKey("transport_drivers.id"), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    boardings = relationship(
        "TripBoarding",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        # Dashboard hot path: "today's trips, ordered by direction".
        Index("ix_transport_trips_org_date_status", "org_id", "trip_date", "status"),
        # One trip per route per direction per date — re-running the daily
        # spawn must not duplicate.
        UniqueConstraint("route_id", "trip_date", "direction", name="uq_trip_route_date_direction"),
    )


class TripBoarding(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "trip_boardings"

    trip_id = Column(String(36), ForeignKey("transport_trips.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("students.id"), nullable=False, index=True)
    # Snapshots of the assignment at trip-creation time so swapping
    # pickup/dropoff stops on the assignment afterwards doesn't rewrite
    # historical trips.
    pickup_stop_id = Column(String(36), ForeignKey("transport_stops.id"), nullable=True)
    dropoff_stop_id = Column(String(36), ForeignKey("transport_stops.id"), nullable=True)

    status = Column(Enum(BoardingStatus), default=BoardingStatus.EXPECTED, nullable=False, index=True)
    event_at = Column(DateTime(timezone=True), nullable=True)  # when status last changed
    recorded_by = Column(String(36), ForeignKey("users.id"), nullable=True)  # the admin/driver who flipped it
    notes = Column(Text, nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("trip_id", "student_id", name="uq_trip_student"),
        # Parent-app "my child's status now" lookup → student_id + most-recent trip.
        Index("ix_trip_boardings_student_org", "student_id", "org_id"),
    )
