"""Tests for HR Development (Batch 1): Staff Assessment + Talent Pool.

Covers CRUD, soft-delete, tenant isolation, filters, and the RBAC contract:
both surfaces require hr:write (org_admin + manager), so hr:read-only roles
(teacher/staff) and low-trust roles are excluded. Handlers are called directly
per the conftest convention.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.organization import Organization, IndustryType
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.routers.hr_development import (
    list_assessments, create_assessment, update_assessment, delete_assessment,
    list_candidates, create_candidate, update_candidate, delete_candidate,
    list_criteria, create_criterion, update_criterion, delete_criterion,
)
from app.schemas.hr_development import (
    StaffAssessmentCreate, StaffAssessmentUpdate,
    TalentCandidateCreate, TalentCandidateUpdate,
    CriterionCreate, CriterionUpdate, ScoreInput,
)


pytestmark = pytest.mark.asyncio


async def _preset_user(db, org, slug: str) -> User:
    u = User(
        id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
        full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id,
    )
    role = Role(
        id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
        permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False,
    )
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


# ── Staff Assessment ──────────────────────────────────────────────────────────

async def test_assessment_create_and_list(db, org, teacher, unlinked_user):
    a = await create_assessment(
        StaffAssessmentCreate(staff_user_id=unlinked_user.id, period="2025/2026 T1", overall_rating=4),
        request=None, db=db, current_user=teacher,
    )
    assert a.staff_user_id == unlinked_user.id
    assert a.reviewer_id == teacher.id
    assert a.staff_name == unlinked_user.full_name
    assert a.reviewer_name == teacher.full_name
    assert a.overall_rating == 4
    assert a.status == "draft"

    listing = await list_assessments(staff_user_id=None, status=None, page=1, page_size=25, db=db, current_user=teacher)
    assert listing.total == 1
    assert listing.items[0].id == a.id


async def test_assessment_rejects_staff_outside_org(db, org, teacher):
    other = Organization(id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:6]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    outsider = User(id=str(uuid.uuid4()), email="x@example.com", full_name="X",
                    status=UserStatus.ACTIVE, org_id=other.id)
    db.add(outsider)
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await create_assessment(StaffAssessmentCreate(staff_user_id=outsider.id, period="T1"),
                                request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 404


# ── Assessment criteria (Setup) + score-derived overall ───────────────────────

async def test_criterion_crud_and_delete_guard(db, org, teacher, unlinked_user):
    c = await create_criterion(CriterionCreate(name="Punctuality", category="Professionalism", weight=2, max_score=5),
                               request=None, db=db, current_user=teacher)
    assert c.name == "Punctuality" and c.weight == 2 and c.max_score == 5
    assert len((await list_criteria(db=db, current_user=teacher)).items) == 1

    upd = await update_criterion(c.id, CriterionUpdate(is_active=False), request=None, db=db, current_user=teacher)
    assert upd.is_active is False

    # a criterion referenced by an assessment's score can't be hard-deleted
    await create_assessment(
        StaffAssessmentCreate(staff_user_id=unlinked_user.id, period="2025/2026 T1",
                              scores=[ScoreInput(criterion_id=c.id, score=4)]),
        request=None, db=db, current_user=teacher)
    with pytest.raises(HTTPException) as ei:
        await delete_criterion(c.id, request=None, db=db, current_user=teacher)
    assert ei.value.status_code == 409


async def test_scores_derive_weighted_overall(db, org, teacher, unlinked_user):
    a_crit = await create_criterion(CriterionCreate(name="Teaching", weight=3, max_score=5), request=None, db=db, current_user=teacher)
    b_crit = await create_criterion(CriterionCreate(name="Admin", weight=1, max_score=5), request=None, db=db, current_user=teacher)
    # weighted: (3*(5/5) + 1*(1/5)) / 4 = 3.2/4 = 0.8 → round(0.8*5) = 4
    a = await create_assessment(
        StaffAssessmentCreate(staff_user_id=unlinked_user.id, period="T1",
                              scores=[ScoreInput(criterion_id=a_crit.id, score=5), ScoreInput(criterion_id=b_crit.id, score=1)]),
        request=None, db=db, current_user=teacher)
    assert a.overall_rating == 4
    assert {s.criterion_id for s in a.scores} == {a_crit.id, b_crit.id}
    assert len(a.scores) == 2

    # re-scoring via update replaces scores and re-derives overall (both low → 1)
    updated = await update_assessment(
        a.id, StaffAssessmentUpdate(scores=[ScoreInput(criterion_id=a_crit.id, score=1), ScoreInput(criterion_id=b_crit.id, score=1)]),
        request=None, db=db, current_user=teacher)
    assert updated.overall_rating == 1 and len(updated.scores) == 2


async def test_score_rejects_foreign_criterion(db, org, teacher, unlinked_user):
    other = Organization(id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:6]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    await db.commit()
    other_teacher = await _preset_user(db, other, "manager")
    foreign = await create_criterion(CriterionCreate(name="X"), request=None, db=db, current_user=other_teacher)
    with pytest.raises(HTTPException) as ei:
        await create_assessment(
            StaffAssessmentCreate(staff_user_id=unlinked_user.id, period="T1",
                                  scores=[ScoreInput(criterion_id=foreign.id, score=3)]),
            request=None, db=db, current_user=teacher)
    assert ei.value.status_code == 404


async def test_assessment_update_and_status_filter(db, org, teacher, unlinked_user, student_user):
    draft = await create_assessment(StaffAssessmentCreate(staff_user_id=unlinked_user.id, period="T1"),
                                    request=None, db=db, current_user=teacher)
    await create_assessment(StaffAssessmentCreate(staff_user_id=student_user.id, period="T1", status="finalized"),
                            request=None, db=db, current_user=teacher)
    updated = await update_assessment(draft.id, StaffAssessmentUpdate(status="finalized", overall_rating=5),
                                      request=None, db=db, current_user=teacher)
    assert updated.status == "finalized"
    assert updated.overall_rating == 5

    finalized = await list_assessments(staff_user_id=None, status="finalized", page=1, page_size=25,
                                       db=db, current_user=teacher)
    assert finalized.total == 2


async def test_assessment_soft_delete(db, org, teacher, unlinked_user):
    a = await create_assessment(StaffAssessmentCreate(staff_user_id=unlinked_user.id, period="T1"),
                                request=None, db=db, current_user=teacher)
    await delete_assessment(a.id, request=None, db=db, current_user=teacher)
    listing = await list_assessments(staff_user_id=None, status=None, page=1, page_size=25, db=db, current_user=teacher)
    assert listing.total == 0


async def test_assessment_tenant_scoped(db, org, teacher, unlinked_user):
    await create_assessment(StaffAssessmentCreate(staff_user_id=unlinked_user.id, period="T1"),
                            request=None, db=db, current_user=teacher)
    other = Organization(id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:6]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    teacher2 = User(id=str(uuid.uuid4()), email="t2@example.com", full_name="T2",
                    status=UserStatus.ACTIVE, org_id=other.id)
    db.add(teacher2)
    await db.commit()
    theirs = await list_assessments(staff_user_id=None, status=None, page=1, page_size=25, db=db, current_user=teacher2)
    assert theirs.total == 0


# ── Talent Pool ───────────────────────────────────────────────────────────────

async def test_candidate_create_and_list(db, org, teacher):
    c = await create_candidate(
        TalentCandidateCreate(full_name="Jane Doe", role_applied="Math Teacher", stage="applied", rating=5),
        request=None, db=db, current_user=teacher,
    )
    assert c.full_name == "Jane Doe"
    assert c.stage == "applied"
    assert c.rating == 5

    listing = await list_candidates(stage=None, search=None, page=1, page_size=25, db=db, current_user=teacher)
    assert listing.total == 1


async def test_candidate_update_stage_and_filter(db, org, teacher):
    c = await create_candidate(TalentCandidateCreate(full_name="John Roe", stage="applied"),
                               request=None, db=db, current_user=teacher)
    await update_candidate(c.id, TalentCandidateUpdate(stage="interview"),
                           request=None, db=db, current_user=teacher)
    interview = await list_candidates(stage="interview", search=None, page=1, page_size=25, db=db, current_user=teacher)
    assert interview.total == 1
    applied = await list_candidates(stage="applied", search=None, page=1, page_size=25, db=db, current_user=teacher)
    assert applied.total == 0


async def test_candidate_bad_stage_rejected(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_candidate(TalentCandidateCreate(full_name="Bad", stage="nope"),
                               request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_candidate_search(db, org, teacher):
    await create_candidate(TalentCandidateCreate(full_name="Grace Hopper", role_applied="ICT Lead"),
                           request=None, db=db, current_user=teacher)
    found = await list_candidates(stage=None, search="grace", page=1, page_size=25, db=db, current_user=teacher)
    assert found.total == 1
    by_role = await list_candidates(stage=None, search="ict", page=1, page_size=25, db=db, current_user=teacher)
    assert by_role.total == 1
    none = await list_candidates(stage=None, search="zzz", page=1, page_size=25, db=db, current_user=teacher)
    assert none.total == 0


async def test_candidate_soft_delete(db, org, teacher):
    c = await create_candidate(TalentCandidateCreate(full_name="Temp"), request=None, db=db, current_user=teacher)
    await delete_candidate(c.id, request=None, db=db, current_user=teacher)
    listing = await list_candidates(stage=None, search=None, page=1, page_size=25, db=db, current_user=teacher)
    assert listing.total == 0


async def test_candidate_tenant_scoped(db, org, teacher):
    await create_candidate(TalentCandidateCreate(full_name="Org1 Person"), request=None, db=db, current_user=teacher)
    other = Organization(id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:6]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    teacher2 = User(id=str(uuid.uuid4()), email="t2b@example.com", full_name="T2",
                    status=UserStatus.ACTIVE, org_id=other.id)
    db.add(teacher2)
    await db.commit()
    theirs = await list_candidates(stage=None, search=None, page=1, page_size=25, db=db, current_user=teacher2)
    assert theirs.total == 0


# ── RBAC contract ─────────────────────────────────────────────────────────────

async def test_rbac_hr_development_requires_hr_write(db, org):
    # Only org_admin + manager hold hr:write → can manage appraisals/candidates.
    for slug in ("org_admin", "manager"):
        u = await _preset_user(db, org, slug)
        assert u.has_permission("hr:write"), f"{slug} should hold hr:write"
    # Teachers hold hr:read (self-service) but NOT hr:write — kept out.
    teacher = await _preset_user(db, org, "teacher")
    assert teacher.has_permission("hr:read")
    assert not teacher.has_permission("hr:write")
    # Everyone else excluded entirely.
    for slug in ("staff", "student", "parent", "viewer"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("hr:write"), f"{slug} must not hold hr:write"
