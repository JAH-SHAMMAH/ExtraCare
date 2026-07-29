"""Pastoral Batch D-2: hostel life comments + Result View aggregation + hostel
reports (daily / manager)."""
from __future__ import annotations

import uuid

import pytest

from app.models.user import User, UserStatus
from app.models.modules.pastoral import Hostel
from app.routers.modules.pastoral import (
    create_hostel_life_comment, list_hostel_life_comments, delete_hostel_life_comment, hostel_results,
    create_hostel_report, list_hostel_reports, update_hostel_report, delete_hostel_report,
)
from app.schemas.pastoral import (
    HostelLifeCommentCreate, HostelReportCreate, HostelReportUpdate,
)


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Manager Musa",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def _hostel(db, org, name="Green House") -> Hostel:
    h = Hostel(id=str(uuid.uuid4()), name=name, gender="boys", org_id=org.id)
    db.add(h)
    await db.commit()
    return h


async def test_life_comments_and_result_view(db, org, student):
    admin = await _admin(db, org)
    h = await _hostel(db, org)

    c1 = await create_hostel_life_comment(
        payload=HostelLifeCommentCreate(student_id=student.id, hostel_id=h.id, term="Autumn Term",
                                        grade="Good", comment="Settling in well."),
        db=db, current_user=admin)
    assert c1.student_name and c1.hostel_name == "Green House" and c1.recorded_by_name == "Manager Musa"
    await create_hostel_life_comment(
        payload=HostelLifeCommentCreate(student_id=student.id, hostel_id=h.id, term="Autumn Term",
                                        grade="Excellent", comment="Great improvement."),
        db=db, current_user=admin)

    lst = await list_hostel_life_comments(student_id=student.id, hostel_id=None, term=None, db=db, current_user=admin)
    assert len(lst) == 2

    results = await hostel_results(hostel_id=h.id, term="Autumn Term", db=db, current_user=admin)
    row = next(r for r in results if r.student_id == student.id)
    assert row.comment_count == 2
    assert row.latest_grade == "Excellent"      # last by date wins
    assert len(row.comments) == 2

    await delete_hostel_life_comment(c1.id, db=db, current_user=admin)
    assert len(await list_hostel_life_comments(student_id=student.id, hostel_id=None, term=None, db=db, current_user=admin)) == 1


async def test_hostel_reports_crud(db, org):
    from datetime import date
    admin = await _admin(db, org)
    h = await _hostel(db, org, "Blue House")

    r = await create_hostel_report(
        payload=HostelReportCreate(report_type="daily", hostel_id=h.id, report_date=date(2026, 7, 28),
                                   title="Evening roll", body="All present."),
        db=db, current_user=admin)
    assert r.report_type == "daily" and r.hostel_name == "Blue House"
    await create_hostel_report(
        payload=HostelReportCreate(report_type="manager", hostel_id=h.id, title="Weekly summary"),
        db=db, current_user=admin)

    assert len(await list_hostel_reports(report_type=None, hostel_id=h.id, db=db, current_user=admin)) == 2
    assert len(await list_hostel_reports(report_type="daily", hostel_id=None, db=db, current_user=admin)) == 1

    r2 = await update_hostel_report(r.id, HostelReportUpdate(body="One absent (sick bay)."), db=db, current_user=admin)
    assert r2.body == "One absent (sick bay)."

    await delete_hostel_report(r.id, db=db, current_user=admin)
    assert len(await list_hostel_reports(report_type=None, hostel_id=h.id, db=db, current_user=admin)) == 1


async def test_hostel_report_type_validated(db, org):
    from fastapi import HTTPException
    admin = await _admin(db, org)
    h = await _hostel(db, org, "Red House")
    with pytest.raises(HTTPException) as ei:
        await create_hostel_report(payload=HostelReportCreate(report_type="weird", hostel_id=h.id), db=db, current_user=admin)
    assert ei.value.status_code == 422
