"""Tests for Manage Clubs — the settings singleton + grade / coordinator /
deadline admin lists (Educare "Manage Clubs" tabs)."""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.routers.modules.clubs import (
    create_club,
    get_club_settings, update_club_settings,
    list_club_grades, create_club_grade, update_club_grade, delete_club_grade,
    list_club_coordinators, create_club_coordinator, delete_club_coordinator,
    list_club_deadlines, create_club_deadline, delete_club_deadline,
)
from app.schemas.school_experience import (
    ClubCreate, ClubSettingsUpdate, ClubGradeCreate, ClubGradeUpdate,
    ClubCoordinatorCreate, ClubDeadlineCreate,
)


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@example.com", full_name="Admin",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def _staff(db, org, name="Coach Bright") -> User:
    u = User(id=str(uuid.uuid4()), email=f"s-{uuid.uuid4().hex[:6]}@example.com", full_name=name,
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


# ── Settings singleton ───────────────────────────────────────────────────────────

async def test_club_settings_singleton_and_update(db, org):
    admin = await _admin(db, org)
    s = await get_club_settings(db=db, current_user=admin)
    assert s["club_limit"] == 3 and s["auto_approve"] is False and s["term_based_activities"] is False
    upd = await update_club_settings(ClubSettingsUpdate(club_limit=5, auto_approve=True, term_based_activities=True), db=db, current_user=admin)
    assert upd["club_limit"] == 5 and upd["auto_approve"] is True and upd["term_based_activities"] is True
    again = await get_club_settings(db=db, current_user=admin)
    assert again["club_limit"] == 5 and again["auto_approve"] is True


# ── Grades ─────────────────────────────────────────────────────────────────────

async def test_club_grade_crud(db, org):
    admin = await _admin(db, org)
    g = await create_club_grade(ClubGradeCreate(grade_letter="A", grade_point=5.0, remarks="Excellent"), db=db, current_user=admin)
    assert g["grade_letter"] == "A" and g["grade_point"] == 5.0
    listing = await list_club_grades(db=db, current_user=admin)
    assert len(listing["items"]) == 1
    upd = await update_club_grade(g["id"], ClubGradeUpdate(remarks="Outstanding"), db=db, current_user=admin)
    assert upd["remarks"] == "Outstanding"
    await delete_club_grade(g["id"], db=db, current_user=admin)
    assert len((await list_club_grades(db=db, current_user=admin))["items"]) == 0


# ── Coordinators ────────────────────────────────────────────────────────────────

async def test_club_coordinator_crud_and_dup(db, org):
    admin = await _admin(db, org)
    coach = await _staff(db, org, "Coach Bright")
    club = await create_club(ClubCreate(name="Football", max_members=100), db=db, current_user=admin)

    c = await create_club_coordinator(ClubCoordinatorCreate(coordinator_id=coach.id, club_id=club["id"]), db=db, current_user=admin)
    assert c["coordinator_name"] == "Coach Bright" and c["club_name"] == "Football"

    listing = await list_club_coordinators(db=db, current_user=admin)
    assert len(listing["items"]) == 1 and listing["items"][0]["club_name"] == "Football"

    # Duplicate assignment is rejected.
    with pytest.raises(HTTPException) as exc:
        await create_club_coordinator(ClubCoordinatorCreate(coordinator_id=coach.id, club_id=club["id"]), db=db, current_user=admin)
    assert exc.value.status_code == 409

    await delete_club_coordinator(c["id"], db=db, current_user=admin)
    assert len((await list_club_coordinators(db=db, current_user=admin))["items"]) == 0


async def test_coordinator_unknown_staff_404(db, org):
    admin = await _admin(db, org)
    club = await create_club(ClubCreate(name="Chess", max_members=50), db=db, current_user=admin)
    with pytest.raises(HTTPException) as exc:
        await create_club_coordinator(ClubCoordinatorCreate(coordinator_id="nope", club_id=club["id"]), db=db, current_user=admin)
    assert exc.value.status_code == 404


# ── Enrollment deadlines ─────────────────────────────────────────────────────────

async def test_club_deadline_crud(db, org):
    admin = await _admin(db, org)
    d = await create_club_deadline(ClubDeadlineCreate(academic_year="2025/2026", term="SPRING", deadline=date(2026, 3, 1)), db=db, current_user=admin)
    assert d["term"] == "SPRING"
    listing = await list_club_deadlines(db=db, current_user=admin)
    assert len(listing["items"]) == 1
    await delete_club_deadline(d["id"], db=db, current_user=admin)
    assert len((await list_club_deadlines(db=db, current_user=admin))["items"]) == 0
