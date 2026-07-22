"""Voting System router, prefix ``/voting``.

Admin (school:write): periods, categories, sessions (+ categories/candidates),
open/conduct/publish, results tally. Voter self-service (any authenticated user
eligible by voter_role): list open sessions, cast a ballot (one per category),
read own votes. Published results are readable at school:read.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.role import Role, user_roles
from app.models.modules.platform import SchoolSection
from app.models.modules.voting import (
    VotingPeriod, VoteCategory, VoteSession, VoteSessionCategory, VoteCandidate, VoteBallot,
)
from app.schemas.voting import (
    PeriodCreate, PeriodExtend, PeriodResponse,
    CategoryCreate, CategoryUpdate, CategoryResponse,
    SessionCreate, SessionUpdate, SessionResponse,
    CandidateCreate, CandidateResponse,
    BallotCreate, CategoryResult, SessionResults,
    BallotCandidate, BallotCategory, BallotView,
)

router = APIRouter(prefix="/voting", tags=["Voting System"])

_can_admin = Depends(PermissionChecker("school:write"))
_can_read = Depends(PermissionChecker("school:read"))


async def _section_names(db: AsyncSession, org_id: str) -> dict:
    return dict((r.id, r.name) for r in (await db.execute(select(SchoolSection).where(SchoolSection.org_id == org_id))).scalars().all())


async def _user_role_slugs(db: AsyncSession, user_id: str) -> set[str]:
    rows = (await db.execute(
        select(Role.slug).join(user_roles, Role.id == user_roles.c.role_id).where(user_roles.c.user_id == user_id)
    )).scalars().all()
    return set(rows)


# ── Periods (Rating Setup) ────────────────────────────────────────────────────

def _period_response(p: VotingPeriod, sections: dict) -> PeriodResponse:
    return PeriodResponse(id=p.id, name=p.name, starts_at=p.starts_at, ends_at=p.ends_at, status=p.status,
                          section_id=p.section_id, section_name=sections.get(p.section_id), created_at=p.created_at, org_id=p.org_id)


@router.get("/periods", response_model=list[PeriodResponse], dependencies=[_can_read])
async def list_periods(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(VotingPeriod).where(VotingPeriod.org_id == current_user.org_id, VotingPeriod.is_deleted == False).order_by(VotingPeriod.created_at.desc()))).scalars().all()  # noqa: E712
    sections = await _section_names(db, current_user.org_id)
    return [_period_response(p, sections) for p in rows]


@router.post("/periods", response_model=PeriodResponse, status_code=201, dependencies=[_can_admin])
async def create_period(payload: PeriodCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = VotingPeriod(org_id=current_user.org_id, name=payload.name.strip(), starts_at=payload.starts_at, ends_at=payload.ends_at,
                     section_id=payload.section_id, status="active")
    db.add(p)
    await db.flush()
    return _period_response(p, await _section_names(db, current_user.org_id))


async def _get_period(db, org_id, pid) -> VotingPeriod:
    p = (await db.execute(select(VotingPeriod).where(VotingPeriod.id == pid, VotingPeriod.org_id == org_id, VotingPeriod.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not p:
        raise HTTPException(status_code=404, detail="Period not found.")
    return p


@router.patch("/periods/{pid}/extend", response_model=PeriodResponse, dependencies=[_can_admin])
async def extend_period(pid: str, payload: PeriodExtend, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = await _get_period(db, current_user.org_id, pid)
    p.ends_at = payload.ends_at
    p.status = "active"
    await db.flush()
    return _period_response(p, await _section_names(db, current_user.org_id))


@router.delete("/periods/{pid}", status_code=204, dependencies=[_can_admin])
async def delete_period(pid: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    p = await _get_period(db, current_user.org_id, pid)
    p.is_deleted = True
    p.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Categories (Voting Setup) ─────────────────────────────────────────────────

def _category_response(c: VoteCategory, sections: dict) -> CategoryResponse:
    return CategoryResponse(id=c.id, description=c.description, section_id=c.section_id, section_name=sections.get(c.section_id),
                            is_active=c.is_active, created_at=c.created_at, org_id=c.org_id)


@router.get("/categories", response_model=list[CategoryResponse], dependencies=[_can_read])
async def list_categories(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(VoteCategory).where(VoteCategory.org_id == current_user.org_id, VoteCategory.is_deleted == False).order_by(VoteCategory.created_at.desc()))).scalars().all()  # noqa: E712
    sections = await _section_names(db, current_user.org_id)
    return [_category_response(c, sections) for c in rows]


@router.post("/categories", response_model=CategoryResponse, status_code=201, dependencies=[_can_admin])
async def create_category(payload: CategoryCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = VoteCategory(org_id=current_user.org_id, description=payload.description.strip(), section_id=payload.section_id, is_active=payload.is_active)
    db.add(c)
    await db.flush()
    return _category_response(c, await _section_names(db, current_user.org_id))


async def _get_category(db, org_id, cid) -> VoteCategory:
    c = (await db.execute(select(VoteCategory).where(VoteCategory.id == cid, VoteCategory.org_id == org_id, VoteCategory.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not c:
        raise HTTPException(status_code=404, detail="Category not found.")
    return c


@router.patch("/categories/{cid}", response_model=CategoryResponse, dependencies=[_can_admin])
async def update_category(cid: str, payload: CategoryUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = await _get_category(db, current_user.org_id, cid)
    data = payload.model_dump(exclude_unset=True)
    if "description" in data and data["description"]:
        data["description"] = data["description"].strip()
    for f, v in data.items():
        setattr(c, f, v)
    await db.flush()
    return _category_response(c, await _section_names(db, current_user.org_id))


@router.delete("/categories/{cid}", status_code=204, dependencies=[_can_admin])
async def delete_category(cid: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = await _get_category(db, current_user.org_id, cid)
    c.is_deleted = True
    c.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Sessions (Manage Votes) ───────────────────────────────────────────────────

async def _session_meta(db: AsyncSession, s: VoteSession) -> tuple[list[str], int, int]:
    cat_ids = (await db.execute(select(VoteSessionCategory.category_id).where(VoteSessionCategory.session_id == s.id))).scalars().all()
    cand_count = (await db.execute(select(func.count(VoteCandidate.id)).where(VoteCandidate.session_id == s.id))).scalar() or 0
    ballots = (await db.execute(select(func.count(VoteBallot.id)).where(VoteBallot.session_id == s.id))).scalar() or 0
    return list(cat_ids), cand_count, ballots


async def _session_response(db: AsyncSession, s: VoteSession) -> SessionResponse:
    cat_ids, cand_count, ballots = await _session_meta(db, s)
    return SessionResponse(
        id=s.id, title=s.title, instructions=s.instructions, starts_at=s.starts_at, ends_at=s.ends_at,
        session_id=s.session_id, section_id=s.section_id, positions=s.positions,
        candidate_role=s.candidate_role, voter_role=s.voter_role, status=s.status, result_published=s.result_published,
        category_ids=cat_ids, candidate_count=cand_count, total_ballots=ballots, created_at=s.created_at, org_id=s.org_id,
    )


async def _get_session(db, org_id, sid) -> VoteSession:
    s = (await db.execute(select(VoteSession).where(VoteSession.id == sid, VoteSession.org_id == org_id, VoteSession.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not s:
        raise HTTPException(status_code=404, detail="Vote session not found.")
    return s


@router.get("/sessions", response_model=list[SessionResponse], dependencies=[_can_read])
async def list_sessions(
    status: str | None = Query(default=None), session_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user),
):
    q = select(VoteSession).where(VoteSession.org_id == current_user.org_id, VoteSession.is_deleted == False)  # noqa: E712
    if status:
        q = q.where(VoteSession.status == status)
    if session_id:
        q = q.where(VoteSession.session_id == session_id)
    rows = (await db.execute(q.order_by(VoteSession.created_at.desc()))).scalars().all()
    return [await _session_response(db, s) for s in rows]


async def _set_session_categories(db, session_id, org_id, category_ids: list[str]):
    await db.execute(delete(VoteSessionCategory).where(VoteSessionCategory.session_id == session_id))
    for cid in dict.fromkeys(category_ids):        # dedupe, preserve order
        db.add(VoteSessionCategory(org_id=org_id, session_id=session_id, category_id=cid))


@router.post("/sessions", response_model=SessionResponse, status_code=201, dependencies=[_can_admin])
async def create_session(payload: SessionCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = VoteSession(
        org_id=current_user.org_id, title=payload.title.strip(), instructions=(payload.instructions or None),
        starts_at=payload.starts_at, ends_at=payload.ends_at, session_id=payload.session_id, section_id=payload.section_id,
        positions=payload.positions, candidate_role=payload.candidate_role, voter_role=payload.voter_role, status="draft",
    )
    db.add(s)
    await db.flush()
    await _set_session_categories(db, s.id, current_user.org_id, payload.category_ids)
    await db.flush()
    return await _session_response(db, s)


@router.patch("/sessions/{sid}", response_model=SessionResponse, dependencies=[_can_admin])
async def update_session(sid: str, payload: SessionUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_session(db, current_user.org_id, sid)
    data = payload.model_dump(exclude_unset=True)
    category_ids = data.pop("category_ids", None)
    if "title" in data and data["title"]:
        data["title"] = data["title"].strip()
    for f, v in data.items():
        setattr(s, f, v)
    if category_ids is not None:
        await _set_session_categories(db, s.id, current_user.org_id, category_ids)
    await db.flush()
    return await _session_response(db, s)


@router.delete("/sessions/{sid}", status_code=204, dependencies=[_can_admin])
async def delete_session(sid: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_session(db, current_user.org_id, sid)
    s.is_deleted = True
    s.deleted_at = datetime.now(timezone.utc)
    await db.flush()


@router.post("/sessions/{sid}/open", response_model=SessionResponse, dependencies=[_can_admin])
async def open_session(sid: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_session(db, current_user.org_id, sid)
    s.status = "open"
    await db.flush()
    return await _session_response(db, s)


@router.post("/sessions/{sid}/conduct", response_model=SessionResponse, dependencies=[_can_admin])
async def conduct_session(sid: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_session(db, current_user.org_id, sid)
    s.status = "conducted"
    await db.flush()
    return await _session_response(db, s)


@router.post("/sessions/{sid}/publish", response_model=SessionResponse, dependencies=[_can_admin])
async def publish_results(sid: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_session(db, current_user.org_id, sid)
    if s.status != "conducted":
        s.status = "conducted"
    s.result_published = True
    await db.flush()
    return await _session_response(db, s)


# ── Candidates ────────────────────────────────────────────────────────────────

@router.get("/sessions/{sid}/candidates", response_model=list[CandidateResponse], dependencies=[_can_read])
async def list_candidates(sid: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_session(db, current_user.org_id, sid)
    rows = (await db.execute(select(VoteCandidate).where(VoteCandidate.session_id == s.id))).scalars().all()
    names = dict((uid, name) for uid, name in (await db.execute(select(User.id, User.full_name).where(User.id.in_({c.user_id for c in rows})))).all()) if rows else {}
    return [CandidateResponse(id=c.id, session_id=c.session_id, category_id=c.category_id, user_id=c.user_id, name=names.get(c.user_id)) for c in rows]


@router.post("/sessions/{sid}/candidates", response_model=CandidateResponse, status_code=201, dependencies=[_can_admin])
async def add_candidate(sid: str, payload: CandidateCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_session(db, current_user.org_id, sid)
    user = (await db.execute(select(User).where(User.id == payload.user_id, User.org_id == current_user.org_id, User.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if not user:
        raise HTTPException(status_code=404, detail="Candidate (staff member) not found.")
    exists = (await db.execute(select(VoteCandidate).where(VoteCandidate.session_id == s.id, VoteCandidate.category_id == payload.category_id, VoteCandidate.user_id == payload.user_id))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Already a candidate in this category.")
    c = VoteCandidate(org_id=current_user.org_id, session_id=s.id, category_id=payload.category_id, user_id=payload.user_id)
    db.add(c)
    await db.flush()
    return CandidateResponse(id=c.id, session_id=c.session_id, category_id=c.category_id, user_id=c.user_id, name=user.full_name)


@router.delete("/candidates/{cid}", status_code=204, dependencies=[_can_admin])
async def remove_candidate(cid: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(VoteCandidate).where(VoteCandidate.id == cid, VoteCandidate.org_id == current_user.org_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    await db.delete(c)
    await db.flush()


# ── Results (tally) ───────────────────────────────────────────────────────────

async def _tally(db: AsyncSession, s: VoteSession) -> SessionResults:
    cat_ids = (await db.execute(select(VoteSessionCategory.category_id).where(VoteSessionCategory.session_id == s.id))).scalars().all()
    cats = {c.id: c for c in (await db.execute(select(VoteCategory).where(VoteCategory.id.in_(cat_ids)))).scalars().all()} if cat_ids else {}
    candidates = (await db.execute(select(VoteCandidate).where(VoteCandidate.session_id == s.id))).scalars().all()
    names = dict((uid, name) for uid, name in (await db.execute(select(User.id, User.full_name).where(User.id.in_({c.user_id for c in candidates})))).all()) if candidates else {}
    counts = dict((cand_id, n) for cand_id, n in (await db.execute(
        select(VoteBallot.candidate_id, func.count(VoteBallot.id)).where(VoteBallot.session_id == s.id).group_by(VoteBallot.candidate_id)
    )).all())

    results: list[CategoryResult] = []
    for cid in cat_ids:
        cat_cands = [c for c in candidates if c.category_id == cid]
        rows = [CandidateResponse(id=c.id, session_id=c.session_id, category_id=c.category_id, user_id=c.user_id, name=names.get(c.user_id), votes=counts.get(c.id, 0)) for c in cat_cands]
        rows.sort(key=lambda r: r.votes, reverse=True)
        winners = [r.id for r in rows[: s.positions] if r.votes > 0]
        results.append(CategoryResult(category_id=cid, category_description=(cats[cid].description if cid in cats else None),
                                      total_votes=sum(r.votes for r in rows), candidates=rows, winner_ids=winners))
    return SessionResults(session_id=s.id, title=s.title, status=s.status, result_published=s.result_published, positions=s.positions, categories=results)


@router.get("/sessions/{sid}/results", response_model=SessionResults, dependencies=[_can_read])
async def session_results(sid: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_session(db, current_user.org_id, sid)
    return await _tally(db, s)


# ── Voter self-service (My Votes) ─────────────────────────────────────────────

async def _assert_eligible(db: AsyncSession, s: VoteSession, user: User):
    if s.voter_role:
        if s.voter_role not in await _user_role_slugs(db, user.id):
            raise HTTPException(status_code=403, detail="You’re not eligible to vote in this session.")


@router.get("/open", response_model=list[SessionResponse])
async def open_sessions(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Open sessions the current user may vote in (by voter_role)."""
    rows = (await db.execute(select(VoteSession).where(
        VoteSession.org_id == current_user.org_id, VoteSession.is_deleted == False, VoteSession.status == "open"  # noqa: E712
    ).order_by(VoteSession.created_at.desc()))).scalars().all()
    my_roles = await _user_role_slugs(db, current_user.id)
    eligible = [s for s in rows if (not s.voter_role) or (s.voter_role in my_roles)]
    return [await _session_response(db, s) for s in eligible]


@router.get("/sessions/{sid}/ballot", response_model=BallotView)
async def ballot_view(sid: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """A voter's ballot — categories + candidates + what they've already chosen.
    Eligibility-gated (voter_role), NOT school:read, so students can vote."""
    s = await _get_session(db, current_user.org_id, sid)
    await _assert_eligible(db, s, current_user)
    cat_ids = (await db.execute(select(VoteSessionCategory.category_id).where(VoteSessionCategory.session_id == s.id))).scalars().all()
    cats = {c.id: c for c in (await db.execute(select(VoteCategory).where(VoteCategory.id.in_(cat_ids)))).scalars().all()} if cat_ids else {}
    candidates = (await db.execute(select(VoteCandidate).where(VoteCandidate.session_id == s.id))).scalars().all()
    names = dict((uid, name) for uid, name in (await db.execute(select(User.id, User.full_name).where(User.id.in_({c.user_id for c in candidates})))).all()) if candidates else {}
    mine = {cat_id: cand_id for cat_id, cand_id in (await db.execute(
        select(VoteBallot.category_id, VoteBallot.candidate_id).where(VoteBallot.session_id == s.id, VoteBallot.voter_user_id == current_user.id)
    )).all()}
    categories = [
        BallotCategory(category_id=cid, description=(cats[cid].description if cid in cats else None),
                       candidates=[BallotCandidate(id=c.id, name=names.get(c.user_id)) for c in candidates if c.category_id == cid])
        for cid in cat_ids
    ]
    return BallotView(session_id=s.id, title=s.title, instructions=s.instructions, categories=categories, my_votes=mine)


@router.post("/sessions/{sid}/vote", status_code=201, dependencies=[])
async def cast_vote(sid: str, payload: BallotCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_session(db, current_user.org_id, sid)
    if s.status != "open":
        raise HTTPException(status_code=409, detail="Voting isn’t open for this session.")
    now = datetime.now(timezone.utc)
    if s.ends_at and now > s.ends_at:
        raise HTTPException(status_code=409, detail="Voting has closed for this session.")
    await _assert_eligible(db, s, current_user)

    cand = (await db.execute(select(VoteCandidate).where(
        VoteCandidate.id == payload.candidate_id, VoteCandidate.session_id == s.id, VoteCandidate.category_id == payload.category_id
    ))).scalar_one_or_none()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found in that category.")
    dup = (await db.execute(select(VoteBallot).where(
        VoteBallot.session_id == s.id, VoteBallot.category_id == payload.category_id, VoteBallot.voter_user_id == current_user.id
    ))).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="You’ve already voted in this category.")
    b = VoteBallot(org_id=current_user.org_id, session_id=s.id, category_id=payload.category_id, candidate_id=cand.id, voter_user_id=current_user.id)
    db.add(b)
    await db.flush()
    return {"ok": True, "category_id": payload.category_id, "candidate_id": cand.id}


@router.get("/sessions/{sid}/my-votes", response_model=dict)
async def my_votes(sid: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_session(db, current_user.org_id, sid)
    rows = (await db.execute(select(VoteBallot.category_id, VoteBallot.candidate_id).where(
        VoteBallot.session_id == s.id, VoteBallot.voter_user_id == current_user.id
    ))).all()
    return {cat_id: cand_id for cat_id, cand_id in rows}
