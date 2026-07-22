"""Tests for the Voting System module.

Covers the full flow end-to-end — period lifecycle, categories, a session with
candidates, opening it, eligible voters casting one ballot per category (dupes
rejected), tallying (winner = most votes), and publishing — plus voter-role
eligibility, the open-window guard, org isolation and the school:write gate.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.core.permissions import PermissionChecker
from app.routers.modules.voting import (
    create_period, extend_period, delete_period, list_periods,
    create_category, update_category, list_categories,
    create_session, update_session, add_candidate, open_session, conduct_session, publish_results,
    session_results, cast_vote, open_sessions, my_votes, ballot_view,
)
from app.schemas.voting import (
    PeriodCreate, PeriodExtend, CategoryCreate, CategoryUpdate,
    SessionCreate, SessionUpdate, CandidateCreate, BallotCreate,
)

pytestmark = pytest.mark.asyncio


async def _staff(db, org, name) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{name.replace(' ', '.').lower()}-{uuid.uuid4().hex[:5]}@example.com",
             full_name=name, status=UserStatus.ACTIVE, org_id=org.id)
    db.add(u)
    await db.commit()
    return u


async def _voter(db, org, name, role: Role | None) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{name.replace(' ', '.').lower()}-{uuid.uuid4().hex[:5]}@example.com",
             full_name=name, status=UserStatus.ACTIVE, org_id=org.id)
    if role:
        u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _role(db, org, slug) -> Role:
    r = Role(id=str(uuid.uuid4()), name=slug.title(), slug=slug, permissions=[], org_id=org.id, is_system=True)
    db.add(r)
    await db.commit()
    return r


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


# ── Setup CRUD ────────────────────────────────────────────────────────────────

async def test_period_lifecycle(db, org, teacher):
    p = await create_period(PeriodCreate(name="January"), db=db, current_user=teacher)
    assert p.status == "active"
    ext = await extend_period(p.id, PeriodExtend(ends_at=datetime.now(timezone.utc) + timedelta(days=2)), db=db, current_user=teacher)
    assert ext.ends_at is not None
    await delete_period(p.id, db=db, current_user=teacher)
    assert p.id not in [x.id for x in await list_periods(db=db, current_user=teacher)]


async def test_category_crud(db, org, teacher):
    c = await create_category(CategoryCreate(description="  Best Staff — Diction  "), db=db, current_user=teacher)
    assert c.description == "Best Staff — Diction"
    upd = await update_category(c.id, CategoryUpdate(is_active=False), db=db, current_user=teacher)
    assert upd.is_active is False
    assert c.id in [x.id for x in await list_categories(db=db, current_user=teacher)]


# ── Full voting flow ──────────────────────────────────────────────────────────

async def test_full_voting_flow(db, org, teacher):
    student_role = await _role(db, org, "student")
    cat = await create_category(CategoryCreate(description="Best Teacher"), db=db, current_user=teacher)
    a = await _staff(db, org, "Teacher Alpha")
    b = await _staff(db, org, "Teacher Beta")

    s = await create_session(SessionCreate(title="Awards 2026", voter_role="student", positions=1, category_ids=[cat.id]),
                             db=db, current_user=teacher)
    assert s.status == "draft" and s.category_ids == [cat.id]

    ca = await add_candidate(s.id, CandidateCreate(category_id=cat.id, user_id=a.id), db=db, current_user=teacher)
    cb = await add_candidate(s.id, CandidateCreate(category_id=cat.id, user_id=b.id), db=db, current_user=teacher)

    # Can't vote before it's open.
    v1 = await _voter(db, org, "Voter One", student_role)
    with pytest.raises(HTTPException) as pre:
        await cast_vote(s.id, BallotCreate(category_id=cat.id, candidate_id=ca.id), db=db, current_user=v1)
    assert pre.value.status_code == 409

    await open_session(s.id, db=db, current_user=teacher)
    v2 = await _voter(db, org, "Voter Two", student_role)
    v3 = await _voter(db, org, "Voter Three", student_role)

    await cast_vote(s.id, BallotCreate(category_id=cat.id, candidate_id=ca.id), db=db, current_user=v1)  # A
    await cast_vote(s.id, BallotCreate(category_id=cat.id, candidate_id=ca.id), db=db, current_user=v2)  # A
    await cast_vote(s.id, BallotCreate(category_id=cat.id, candidate_id=cb.id), db=db, current_user=v3)  # B

    # One vote per category — v1 can't vote again.
    with pytest.raises(HTTPException) as dup:
        await cast_vote(s.id, BallotCreate(category_id=cat.id, candidate_id=cb.id), db=db, current_user=v1)
    assert dup.value.status_code == 409

    # v1 sees their own vote.
    mine = await my_votes(s.id, db=db, current_user=v1)
    assert mine.get(cat.id) == ca.id

    # Tally: A=2, B=1, winner A.
    res = await session_results(s.id, db=db, current_user=teacher)
    catres = res.categories[0]
    assert catres.total_votes == 3
    top = catres.candidates[0]
    assert top.id == ca.id and top.votes == 2
    assert catres.winner_ids == [ca.id]

    # Publish.
    pub = await publish_results(s.id, db=db, current_user=teacher)
    assert pub.result_published is True and pub.status == "conducted" and pub.total_ballots == 3


async def test_ineligible_voter_rejected(db, org, teacher):
    await _role(db, org, "student")
    cat = await create_category(CategoryCreate(description="Award"), db=db, current_user=teacher)
    staff = await _staff(db, org, "Cand One")
    s = await create_session(SessionCreate(title="S", voter_role="student", category_ids=[cat.id]), db=db, current_user=teacher)
    c = await add_candidate(s.id, CandidateCreate(category_id=cat.id, user_id=staff.id), db=db, current_user=teacher)
    await open_session(s.id, db=db, current_user=teacher)

    outsider = await _voter(db, org, "No Role", None)     # not a student
    with pytest.raises(HTTPException) as exc:
        await cast_vote(s.id, BallotCreate(category_id=cat.id, candidate_id=c.id), db=db, current_user=outsider)
    assert exc.value.status_code == 403


async def test_open_sessions_lists_eligible(db, org, teacher):
    student_role = await _role(db, org, "student")
    cat = await create_category(CategoryCreate(description="A"), db=db, current_user=teacher)
    s = await create_session(SessionCreate(title="Open One", voter_role="student", category_ids=[cat.id]), db=db, current_user=teacher)
    await open_session(s.id, db=db, current_user=teacher)
    voter = await _voter(db, org, "Elig", student_role)
    assert s.id in [x.id for x in await open_sessions(db=db, current_user=voter)]
    outsider = await _voter(db, org, "Inelig", None)
    assert s.id not in [x.id for x in await open_sessions(db=db, current_user=outsider)]


async def test_ballot_view(db, org, teacher):
    student_role = await _role(db, org, "student")
    cat = await create_category(CategoryCreate(description="Award X"), db=db, current_user=teacher)
    staff = await _staff(db, org, "Cand Two")
    s = await create_session(SessionCreate(title="Ballot S", voter_role="student", category_ids=[cat.id]), db=db, current_user=teacher)
    cand = await add_candidate(s.id, CandidateCreate(category_id=cat.id, user_id=staff.id), db=db, current_user=teacher)
    await open_session(s.id, db=db, current_user=teacher)

    voter = await _voter(db, org, "Ballot Voter", student_role)
    view = await ballot_view(s.id, db=db, current_user=voter)
    assert view.title == "Ballot S" and len(view.categories) == 1
    assert view.categories[0].candidates[0].id == cand.id and view.my_votes == {}

    # After voting, my_votes reflects the choice.
    await cast_vote(s.id, BallotCreate(category_id=cat.id, candidate_id=cand.id), db=db, current_user=voter)
    view2 = await ballot_view(s.id, db=db, current_user=voter)
    assert view2.my_votes.get(cat.id) == cand.id

    # Ineligible voter can't even see the ballot.
    outsider = await _voter(db, org, "Ballot Outsider", None)
    with pytest.raises(HTTPException) as exc:
        await ballot_view(s.id, db=db, current_user=outsider)
    assert exc.value.status_code == 403


async def test_org_isolation(db, org, teacher):
    cat = await create_category(CategoryCreate(description="Mine"), db=db, current_user=teacher)
    other = SimpleNamespace(org_id=str(uuid.uuid4()))
    assert cat.id not in [x.id for x in await list_categories(db=db, current_user=other)]


# ── RBAC (admin gated school:write) ───────────────────────────────────────────

async def _run_gate(user, org, db):
    checker = PermissionChecker("school:write")
    request = SimpleNamespace(state=SimpleNamespace(org=org, org_id=org.id))
    return await checker(request=request, current_user=user, db=db)


async def test_voting_admin_rbac(db, org):
    parent = await _preset_user(db, org, "parent")
    assert not parent.has_permission("school:write")
    with pytest.raises(HTTPException) as exc:
        await _run_gate(parent, org, db)
    assert exc.value.status_code == 403
    tchr = await _preset_user(db, org, "teacher")
    assert (await _run_gate(tchr, org, db)).id == tchr.id
