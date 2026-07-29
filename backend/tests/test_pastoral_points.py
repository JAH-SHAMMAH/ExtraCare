"""Pastoral Batch C: Point/Award type config + Point Entry (writes the Recognition
conduct-point ledger) + per-student Points Analysis (term buckets, PG/PL/total)."""
from __future__ import annotations

import uuid

import pytest

from app.models.user import User, UserStatus
from app.routers.modules.pastoral import (
    create_point_type, list_point_types, update_point_type, delete_point_type,
    create_award_type, list_award_types,
    add_point_entry, list_point_entries, points_analysis, export_points_analysis,
)
from app.schemas.pastoral import (
    PointTypeCreate, PointTypeUpdate, AwardTypeCreate, PointEntryCreate,
)


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Admin",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def test_point_and_award_type_crud(db, org):
    admin = await _admin(db, org)
    pt = await create_point_type(payload=PointTypeCreate(name="Opening Point", scope="sessional", max_point=60), db=db, current_user=admin)
    assert pt.scope == "sessional" and pt.max_point == 60 and pt.is_active is True
    pt2 = await update_point_type(pt.id, PointTypeUpdate(is_active=False, max_point=50), db=db, current_user=admin)
    assert pt2.is_active is False and pt2.max_point == 50
    assert len(await list_point_types(db=db, current_user=admin)) == 1
    await delete_point_type(pt.id, db=db, current_user=admin)
    assert len(await list_point_types(db=db, current_user=admin)) == 0

    aw = await create_award_type(payload=AwardTypeCreate(name="Best in Neatness", min_point=2, max_point=10), db=db, current_user=admin)
    assert aw.min_point == 2 and aw.max_point == 10
    assert len(await list_award_types(db=db, current_user=admin)) == 1


async def test_point_entry_and_analysis(db, org, student):
    admin = await _admin(db, org)

    async def entry(points, term):
        return await add_point_entry(payload=PointEntryCreate(student_id=student.id, points=points, term=term, category="Reading"), db=db, current_user=admin)

    await entry(60, "Opening")
    await entry(10, "Autumn Term")
    await entry(-5, "Autumn Term")
    await entry(8, "Spring Term")
    await entry(3, "Summer Term")

    # Entry writes the Recognition ledger; list reflects it.
    entries = await list_point_entries(student_id=student.id, db=db, current_user=admin)
    assert len(entries) == 5 and entries[0].student_name

    rows = await points_analysis(section=None, house=None, db=db, current_user=admin)
    row = next(r for r in rows if r.student_id == student.id)
    assert row.opening_point == 60
    assert row.autumn == 5      # +10 - 5
    assert row.spring == 8 and row.summer == 3
    assert row.total_pg == 81   # 60 + 10 + 8 + 3
    assert row.total_pl == 5    # |-5|
    assert row.total == 76      # net

    resp = await export_points_analysis(section=None, house=None, db=db, current_user=admin)
    body = resp.body.decode()
    assert resp.media_type == "text/csv" and "Total PG" in body and "Total PL" in body
