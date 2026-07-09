"""Tests for CBT Phase C — reset attempt, interventions, settings."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.database import get_db
from app.core.security import create_access_token
from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.organization import Organization, IndustryType, SubscriptionTier
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


async def test_create_intervention_validates_links(db, org, teacher, student):
    # C1: a foreign/nonexistent exam_id or attempt_id is rejected (404), not stored.
    with pytest.raises(HTTPException) as exc_exam:
        await create_intervention(
            InterventionCreate(student_id=student.id, reason="x", exam_id=str(uuid.uuid4())),
            request=None, db=db, current_user=teacher)
    assert exc_exam.value.status_code == 404
    with pytest.raises(HTTPException) as exc_attempt:
        await create_intervention(
            InterventionCreate(student_id=student.id, reason="x", attempt_id=str(uuid.uuid4())),
            request=None, db=db, current_user=teacher)
    assert exc_attempt.value.status_code == 404


async def test_list_interventions_invalid_status_422(db, org, teacher):
    # C2: an unrecognised status filter is a 422, not a silent "return everything".
    with pytest.raises(HTTPException) as exc:
        await list_interventions(status="banana", student_id=None, exam_id=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422


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


# ── T1: RBAC enforced at the HTTP layer (not just has_permission on presets) ──────

@pytest_asyncio.fixture
async def http_app(db):
    """AsyncClient bound to the real app, sharing the test session, so the real
    auth + PermissionChecker dependency chain runs on each request."""
    async def _get_db():
        yield db
    app.dependency_overrides[get_db] = _get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


def _bearer(user) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.id})}"}


async def test_rbac_enforced_at_http_layer(db, org, teacher, student, http_app):
    # Enterprise tier clears the plan/module gate so we fail on the PERMISSION gate.
    org.subscription_tier = SubscriptionTier.ENTERPRISE
    db.add(org)
    await db.commit()
    readonly = await _preset_user(db, org, "staff")   # school:read, NOT school:write
    writer = await _preset_user(db, org, "teacher")   # school:read + school:write

    # read-only staff: every Phase C mutation is a real 403 from the endpoint gate
    ro = _bearer(readonly)
    assert (await http_app.post("/api/v1/cbt/interventions",
                                json={"student_id": student.id, "reason": "x"}, headers=ro)).status_code == 403
    assert (await http_app.post(f"/api/v1/cbt/attempts/{uuid.uuid4()}/reset", headers=ro)).status_code == 403
    assert (await http_app.put("/api/v1/cbt/settings",
                               json={"default_duration_minutes": 45}, headers=ro)).status_code == 403

    # writer clears the gate (create succeeds) — proves the 403s were the gate, not a fluke
    assert (await http_app.post("/api/v1/cbt/interventions",
                                json={"student_id": student.id, "reason": "x"}, headers=_bearer(writer))).status_code == 201


# ── T2: cross-org isolation (org B can't touch org A's Phase C data) ──────────────

async def test_cross_org_isolation(db, org, teacher, student):
    exam = CBTExam(id=str(uuid.uuid4()), title="A", created_by=teacher.id, org_id=org.id,
                   status=ExamStatus.PUBLISHED, total_points=1)
    attempt = CBTAttempt(id=str(uuid.uuid4()), exam_id=exam.id, student_id=student.id,
                         max_score=1, score=1, status=AttemptStatus.GRADED, org_id=org.id)
    db.add_all([exam, attempt])
    await db.commit()
    iv = await create_intervention(InterventionCreate(student_id=student.id, reason="low"),
                                   request=None, db=db, current_user=teacher)
    await get_cbt_settings(db=db, current_user=teacher)  # create org A settings

    org_b = Organization(id=str(uuid.uuid4()), name="Other School",
                         slug=f"other-{uuid.uuid4().hex[:8]}", industry=IndustryType.SCHOOL,
                         modules_enabled=["school"])
    db.add(org_b)
    await db.commit()
    user_b = await _preset_user(db, org_b, "manager")

    # org B cannot reach org A's attempt or intervention (404 via the org-scoped loaders)
    with pytest.raises(HTTPException) as e1:
        await reset_attempt(attempt.id, request=None, db=db, current_user=user_b)
    assert e1.value.status_code == 404
    with pytest.raises(HTTPException) as e2:
        await update_intervention(iv["id"], InterventionUpdate(status="resolved"),
                                  request=None, db=db, current_user=user_b)
    assert e2.value.status_code == 404
    # org B's list excludes org A's intervention
    listed = await list_interventions(status=None, student_id=None, exam_id=None, db=db, current_user=user_b)
    assert all(i["id"] != iv["id"] for i in listed["items"])
    # org A's attempt survived org B's failed reset
    assert (await db.execute(select(CBTAttempt).where(CBTAttempt.id == attempt.id))).scalar_one_or_none() is not None
