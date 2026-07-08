"""Tests for CBT Phase C — reset attempt, interventions, settings."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import (
    CBTExam, CBTAttempt, CBTAnswer, CBTIntervention, CBTSettings,
    ExamStatus, AttemptStatus, InterventionStatus,
)
from app.routers.modules.cbt import (
    reset_attempt, list_interventions, create_intervention, update_intervention,
    get_cbt_settings, update_cbt_settings,
)
from app.schemas.cbt_ops import InterventionCreate, InterventionUpdate, CBTSettingsUpdate

pytestmark = pytest.mark.asyncio


async def _preset_user(db, org, slug) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


# ── Reset ──────────────────────────────────────────────────────────────────────

async def test_reset_deletes_attempt_and_answers(db, org, teacher, student):
    exam = CBTExam(id=str(uuid.uuid4()), title="Q", created_by=teacher.id, org_id=org.id,
                   status=ExamStatus.PUBLISHED, total_points=2)
    attempt = CBTAttempt(id=str(uuid.uuid4()), exam_id=exam.id, student_id=student.id,
                         max_score=2, score=2, status=AttemptStatus.GRADED, org_id=org.id)
    ans = CBTAnswer(id=str(uuid.uuid4()), attempt_id=attempt.id, question_id=str(uuid.uuid4()),
                    answer_text="a", points_awarded=2, org_id=org.id)
    db.add_all([exam, attempt, ans])
    await db.commit()

    res = await reset_attempt(attempt.id, request=None, db=db, current_user=teacher)
    assert res["reset"] is True
    assert (await db.execute(select(CBTAttempt).where(CBTAttempt.id == attempt.id))).scalar_one_or_none() is None
    assert (await db.execute(select(CBTAnswer).where(CBTAnswer.attempt_id == attempt.id))).scalar_one_or_none() is None


async def test_reset_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await reset_attempt(str(uuid.uuid4()), request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 404


# ── Interventions ──────────────────────────────────────────────────────────────

async def test_intervention_flag_list_resolve(db, org, teacher, student):
    created = await create_intervention(
        InterventionCreate(student_id=student.id, reason="Scored 30% on Quiz 1"),
        request=None, db=db, current_user=teacher,
    )
    assert created["status"] == "open" and created["student_name"] and created["resolved_at"] is None

    listed = await list_interventions(status="open", student_id=None, exam_id=None, db=db, current_user=teacher)
    assert listed["items"][0]["id"] == created["id"]

    resolved = await update_intervention(created["id"], InterventionUpdate(status="resolved", note="Extra tutoring arranged"),
                                         request=None, db=db, current_user=teacher)
    assert resolved["status"] == "resolved" and resolved["resolved_at"] is not None and resolved["note"] == "Extra tutoring arranged"

    # resolved ones drop out of the open filter
    still_open = await list_interventions(status="open", student_id=None, exam_id=None, db=db, current_user=teacher)
    assert all(i["id"] != created["id"] for i in still_open["items"])

    # re-opening clears resolved_at
    reopened = await update_intervention(created["id"], InterventionUpdate(status="open"),
                                         request=None, db=db, current_user=teacher)
    assert reopened["status"] == "open" and reopened["resolved_at"] is None


async def test_intervention_unknown_student_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_intervention(InterventionCreate(student_id=str(uuid.uuid4()), reason="x"),
                                  request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 404


# ── Settings ────────────────────────────────────────────────────────────────────

async def test_settings_get_creates_default_then_update(db, org, teacher):
    s = await get_cbt_settings(db=db, current_user=teacher)
    assert s["default_duration_minutes"] == 60 and s["default_pass_percentage"] == 50 and s["shuffle_default"] is False

    upd = await update_cbt_settings(CBTSettingsUpdate(default_duration_minutes=90, shuffle_default=True, instructions="Read carefully."),
                                    request=None, db=db, current_user=teacher)
    assert upd["default_duration_minutes"] == 90 and upd["shuffle_default"] is True and upd["instructions"] == "Read carefully."
    # persisted as a single row per org
    rows = (await db.execute(select(CBTSettings).where(CBTSettings.org_id == org.id))).scalars().all()
    assert len(rows) == 1 and rows[0].default_duration_minutes == 90


# ── RBAC ────────────────────────────────────────────────────────────────────────

async def test_phase_c_rbac_staff_only(db, org):
    for slug in ("manager", "teacher"):
        u = await _preset_user(db, org, slug)
        assert u.has_permission("school:read") and u.has_permission("school:write")
    student = await _preset_user(db, org, "student")
    assert not student.has_permission("school:read") and not student.has_permission("school:write")
