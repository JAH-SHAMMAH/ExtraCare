"""Tests for Club Membership List + Club Enrollment: term-scoped enrolment with
capacity / club-limit guards, the auto-approve vs pending workflow, the club
account summary counts, the enriched member list, and withhold/approve."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.modules.school import Student
from app.routers.modules.clubs import (
    create_club, update_club_settings,
    enroll_students, club_membership_summary, list_members,
    update_membership_status, enrollment_candidates,
)
from app.schemas.school_experience import (
    ClubCreate, ClubSettingsUpdate, ClubEnrollRequest, ClubMembershipStatusUpdate,
)


pytestmark = pytest.mark.asyncio
YEAR, TERM = "2025/2026", "SPRING"


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@example.com", full_name="Admin",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def _student(db, org, first, class_id=None) -> Student:
    s = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:5]}", first_name=first, last_name="X",
                class_id=class_id, org_id=org.id)
    db.add(s)
    await db.commit()
    return s


async def _summary_row(db, admin, club_id):
    res = await club_membership_summary(academic_year=YEAR, term=TERM, db=db, current_user=admin)
    return next(r for r in res["items"] if r["club_id"] == club_id)


# ── Enrol + summary + member list ────────────────────────────────────────────────

async def test_enroll_summary_and_member_list(db, org, student, school_class):
    admin = await _admin(db, org)
    # Auto-approve on so members land approved.
    await update_club_settings(ClubSettingsUpdate(auto_approve=True), db=db, current_user=admin)
    club = await create_club(ClubCreate(name="Football", max_members=100), db=db, current_user=admin)

    res = await enroll_students(club["id"], ClubEnrollRequest(student_ids=[student.id], academic_year=YEAR, term=TERM), db=db, current_user=admin)
    assert res["enrolled"] == 1 and res["skipped"] == 0

    row = await _summary_row(db, admin, club["id"])
    assert row["active_members"] == 1 and row["inactive_members"] == 0 and row["pending_requests"] == 0
    assert row["club_status"] == "ACTIVE"

    members = await list_members(club["id"], academic_year=YEAR, term=TERM, db=db, current_user=admin)
    assert len(members["items"]) == 1
    m = members["items"][0]
    assert m["student_name"] == "Ada Okafor" and m["current_class"] == "Year 10A" and m["status"] == "approved"


async def test_pending_when_no_auto_approve_then_withhold(db, org, student):
    admin = await _admin(db, org)
    club = await create_club(ClubCreate(name="Chess", max_members=50), db=db, current_user=admin)
    # Default settings: auto_approve False → pending request.
    await enroll_students(club["id"], ClubEnrollRequest(student_ids=[student.id], academic_year=YEAR, term=TERM), db=db, current_user=admin)
    row = await _summary_row(db, admin, club["id"])
    assert row["pending_requests"] == 1 and row["active_members"] == 0

    members = await list_members(club["id"], academic_year=YEAR, term=TERM, db=db, current_user=admin)
    mid = members["items"][0]["id"]
    # Approve → active.
    await update_membership_status(mid, ClubMembershipStatusUpdate(status="approved"), db=db, current_user=admin)
    assert (await _summary_row(db, admin, club["id"]))["active_members"] == 1
    # Withhold → inactive.
    await update_membership_status(mid, ClubMembershipStatusUpdate(status="withheld"), db=db, current_user=admin)
    row = await _summary_row(db, admin, club["id"])
    assert row["inactive_members"] == 1 and row["active_members"] == 0


async def test_bad_status_rejected(db, org, student):
    admin = await _admin(db, org)
    club = await create_club(ClubCreate(name="Book", max_members=50), db=db, current_user=admin)
    await enroll_students(club["id"], ClubEnrollRequest(student_ids=[student.id], academic_year=YEAR, term=TERM), db=db, current_user=admin)
    members = await list_members(club["id"], academic_year=YEAR, term=TERM, db=db, current_user=admin)
    with pytest.raises(HTTPException) as exc:
        await update_membership_status(members["items"][0]["id"], ClubMembershipStatusUpdate(status="banana"), db=db, current_user=admin)
    assert exc.value.status_code == 422


# ── Capacity + club-limit guards ─────────────────────────────────────────────────

async def test_capacity_skips_extra_students(db, org):
    admin = await _admin(db, org)
    club = await create_club(ClubCreate(name="Small", max_members=1), db=db, current_user=admin)
    s1 = await _student(db, org, "Alpha")
    s2 = await _student(db, org, "Beta")
    res = await enroll_students(club["id"], ClubEnrollRequest(student_ids=[s1.id, s2.id], academic_year=YEAR, term=TERM), db=db, current_user=admin)
    assert res["enrolled"] == 1 and res["skipped"] == 1


async def test_club_limit_per_student(db, org, student):
    admin = await _admin(db, org)
    await update_club_settings(ClubSettingsUpdate(club_limit=1), db=db, current_user=admin)
    c1 = await create_club(ClubCreate(name="One", max_members=50), db=db, current_user=admin)
    c2 = await create_club(ClubCreate(name="Two", max_members=50), db=db, current_user=admin)
    r1 = await enroll_students(c1["id"], ClubEnrollRequest(student_ids=[student.id], academic_year=YEAR, term=TERM), db=db, current_user=admin)
    r2 = await enroll_students(c2["id"], ClubEnrollRequest(student_ids=[student.id], academic_year=YEAR, term=TERM), db=db, current_user=admin)
    assert r1["enrolled"] == 1 and r2["enrolled"] == 0 and r2["skipped"] == 1


async def test_duplicate_enrol_skipped(db, org, student):
    admin = await _admin(db, org)
    club = await create_club(ClubCreate(name="Dup", max_members=50), db=db, current_user=admin)
    await enroll_students(club["id"], ClubEnrollRequest(student_ids=[student.id], academic_year=YEAR, term=TERM), db=db, current_user=admin)
    again = await enroll_students(club["id"], ClubEnrollRequest(student_ids=[student.id], academic_year=YEAR, term=TERM), db=db, current_user=admin)
    assert again["enrolled"] == 0 and again["skipped"] == 1


# ── Enrollment candidates ────────────────────────────────────────────────────────

async def test_enrollment_candidates_show_state(db, org, student, school_class):
    admin = await _admin(db, org)
    await update_club_settings(ClubSettingsUpdate(auto_approve=True), db=db, current_user=admin)
    club = await create_club(ClubCreate(name="Cands", max_members=50), db=db, current_user=admin)
    other = await _student(db, org, "Zed", class_id=school_class.id)
    await enroll_students(club["id"], ClubEnrollRequest(student_ids=[student.id], academic_year=YEAR, term=TERM), db=db, current_user=admin)

    res = await enrollment_candidates(club["id"], academic_year=YEAR, term=TERM, class_id=school_class.id, db=db, current_user=admin)
    by_id = {c["student_id"]: c for c in res["items"]}
    assert by_id[student.id]["membership_id"] is not None and by_id[student.id]["status"] == "approved"
    assert by_id[other.id]["membership_id"] is None
