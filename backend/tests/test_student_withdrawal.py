"""Tests for the Students withdrawal / inactive cluster.

Manage Withdrawal → withdraw (marks inactive + records reason/date); Withdrawal
List → status=withdrawn; Manage Inactive Students → status=inactive; reactivate
clears the record. Gated school:write.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers.modules.school import withdraw_student, reactivate_student, list_students

pytestmark = pytest.mark.asyncio


async def test_withdraw_reactivate_and_filters(db, org, teacher, student):
    w = await withdraw_student(student.id, payload={"reason": "Relocated", "effective_date": "2026-03-01"},
                               request=None, db=db, current_user=teacher)
    assert w["is_active"] is False and w["withdrawal_reason"] == "Relocated" and w["withdrawal_date"] == "2026-03-01"

    # Shows in the withdrawn + inactive rosters, not the active one.
    withdrawn = await list_students(page=1, page_size=100, status="withdrawn", db=db, current_user=teacher)
    assert student.id in [x["id"] for x in withdrawn["items"]]
    inactive = await list_students(page=1, page_size=100, status="inactive", db=db, current_user=teacher)
    assert student.id in [x["id"] for x in inactive["items"]]
    active = await list_students(page=1, page_size=100, status="active", db=db, current_user=teacher)
    assert student.id not in [x["id"] for x in active["items"]]

    # Already withdrawn → 409.
    with pytest.raises(HTTPException) as exc:
        await withdraw_student(student.id, payload={"reason": "x"}, request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 409

    # Reactivate clears the withdrawal record and returns to active.
    r = await reactivate_student(student.id, request=None, db=db, current_user=teacher)
    assert r["is_active"] is True and r["withdrawal_date"] is None and r["withdrawal_reason"] is None
    active2 = await list_students(page=1, page_size=100, status="active", db=db, current_user=teacher)
    assert student.id in [x["id"] for x in active2["items"]]


async def test_withdraw_defaults_to_today_when_no_date(db, org, teacher, student):
    from datetime import date
    w = await withdraw_student(student.id, payload={}, request=None, db=db, current_user=teacher)
    assert w["is_active"] is False and w["withdrawal_date"] == date.today().isoformat()


async def test_withdraw_unknown_and_org_isolation(db, org, teacher, student):
    with pytest.raises(HTTPException) as e1:
        await withdraw_student("nope", payload={}, request=None, db=db, current_user=teacher)
    assert e1.value.status_code == 404
    other = SimpleNamespace(org_id=str(uuid.uuid4()))
    with pytest.raises(HTTPException) as e2:
        await withdraw_student(student.id, payload={}, request=None, db=db, current_user=other)
    assert e2.value.status_code == 404


async def test_withdraw_bad_date_422(db, org, teacher, student):
    with pytest.raises(HTTPException) as exc:
        await withdraw_student(student.id, payload={"effective_date": "not-a-date"}, request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422
