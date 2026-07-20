"""Discipline › My Actions — a staff member's self-service view of their OWN
disciplinary records.

Unlike the admin disciplinary endpoints (hr:write), this one is reachable by any
authenticated staff BUT is pinned to current_user.id, so it can only ever return
the caller's own cases — never a colleague's, never another org's. It also omits
`reported_by` (who reported them).
"""
from __future__ import annotations

import uuid

import pytest

from app.models.user import User, UserStatus
from app.models.hr_extended import DisciplinaryCase
from app.routers.hr_extended import list_my_cases

pytestmark = pytest.mark.asyncio


async def _staff(db, org, name) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{name}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=name, status=UserStatus.ACTIVE, org_id=org.id)
    db.add(u)
    await db.commit()
    return u


async def _case(db, org, staff, title, reporter=None) -> DisciplinaryCase:
    c = DisciplinaryCase(id=str(uuid.uuid4()), org_id=org.id, staff_user_id=staff.id,
                         title=title, severity="minor", status="open",
                         reported_by=(reporter.id if reporter else None), action_taken="Verbal warning")
    db.add(c)
    await db.commit()
    return c


async def test_my_cases_returns_only_own(db, org):
    me = await _staff(db, org, "Me Staff")
    other = await _staff(db, org, "Other Staff")
    await _case(db, org, me, "My late arrival")
    await _case(db, org, me, "My uniform breach")
    await _case(db, org, other, "Their case")

    mine = await list_my_cases(db=db, current_user=me)
    assert {r.title for r in mine} == {"My late arrival", "My uniform breach"}
    assert "Their case" not in {r.title for r in mine}


async def test_my_cases_omits_reporter(db, org):
    me = await _staff(db, org, "Subject")
    reporter = await _staff(db, org, "Reporter")
    await _case(db, org, me, "Incident", reporter=reporter)
    mine = await list_my_cases(db=db, current_user=me)
    assert len(mine) == 1
    # The self-view schema has no reported_by field at all.
    assert not hasattr(mine[0], "reported_by")
    assert mine[0].action_taken == "Verbal warning"   # but the outcome IS shown


async def test_my_cases_empty_for_clean_record(db, org):
    clean = await _staff(db, org, "Clean Record")
    assert await list_my_cases(db=db, current_user=clean) == []
