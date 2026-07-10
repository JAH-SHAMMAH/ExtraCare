"""HR Development router (Batch 1): Staff Assessment + Talent Pool.

Two confidential HR surfaces:

  /hr/assessments      GET/POST          — staff performance appraisals
  /hr/assessments/{id} PATCH/DELETE
  /hr/talent           GET/POST          — recruitment pipeline candidates
  /hr/talent/{id}      PATCH/DELETE

RBAC
----
Everything here is gated by ``hr:write`` (org_admin + manager). Teachers hold
only ``hr:read`` (a self-service marker for *My HRM Info / My Leave*), so they
never see appraisals or candidates — these reads deliberately require write.
Reusing ``hr:*`` keeps HR admin on one lattice (same choice the core HR router
made with ``users:*``). Every query is pinned to ``current_user.org_id``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.hrm import StaffAssessment, TalentCandidate, StaffAssessmentCriterion, StaffAssessmentScore
from app.schemas.hr_development import (
    StaffAssessmentCreate, StaffAssessmentUpdate, StaffAssessmentResponse, StaffAssessmentListResponse,
    TalentCandidateCreate, TalentCandidateUpdate, TalentCandidateResponse, TalentCandidateListResponse,
    CriterionCreate, CriterionUpdate, CriterionResponse, CriterionListResponse, ScoreResponse, ScoreInput,
    _ASSESSMENT_STATUSES, _TALENT_STAGES,
)
from app.services.audit_service import log_action
from app.models.audit import AuditAction

logger = logging.getLogger("extracare.hr_dev")
router = APIRouter(prefix="/hr", tags=["HR Development"])

# Confidential HR admin — write-tier for everything, so hr:read-only roles
# (teachers/staff) can't read appraisals or the candidate pipeline.
_can_hr = Depends(PermissionChecker("hr:write"))


# ── Assessment criteria / rubric ("Setup Staff Assessment") ──────────────────

async def _load_criterion(db: AsyncSession, cid: str, org_id: str) -> StaffAssessmentCriterion:
    c = (await db.execute(
        select(StaffAssessmentCriterion).where(
            StaffAssessmentCriterion.id == cid, StaffAssessmentCriterion.org_id == org_id)
    )).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Criterion not found.")
    return c


@router.get("/assessment-criteria", response_model=CriterionListResponse, dependencies=[_can_hr])
async def list_criteria(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(
        select(StaffAssessmentCriterion).where(StaffAssessmentCriterion.org_id == current_user.org_id)
        .order_by(StaffAssessmentCriterion.position, StaffAssessmentCriterion.name)
    )).scalars().all()
    return CriterionListResponse(items=[CriterionResponse.model_validate(r) for r in rows])


@router.post("/assessment-criteria", response_model=CriterionResponse, status_code=201, dependencies=[_can_hr])
async def create_criterion(payload: CriterionCreate, request: Request = None,
                           db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = StaffAssessmentCriterion(**payload.model_dump(), org_id=current_user.org_id)
    db.add(c)
    await db.flush()
    await log_action(db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
                     resource_type="StaffAssessmentCriterion", resource_id=c.id, resource_label=c.name, request=request)
    return CriterionResponse.model_validate(c)


@router.patch("/assessment-criteria/{criterion_id}", response_model=CriterionResponse, dependencies=[_can_hr])
async def update_criterion(criterion_id: str, payload: CriterionUpdate, request: Request = None,
                           db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = await _load_criterion(db, criterion_id, current_user.org_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(c, field, value)
    await db.flush()
    await log_action(db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
                     resource_type="StaffAssessmentCriterion", resource_id=c.id, resource_label=c.name, request=request)
    return CriterionResponse.model_validate(c)


@router.delete("/assessment-criteria/{criterion_id}", status_code=204, dependencies=[_can_hr])
async def delete_criterion(criterion_id: str, request: Request = None,
                           db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = await _load_criterion(db, criterion_id, current_user.org_id)
    used = (await db.execute(select(func.count(StaffAssessmentScore.id)).where(
        StaffAssessmentScore.criterion_id == criterion_id))).scalar()
    if used:
        raise HTTPException(status_code=409, detail="Criterion is in use by assessments. Deactivate it instead.")
    await db.delete(c)
    await log_action(db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
                     resource_type="StaffAssessmentCriterion", resource_id=criterion_id,
                     resource_label=c.name, severity="warning", request=request)


# ── Staff Assessment ─────────────────────────────────────────────────────────

def _overall_from_scores(scored: list[tuple[StaffAssessmentCriterion, int]]) -> int | None:
    """Weighted average of per-criterion scores, normalised to the 1–5 scale."""
    total_w = sum(c.weight for c, _ in scored)
    if not total_w:
        return None
    frac = sum(c.weight * (sc / c.max_score) for c, sc in scored if c.max_score) / total_w
    return max(1, min(5, round(frac * 5)))


async def _apply_scores(db: AsyncSession, assessment: StaffAssessment, score_inputs: list[ScoreInput], org_id: str) -> int | None:
    """Replace an assessment's scores; returns the derived overall rating (or None
    when no scores). Each criterion is validated to belong to the org."""
    await db.execute(delete(StaffAssessmentScore).where(StaffAssessmentScore.assessment_id == assessment.id))
    scored: list[tuple[StaffAssessmentCriterion, int]] = []
    for si in score_inputs:
        crit = await _load_criterion(db, si.criterion_id, org_id)
        db.add(StaffAssessmentScore(assessment_id=assessment.id, criterion_id=crit.id,
                                    score=si.score, comment=si.comment, org_id=org_id))
        scored.append((crit, si.score))
    await db.flush()
    return _overall_from_scores(scored) if scored else None


async def _scores_by_assessment(db: AsyncSession, assessment_ids: list[str], org_id: str) -> dict[str, list[ScoreResponse]]:
    if not assessment_ids:
        return {}
    rows = (await db.execute(
        select(StaffAssessmentScore, StaffAssessmentCriterion)
        .join(StaffAssessmentCriterion, StaffAssessmentScore.criterion_id == StaffAssessmentCriterion.id)
        .where(StaffAssessmentScore.assessment_id.in_(assessment_ids), StaffAssessmentScore.org_id == org_id)
        .order_by(StaffAssessmentCriterion.position, StaffAssessmentCriterion.name)
    )).all()
    out: dict[str, list[ScoreResponse]] = {}
    for s, c in rows:
        out.setdefault(s.assessment_id, []).append(ScoreResponse(
            criterion_id=s.criterion_id, criterion_name=c.name, category=c.category,
            score=s.score, max_score=c.max_score, weight=c.weight, comment=s.comment))
    return out


def _assessment_response(a: StaffAssessment, scores: list[ScoreResponse] | None = None) -> StaffAssessmentResponse:
    return StaffAssessmentResponse(
        id=a.id,
        staff_user_id=a.staff_user_id,
        staff_name=a.staff.full_name if a.staff else None,
        reviewer_id=a.reviewer_id,
        reviewer_name=a.reviewer.full_name if a.reviewer else None,
        period=a.period,
        review_date=a.review_date,
        overall_rating=a.overall_rating,
        strengths=a.strengths,
        improvements=a.improvements,
        goals=a.goals,
        status=a.status,
        scores=scores or [],
        created_at=a.created_at,
        updated_at=a.updated_at,
        org_id=a.org_id,
    )


async def _assessment_response_with_scores(db: AsyncSession, a: StaffAssessment, org_id: str) -> StaffAssessmentResponse:
    scores = (await _scores_by_assessment(db, [a.id], org_id)).get(a.id, [])
    return _assessment_response(a, scores)


async def _load_assessment(db: AsyncSession, aid: str, org_id: str) -> StaffAssessment:
    a = (await db.execute(
        select(StaffAssessment).where(
            StaffAssessment.id == aid,
            StaffAssessment.org_id == org_id,
            StaffAssessment.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    return a


@router.get("/assessments", response_model=StaffAssessmentListResponse, dependencies=[_can_hr])
async def list_assessments(
    staff_user_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = select(StaffAssessment).where(
        StaffAssessment.org_id == current_user.org_id,
        StaffAssessment.is_deleted == False,  # noqa: E712
    )
    if staff_user_id:
        base = base.where(StaffAssessment.staff_user_id == staff_user_id)
    if status:
        base = base.where(StaffAssessment.status == status)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(StaffAssessment.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    scores_map = await _scores_by_assessment(db, [r.id for r in rows], current_user.org_id)
    return StaffAssessmentListResponse(
        items=[_assessment_response(r, scores_map.get(r.id, [])) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/assessments", response_model=StaffAssessmentResponse, status_code=201, dependencies=[_can_hr])
async def create_assessment(
    payload: StaffAssessmentCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.status not in _ASSESSMENT_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(_ASSESSMENT_STATUSES)}")
    staff = (await db.execute(
        select(User).where(
            User.id == payload.staff_user_id,
            User.org_id == current_user.org_id,
            User.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="staff_user_id: staff member not found in your organisation.")

    a = StaffAssessment(
        staff_user_id=staff.id,
        reviewer_id=current_user.id,
        period=payload.period,
        review_date=payload.review_date,
        overall_rating=payload.overall_rating,
        strengths=payload.strengths,
        improvements=payload.improvements,
        goals=payload.goals,
        status=payload.status,
        org_id=current_user.org_id,
    )
    db.add(a)
    await db.flush()
    # Per-criterion scores (when supplied) derive the overall rating.
    if payload.scores is not None:
        derived = await _apply_scores(db, a, payload.scores, current_user.org_id)
        if derived is not None:
            a.overall_rating = derived
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="StaffAssessment", resource_id=a.id,
        resource_label=f"appraisal of {staff.full_name} ({a.period})",
        metadata={"staff_user_id": staff.id, "status": a.status}, request=request,
    )
    return await _assessment_response_with_scores(db, await _load_assessment(db, a.id, current_user.org_id), current_user.org_id)


@router.patch("/assessments/{assessment_id}", response_model=StaffAssessmentResponse, dependencies=[_can_hr])
async def update_assessment(
    assessment_id: str,
    payload: StaffAssessmentUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    a = await _load_assessment(db, assessment_id, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in _ASSESSMENT_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(_ASSESSMENT_STATUSES)}")
    scores = data.pop("scores", None)  # not a column — handled separately
    for field, value in data.items():
        setattr(a, field, value)
    if scores is not None:
        derived = await _apply_scores(db, a, payload.scores, current_user.org_id)
        if derived is not None:
            a.overall_rating = derived
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="StaffAssessment", resource_id=a.id,
        resource_label=f"appraisal {a.period}", request=request,
    )
    return await _assessment_response_with_scores(db, await _load_assessment(db, a.id, current_user.org_id), current_user.org_id)


@router.delete("/assessments/{assessment_id}", status_code=204, dependencies=[_can_hr])
async def delete_assessment(
    assessment_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    a = await _load_assessment(db, assessment_id, current_user.org_id)
    a.is_deleted = True
    a.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
        resource_type="StaffAssessment", resource_id=a.id,
        resource_label="appraisal", severity="warning", request=request,
    )


# ── Talent Pool ──────────────────────────────────────────────────────────────

def _candidate_response(c: TalentCandidate) -> TalentCandidateResponse:
    return TalentCandidateResponse.model_validate(c)


async def _load_candidate(db: AsyncSession, cid: str, org_id: str) -> TalentCandidate:
    c = (await db.execute(
        select(TalentCandidate).where(
            TalentCandidate.id == cid,
            TalentCandidate.org_id == org_id,
            TalentCandidate.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return c


@router.get("/talent", response_model=TalentCandidateListResponse, dependencies=[_can_hr])
async def list_candidates(
    stage: str | None = Query(default=None),
    search: str | None = Query(default=None, description="Filter by name, email, or role applied."),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    base = select(TalentCandidate).where(
        TalentCandidate.org_id == current_user.org_id,
        TalentCandidate.is_deleted == False,  # noqa: E712
    )
    if stage:
        base = base.where(TalentCandidate.stage == stage)
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        base = base.where(or_(
            func.lower(TalentCandidate.full_name).like(term),
            func.lower(TalentCandidate.email).like(term),
            func.lower(TalentCandidate.role_applied).like(term),
        ))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(TalentCandidate.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return TalentCandidateListResponse(
        items=[_candidate_response(r) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/talent", response_model=TalentCandidateResponse, status_code=201, dependencies=[_can_hr])
async def create_candidate(
    payload: TalentCandidateCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.stage not in _TALENT_STAGES:
        raise HTTPException(status_code=422, detail=f"stage must be one of {sorted(_TALENT_STAGES)}")
    c = TalentCandidate(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        role_applied=payload.role_applied,
        source=payload.source,
        stage=payload.stage,
        rating=payload.rating,
        notes=payload.notes,
        created_by=current_user.id,
        org_id=current_user.org_id,
    )
    db.add(c)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="TalentCandidate", resource_id=c.id,
        resource_label=f"candidate {c.full_name}",
        metadata={"stage": c.stage, "role_applied": c.role_applied}, request=request,
    )
    return _candidate_response(await _load_candidate(db, c.id, current_user.org_id))


@router.patch("/talent/{candidate_id}", response_model=TalentCandidateResponse, dependencies=[_can_hr])
async def update_candidate(
    candidate_id: str,
    payload: TalentCandidateUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    c = await _load_candidate(db, candidate_id, current_user.org_id)
    data = payload.model_dump(exclude_unset=True)
    if "stage" in data and data["stage"] not in _TALENT_STAGES:
        raise HTTPException(status_code=422, detail=f"stage must be one of {sorted(_TALENT_STAGES)}")
    for field, value in data.items():
        setattr(c, field, value)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="TalentCandidate", resource_id=c.id,
        resource_label=f"candidate {c.full_name}", request=request,
    )
    return _candidate_response(await _load_candidate(db, c.id, current_user.org_id))


@router.delete("/talent/{candidate_id}", status_code=204, dependencies=[_can_hr])
async def delete_candidate(
    candidate_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    c = await _load_candidate(db, candidate_id, current_user.org_id)
    c.is_deleted = True
    c.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
        resource_type="TalentCandidate", resource_id=c.id,
        resource_label="candidate", severity="warning", request=request,
    )
