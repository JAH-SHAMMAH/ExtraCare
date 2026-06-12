"""Tests for /hr/events CRUD.

Validates the dashboard's "Upcoming Events" surface:
  • create/list/update/delete on the org calendar
  • ends_at must be >= starts_at (explicit 422, not SQLAlchemy blow-up)
  • tenant isolation on every read/write
  • soft-delete hides from list but preserves the row
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.hrm import Event
from app.routers.hr import (
    list_events, create_event, update_event, delete_event,
)
from app.schemas.hrm import EventCreate, EventUpdate


pytestmark = pytest.mark.asyncio


def _future(days: int = 1, hours: int = 0) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days, hours=hours)


async def test_create_event_happy_path(db, teacher):
    data = EventCreate(
        title="Staff Meeting",
        starts_at=_future(1),
        ends_at=_future(1, 2),
        location="Conference Room",
        category="meeting",
    )
    result = await create_event(data=data, db=db, current_user=teacher)
    assert result.title == "Staff Meeting"
    assert result.created_by == teacher.id


async def test_create_event_ends_before_starts_422(db, teacher):
    data = EventCreate(
        title="Bad Event",
        starts_at=_future(2),
        ends_at=_future(1),
    )
    with pytest.raises(HTTPException) as exc:
        await create_event(data=data, db=db, current_user=teacher)
    assert exc.value.status_code == 422
    assert "ends_at" in exc.value.detail


async def test_create_event_rejects_blank_title(db):
    with pytest.raises(Exception):  # pydantic ValidationError
        EventCreate.model_validate({"title": "", "starts_at": _future(1).isoformat()})


async def test_list_events_upcoming_only_default(db, teacher):
    """Past events must not appear when upcoming_only is True."""
    past = Event(
        id=str(uuid.uuid4()), org_id=teacher.org_id,
        title="Past", starts_at=datetime.now(timezone.utc) - timedelta(days=5),
    )
    future = Event(
        id=str(uuid.uuid4()), org_id=teacher.org_id,
        title="Future", starts_at=_future(3),
    )
    db.add_all([past, future])
    await db.commit()

    result = await list_events(upcoming_only=True, limit=20, db=db, current_user=teacher)
    titles = {e.title for e in result}
    assert "Future" in titles
    assert "Past" not in titles


async def test_list_events_sorted_ascending(db, teacher):
    later = Event(
        id=str(uuid.uuid4()), org_id=teacher.org_id,
        title="Later", starts_at=_future(5),
    )
    sooner = Event(
        id=str(uuid.uuid4()), org_id=teacher.org_id,
        title="Sooner", starts_at=_future(2),
    )
    db.add_all([later, sooner])
    await db.commit()

    result = await list_events(upcoming_only=True, limit=20, db=db, current_user=teacher)
    assert [e.title for e in result[:2]] == ["Sooner", "Later"]


async def test_update_event(db, teacher):
    data = EventCreate(title="Orig", starts_at=_future(1))
    created = await create_event(data=data, db=db, current_user=teacher)

    updated = await update_event(
        event_id=created.id,
        data=EventUpdate(title="Renamed", location="Room B"),
        db=db, current_user=teacher,
    )
    assert updated.title == "Renamed"
    assert updated.location == "Room B"


async def test_update_event_validates_ends_at(db, teacher):
    created = await create_event(
        data=EventCreate(title="X", starts_at=_future(2), ends_at=_future(3)),
        db=db, current_user=teacher,
    )
    with pytest.raises(HTTPException) as exc:
        await update_event(
            event_id=created.id,
            data=EventUpdate(ends_at=_future(1)),
            db=db, current_user=teacher,
        )
    assert exc.value.status_code == 422


async def test_update_event_404_unknown(db, teacher):
    with pytest.raises(HTTPException) as exc:
        await update_event(
            event_id="nope", data=EventUpdate(title="z"),
            db=db, current_user=teacher,
        )
    assert exc.value.status_code == 404


async def test_delete_event_soft_deletes(db, teacher):
    data = EventCreate(title="ToDelete", starts_at=_future(1))
    created = await create_event(data=data, db=db, current_user=teacher)

    await delete_event(event_id=created.id, db=db, current_user=teacher)
    await db.commit()

    row = (await db.execute(
        select(Event).where(Event.id == created.id)
    )).scalar_one()
    assert row.is_deleted is True

    # List should no longer include it.
    result = await list_events(upcoming_only=True, limit=20, db=db, current_user=teacher)
    assert all(e.id != created.id for e in result)


async def test_events_tenant_isolated(db, teacher):
    """Events from another org must not leak into this org's list/update/delete."""
    from app.models.user import User, UserStatus
    from app.models.organization import Organization, IndustryType

    other_org = Organization(
        id=str(uuid.uuid4()), name="Other", slug=f"oth-{uuid.uuid4().hex[:6]}",
        industry=IndustryType.SCHOOL, modules_enabled=["school"],
    )
    db.add(other_org)
    await db.commit()
    other_user = User(
        id=str(uuid.uuid4()), email="o@example.com", full_name="Other User",
        status=UserStatus.ACTIVE, org_id=other_org.id,
    )
    db.add(other_user)
    await db.commit()

    other_event = Event(
        id=str(uuid.uuid4()), org_id=other_org.id,
        title="OtherOrgEvent", starts_at=_future(1),
    )
    db.add(other_event)
    await db.commit()

    # List must not contain the other org's event.
    result = await list_events(upcoming_only=True, limit=20, db=db, current_user=teacher)
    assert all(e.id != other_event.id for e in result)

    # Direct PATCH / DELETE by id must 404 (not silently touch another tenant's row).
    with pytest.raises(HTTPException) as exc:
        await update_event(
            event_id=other_event.id, data=EventUpdate(title="hacked"),
            db=db, current_user=teacher,
        )
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc:
        await delete_event(event_id=other_event.id, db=db, current_user=teacher)
    assert exc.value.status_code == 404
