"""Pastoral Batch F-2: Roll Call + Pastoral Report Setup (remark bank) +
per-student remarks + the aggregated Pastoral Report."""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.modules.pastoral import Hostel, BoardingAllocation
from app.routers.modules.pastoral import (
    get_roll_call, mark_roll_call,
    create_remark_bank, list_remark_bank, delete_remark_bank,
    create_pastoral_remark, list_pastoral_remarks,
    add_point_entry, create_disciplinary_case, pastoral_report,
)
from app.schemas.pastoral import (
    RollCallMark, RollCallMarkItem, RemarkBankCreate,
    PastoralRemarkCreate, PointEntryCreate, DisciplinaryCaseCreate,
)


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Head Hana",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def _hostel_with_boarder(db, org, student) -> Hostel:
    h = Hostel(id=str(uuid.uuid4()), name="Green House", org_id=org.id)
    db.add(h)
    await db.flush()
    db.add(BoardingAllocation(id=str(uuid.uuid4()), student_id=student.id, hostel_id=h.id, is_active=True, room="R1", org_id=org.id))
    await db.commit()
    return h


async def test_roll_call(db, org, student):
    admin = await _admin(db, org)
    h = await _hostel_with_boarder(db, org, student)
    today = date.today()

    # Before marking, the boarder shows with status None.
    rows = await get_roll_call(hostel_id=h.id, roll_date=today, session="evening", db=db, current_user=admin)
    assert len(rows) == 1 and rows[0].status is None and rows[0].room == "R1"

    await mark_roll_call(payload=RollCallMark(hostel_id=h.id, roll_date=today, session="evening",
                                              marks=[RollCallMarkItem(student_id=student.id, status="present")]),
                         db=db, current_user=admin)
    rows = await get_roll_call(hostel_id=h.id, roll_date=today, session="evening", db=db, current_user=admin)
    assert rows[0].status == "present"

    # Re-marking the same student/date/session updates in place (no duplicate).
    await mark_roll_call(payload=RollCallMark(hostel_id=h.id, roll_date=today, session="evening",
                                              marks=[RollCallMarkItem(student_id=student.id, status="absent")]),
                         db=db, current_user=admin)
    rows = await get_roll_call(hostel_id=h.id, roll_date=today, session="evening", db=db, current_user=admin)
    assert len(rows) == 1 and rows[0].status == "absent"

    # Bad session / status rejected.
    with pytest.raises(HTTPException) as ei:
        await get_roll_call(hostel_id=h.id, roll_date=today, session="lunchtime", db=db, current_user=admin)
    assert ei.value.status_code == 422
    with pytest.raises(HTTPException) as ei:
        await mark_roll_call(payload=RollCallMark(hostel_id=h.id, roll_date=today, session="night",
                                                  marks=[RollCallMarkItem(student_id=student.id, status="teleported")]),
                             db=db, current_user=admin)
    assert ei.value.status_code == 422


async def test_remark_bank_and_remarks(db, org, student):
    admin = await _admin(db, org)
    rb = await create_remark_bank(payload=RemarkBankCreate(text="A dependable boarder.", category="General"), db=db, current_user=admin)
    assert len(await list_remark_bank(db=db, current_user=admin)) == 1
    await delete_remark_bank(rb.id, db=db, current_user=admin)
    assert len(await list_remark_bank(db=db, current_user=admin)) == 0

    r = await create_pastoral_remark(payload=PastoralRemarkCreate(student_id=student.id, term="Autumn Term", remark="Settled well."), db=db, current_user=admin)
    assert r.student_name and r.recorded_by_name == "Head Hana"
    assert len(await list_pastoral_remarks(student_id=student.id, term="Autumn Term", db=db, current_user=admin)) == 1
    assert len(await list_pastoral_remarks(student_id=student.id, term="Spring Term", db=db, current_user=admin)) == 0


async def test_pastoral_report_aggregation(db, org, student):
    admin = await _admin(db, org)
    await _hostel_with_boarder(db, org, student)
    await add_point_entry(payload=PointEntryCreate(student_id=student.id, points=10, term="Autumn Term"), db=db, current_user=admin)
    await add_point_entry(payload=PointEntryCreate(student_id=student.id, points=-4, term="Autumn Term"), db=db, current_user=admin)
    await create_disciplinary_case(payload=DisciplinaryCaseCreate(student_id=student.id, offence="x", status="pending"), db=db, current_user=admin)
    await create_pastoral_remark(payload=PastoralRemarkCreate(student_id=student.id, term="Autumn Term", remark="Good"), db=db, current_user=admin)

    rep = await pastoral_report(student_id=student.id, term="Autumn Term", db=db, current_user=admin)
    assert rep.student_name and rep.hostel_name == "Green House"
    assert rep.points_gained == 10 and rep.points_lost == 4 and rep.total_points == 6
    assert rep.open_cases == 1 and rep.total_cases == 1
    assert len(rep.remarks) == 1
