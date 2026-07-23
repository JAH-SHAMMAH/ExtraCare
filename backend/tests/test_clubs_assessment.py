"""Tests for Club Assessment — the grading grid (approved members + their grade
band + remarks) and the upsert-save."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.routers.modules.clubs import (
    create_club, update_club_settings, enroll_students, create_club_grade,
    list_club_assessments, save_club_assessments,
)
from app.schemas.school_experience import (
    ClubCreate, ClubSettingsUpdate, ClubEnrollRequest, ClubGradeCreate,
    ClubAssessmentSave, ClubAssessmentEntry,
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


async def _club_with_member(db, org, admin, student):
    await update_club_settings(ClubSettingsUpdate(auto_approve=True), db=db, current_user=admin)
    club = await create_club(ClubCreate(name="Football", max_members=50), db=db, current_user=admin)
    await enroll_students(club["id"], ClubEnrollRequest(student_ids=[student.id], academic_year=YEAR, term=TERM), db=db, current_user=admin)
    return club


async def test_assessment_grid_lists_members_ungraded(db, org, student):
    admin = await _admin(db, org)
    club = await _club_with_member(db, org, admin, student)
    res = await list_club_assessments(club["id"], academic_year=YEAR, term=TERM, db=db, current_user=admin)
    assert len(res["items"]) == 1
    row = res["items"][0]
    assert row["student_name"] == "Ada Okafor" and row["current_class"] == "Year 10A"
    assert row["grade_id"] is None and row["grade_letter"] is None


async def test_save_and_reload_assessment(db, org, student):
    admin = await _admin(db, org)
    club = await _club_with_member(db, org, admin, student)
    grade = await create_club_grade(ClubGradeCreate(grade_letter="A", grade_point=5.0, remarks="Excellent"), db=db, current_user=admin)

    res = await save_club_assessments(
        club["id"], ClubAssessmentSave(academic_year=YEAR, term=TERM, entries=[ClubAssessmentEntry(student_id=student.id, grade_id=grade["id"], remarks="Great season")]),
        db=db, current_user=admin,
    )
    assert res["saved"] == 1

    reloaded = await list_club_assessments(club["id"], academic_year=YEAR, term=TERM, db=db, current_user=admin)
    row = reloaded["items"][0]
    assert row["grade_id"] == grade["id"] and row["grade_letter"] == "A" and row["remarks"] == "Great season"

    # Upsert: saving again updates the same row (no duplicate).
    grade_b = await create_club_grade(ClubGradeCreate(grade_letter="B", grade_point=4.0), db=db, current_user=admin)
    await save_club_assessments(
        club["id"], ClubAssessmentSave(academic_year=YEAR, term=TERM, entries=[ClubAssessmentEntry(student_id=student.id, grade_id=grade_b["id"], remarks="Revised")]),
        db=db, current_user=admin,
    )
    again = await list_club_assessments(club["id"], academic_year=YEAR, term=TERM, db=db, current_user=admin)
    assert len(again["items"]) == 1 and again["items"][0]["grade_letter"] == "B" and again["items"][0]["remarks"] == "Revised"


async def test_save_unknown_grade_404(db, org, student):
    admin = await _admin(db, org)
    club = await _club_with_member(db, org, admin, student)
    with pytest.raises(HTTPException) as exc:
        await save_club_assessments(
            club["id"], ClubAssessmentSave(academic_year=YEAR, term=TERM, entries=[ClubAssessmentEntry(student_id=student.id, grade_id="nope")]),
            db=db, current_user=admin,
        )
    assert exc.value.status_code == 404
