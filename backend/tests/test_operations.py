"""Tests for Operations (Batch 6, non-financial): Calendar, Facility, Visitor.

Safeguarding focus on Visitor Management:
  • a child-collection REQUIRES (and captures) an authorising staff member;
  • visitor + collection mutations are written to the immutable audit log;
  • deletes are SOFT only (the record is preserved, not silently removed).
Plus calendar/facility CRUD, the facility double-booking guard, and RBAC.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.audit import AuditLog
from app.models.modules.operations import VisitorLog, StudentCollection
from app.routers.modules.operations import (
    list_events, create_event, delete_event,
    create_facility, create_booking, cancel_booking,
    sign_in_visitor, sign_out_visitor, delete_visitor, list_visitors,
    record_collection, delete_collection, list_collections,
)
from app.schemas.operations import (
    CalendarEventCreate, FacilityCreate, BookingCreate, VisitorCreate, CollectionCreate,
)


pytestmark = pytest.mark.asyncio


def _dt(h):
    return datetime(2026, 5, 1, h, 0, tzinfo=timezone.utc)


async def _preset_user(db, org, slug) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


# ── Calendar ────────────────────────────────────────────────────────────────────

async def test_calendar_crud(db, org, teacher):
    e = await create_event(CalendarEventCreate(title="Sports Day", start_at=_dt(9), category="sports"),
                           db=db, current_user=teacher)
    assert e.title == "Sports Day"
    listing = await list_events(page=1, page_size=100, db=db, current_user=teacher)
    assert listing.total == 1
    await delete_event(e.id, db=db, current_user=teacher)
    assert (await list_events(page=1, page_size=100, db=db, current_user=teacher)).total == 0


async def test_calendar_upcoming_only_filter(db, org, teacher):
    """upcoming_only powers the dashboard widget: future events, soonest first."""
    now = datetime.now(timezone.utc)
    await create_event(CalendarEventCreate(title="Past", start_at=now - timedelta(days=3)),
                       db=db, current_user=teacher)
    future = await create_event(CalendarEventCreate(title="Future", start_at=now + timedelta(days=3)),
                                db=db, current_user=teacher)
    # Default lists everything (newest-first) — unchanged behaviour.
    assert (await list_events(page=1, page_size=100, db=db, current_user=teacher)).total == 2
    # upcoming_only → only the future event.
    up = await list_events(page=1, page_size=100, upcoming_only=True, db=db, current_user=teacher)
    assert up.total == 1 and up.items[0].id == future.id


# ── Facility + double-booking guard ──────────────────────────────────────────────

async def test_facility_double_booking_blocked(db, org, teacher):
    f = await create_facility(FacilityCreate(name="Main Hall", type="hall", capacity=300), db=db, current_user=teacher)
    await create_booking(f.id, BookingCreate(title="Assembly", start_at=_dt(9), end_at=_dt(11)),
                         db=db, current_user=teacher)
    # Overlapping booking on the same facility is refused.
    with pytest.raises(HTTPException) as exc:
        await create_booking(f.id, BookingCreate(title="Rehearsal", start_at=_dt(10), end_at=_dt(12)),
                             db=db, current_user=teacher)
    assert exc.value.status_code == 409
    # A non-overlapping slot is fine.
    b = await create_booking(f.id, BookingCreate(title="Evening", start_at=_dt(13), end_at=_dt(15)),
                             db=db, current_user=teacher)
    assert b.status == "booked"
    # Cancelling frees the slot.
    await cancel_booking(b.id, db=db, current_user=teacher)
    ok = await create_booking(f.id, BookingCreate(title="Reuse", start_at=_dt(13), end_at=_dt(14)),
                              db=db, current_user=teacher)
    assert ok.status == "booked"


# ── Visitor (safeguarding) ───────────────────────────────────────────────────────

async def test_visitor_signin_signout_is_audited(db, org, teacher):
    v = await sign_in_visitor(VisitorCreate(visitor_name="Jane Auditor", host_name="Head"),
                              request=None, db=db, current_user=teacher)
    assert v.status == "signed_in" and v.sign_in_at is not None
    out = await sign_out_visitor(v.id, request=None, db=db, current_user=teacher)
    assert out.status == "signed_out" and out.sign_out_at is not None
    logs = (await db.execute(select(AuditLog).where(AuditLog.org_id == org.id, AuditLog.resource_type == "VisitorLog"))).scalars().all()
    assert any(l.resource_id == v.id for l in logs)   # the sign-in/out is on the immutable log


async def test_visitor_delete_is_soft_and_audited(db, org, teacher):
    v = await sign_in_visitor(VisitorCreate(visitor_name="Temp"), request=None, db=db, current_user=teacher)
    await delete_visitor(v.id, request=None, db=db, current_user=teacher)
    # Not silently removed — the row is preserved with is_deleted=True…
    row = (await db.execute(select(VisitorLog).where(VisitorLog.id == v.id))).scalar_one()
    assert row.is_deleted is True
    # …and a deletion is on the audit log.
    logs = (await db.execute(select(AuditLog).where(AuditLog.resource_type == "VisitorLog", AuditLog.resource_id == v.id))).scalars().all()
    assert any(l.action.value == "record.deleted" for l in logs)
    # And it drops out of the active list.
    assert (await list_visitors(status=None, page=1, page_size=25, db=db, current_user=teacher)).total == 0


# ── Student collection (the safeguarding-critical record) ─────────────────────────

async def test_collection_requires_and_captures_authoriser(db, org, teacher, student, unlinked_user):
    # authorized_by must be a real staff member; captured + name resolved.
    c = await record_collection(
        CollectionCreate(student_id=student.id, collector_name="Aunt May", relationship_to_student="aunt",
                         authorized_by=unlinked_user.id),
        request=None, db=db, current_user=teacher,
    )
    assert c.authorized_by == unlinked_user.id
    assert c.authorized_by_name == unlinked_user.full_name
    assert c.student_name == "Ada Okafor"
    # A bogus authoriser is refused.
    with pytest.raises(HTTPException) as exc:
        await record_collection(
            CollectionCreate(student_id=student.id, collector_name="Stranger", authorized_by="ghost"),
            request=None, db=db, current_user=teacher,
        )
    assert exc.value.status_code == 404


async def test_collection_is_audited_and_soft_deleted(db, org, teacher, student, unlinked_user):
    c = await record_collection(
        CollectionCreate(student_id=student.id, collector_name="Dad", authorized_by=unlinked_user.id),
        request=None, db=db, current_user=teacher,
    )
    logs = (await db.execute(select(AuditLog).where(AuditLog.resource_type == "StudentCollection", AuditLog.resource_id == c.id))).scalars().all()
    assert logs and logs[0].metadata_.get("authorized_by") == unlinked_user.id
    await delete_collection(c.id, request=None, db=db, current_user=teacher)
    row = (await db.execute(select(StudentCollection).where(StudentCollection.id == c.id))).scalar_one()
    assert row.is_deleted is True   # preserved, not silently removed
    assert (await list_collections(student_id=None, page=1, page_size=25, db=db, current_user=teacher)).total == 0


# ── RBAC ──────────────────────────────────────────────────────────────────────

async def test_operations_rbac(db, org):
    # Calendar rides school:read/write; Facility + Visitor are school_admin (admin tier).
    for slug in ("org_admin", "manager"):
        u = await _preset_user(db, org, slug)
        assert u.has_permission("school:write")
        assert u.has_permission("school_admin:write")   # facility + visitor
    teacher = await _preset_user(db, org, "teacher")
    assert teacher.has_permission("school:write")        # calendar yes
    assert not teacher.has_permission("school_admin:write")  # facility/visitor NO
    for slug in ("student", "parent"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("school:write")
        assert not u.has_permission("school_admin:read")
