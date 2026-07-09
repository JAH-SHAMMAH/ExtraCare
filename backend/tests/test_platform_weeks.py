"""Tests for Admin Management → Manage Week Entries (academic_weeks registry).

Covers the calendar rules that matter: sequential auto-generation across a term's
date range, refusal to clobber an existing term's weeks, per-slot week-number
uniqueness, and the lock that freezes a week against edits/deletes. RBAC is
settings:* (admin-only), like the rest of platform config.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.routers.modules.platform import (
    create_week, list_weeks, generate_weeks, update_week, delete_week,
)
from app.schemas.platform import WeekCreate, WeekUpdate, WeekGenerate

pytestmark = pytest.mark.asyncio

YEAR = "2025/2026"
TERM = "Term 1"


async def _user(db, org, perms: list[str]) -> User:
    u = User(id=str(uuid.uuid4()), email=f"u-{uuid.uuid4().hex[:6]}@example.com",
             full_name="U", status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="r", slug=f"r-{uuid.uuid4().hex[:6]}",
                permissions=list(perms), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _admin(db, org) -> User:
    return await _user(db, org, ["settings:read", "settings:write"])


def _mk(week_number: int, **kw) -> WeekCreate:
    base = dict(academic_year=YEAR, term=TERM, week_number=week_number,
                start_date=date(2026, 1, 5), end_date=date(2026, 1, 11))
    base.update(kw)
    return WeekCreate(**base)


# ── Create + list ────────────────────────────────────────────────────────────────

async def test_create_and_list_ordered_by_week_number(db, org):
    admin = await _admin(db, org)
    # insert out of order — list must still come back sorted
    await create_week(_mk(2, start_date=date(2026, 1, 12), end_date=date(2026, 1, 18)), db=db, current_user=admin)
    await create_week(_mk(1), db=db, current_user=admin)

    rows = await list_weeks(academic_year=YEAR, term=TERM, db=db, current_user=admin)
    assert [w.week_number for w in rows] == [1, 2]


async def test_end_before_start_rejected(db, org):
    admin = await _admin(db, org)
    with pytest.raises(HTTPException) as exc:
        await create_week(_mk(1, start_date=date(2026, 1, 11), end_date=date(2026, 1, 5)), db=db, current_user=admin)
    assert exc.value.status_code == 422


async def test_duplicate_week_number_conflicts(db, org):
    admin = await _admin(db, org)
    await create_week(_mk(1), db=db, current_user=admin)
    with pytest.raises(HTTPException) as exc:
        await create_week(_mk(1), db=db, current_user=admin)
    assert exc.value.status_code == 409


# ── Generate ─────────────────────────────────────────────────────────────────────

async def test_generate_fills_range_then_refuses_second_run(db, org):
    admin = await _admin(db, org)
    created = await generate_weeks(
        WeekGenerate(academic_year=YEAR, term=TERM, start_date=date(2026, 1, 5), end_date=date(2026, 1, 25)),
        db=db, current_user=admin,
    )
    # Jan 5–25 → three 7-day weeks; last one clamps to the term end.
    assert [w.week_number for w in created] == [1, 2, 3]
    assert created[0].start_date == date(2026, 1, 5) and created[0].end_date == date(2026, 1, 11)
    assert created[2].end_date == date(2026, 1, 25)

    # second run refuses rather than duplicating the calendar
    with pytest.raises(HTTPException) as exc:
        await generate_weeks(
            WeekGenerate(academic_year=YEAR, term=TERM, start_date=date(2026, 1, 5), end_date=date(2026, 1, 25)),
            db=db, current_user=admin,
        )
    assert exc.value.status_code == 409


# ── Lock ─────────────────────────────────────────────────────────────────────────

async def test_lock_freezes_edit_and_delete_until_unlocked(db, org):
    admin = await _admin(db, org)
    w = await create_week(_mk(1), db=db, current_user=admin)

    locked = await update_week(w.id, WeekUpdate(is_locked=True), db=db, current_user=admin)
    assert locked.is_locked is True

    # editing another field while locked is refused
    with pytest.raises(HTTPException) as exc:
        await update_week(w.id, WeekUpdate(label="Exam week"), db=db, current_user=admin)
    assert exc.value.status_code == 409
    # deleting while locked is refused
    with pytest.raises(HTTPException) as exc:
        await delete_week(w.id, db=db, current_user=admin)
    assert exc.value.status_code == 409

    # unlocking is allowed, then edits/deletes work again
    await update_week(w.id, WeekUpdate(is_locked=False), db=db, current_user=admin)
    edited = await update_week(w.id, WeekUpdate(label="Exam week"), db=db, current_user=admin)
    assert edited.label == "Exam week"
    await delete_week(w.id, db=db, current_user=admin)
    remaining = await list_weeks(academic_year=YEAR, term=TERM, db=db, current_user=admin)
    assert remaining == []


async def test_update_404(db, org):
    admin = await _admin(db, org)
    with pytest.raises(HTTPException) as exc:
        await update_week(str(uuid.uuid4()), WeekUpdate(label="x"), db=db, current_user=admin)
    assert exc.value.status_code == 404


# ── RBAC ─────────────────────────────────────────────────────────────────────────

async def test_weeks_rbac_settings_only(db, org):
    admin = await _user(db, org, SCHOOL_PERMISSION_PRESETS["org_admin"])
    assert admin.has_permission("settings:read") and admin.has_permission("settings:write")
    for slug in ("manager", "teacher", "staff", "student", "parent"):
        u = await _user(db, org, SCHOOL_PERMISSION_PRESETS[slug])
        assert not u.has_permission("settings:write"), f"{slug} must not hold settings:write"
