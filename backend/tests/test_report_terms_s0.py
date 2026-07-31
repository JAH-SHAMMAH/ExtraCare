"""Secondary Report parity S-0: Terms & Sub-term + Term Periods (Begins/Ends +
Attendance) + Deadlines."""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.modules.platform import AcademicSession
from app.routers.modules.platform import (
    create_sub_term, list_sub_terms, update_sub_term, delete_sub_term,
    create_term, list_terms, update_term, delete_term, bootstrap_terms,
    upsert_term_period, list_term_periods, delete_term_period,
    create_deadline, list_deadlines, update_deadline,
)
from app.schemas.platform import (
    SubTermCreate, SubTermUpdate, TermCreate, TermUpdate,
    TermPeriodUpsert, DeadlineUpsert,
)


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Registrar",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def _session(db, org) -> AcademicSession:
    s = AcademicSession(id=str(uuid.uuid4()), name="2025/2026", is_current=True, org_id=org.id)
    db.add(s)
    await db.commit()
    return s


async def test_bootstrap_seeds_terms_and_sub_terms(db, org):
    admin = await _admin(db, org)
    terms = await bootstrap_terms(db=db, current_user=admin)
    assert {t.name for t in terms} == {"Autumn", "Spring", "Summer"}
    subs = await list_sub_terms(db=db, current_user=admin)
    assert {s.name for s in subs} == {"Half-Term", "Full-Term"}
    # Idempotent — a second run adds nothing.
    await bootstrap_terms(db=db, current_user=admin)
    assert len(await list_terms(db=db, current_user=admin)) == 3
    assert len(await list_sub_terms(db=db, current_user=admin)) == 2


async def test_sub_term_crud_and_duplicate(db, org):
    admin = await _admin(db, org)
    s = await create_sub_term(payload=SubTermCreate(name="Half-Term", position=1), db=db, current_user=admin)
    assert s.is_active is True
    with pytest.raises(HTTPException) as ei:
        await create_sub_term(payload=SubTermCreate(name="Half-Term"), db=db, current_user=admin)
    assert ei.value.status_code == 409
    s2 = await update_sub_term(s.id, SubTermUpdate(alias="Mid-Term", is_active=False), db=db, current_user=admin)
    assert s2.alias == "Mid-Term" and s2.is_active is False
    await delete_sub_term(s.id, db=db, current_user=admin)
    assert len(await list_sub_terms(db=db, current_user=admin)) == 0


async def test_term_active_exclusivity_and_sub_term_link(db, org):
    admin = await _admin(db, org)
    half = await create_sub_term(payload=SubTermCreate(name="Half-Term", position=1), db=db, current_user=admin)
    autumn = await create_term(payload=TermCreate(name="Autumn", position=1), db=db, current_user=admin)
    spring = await create_term(payload=TermCreate(name="Spring", position=2), db=db, current_user=admin)

    await update_term(autumn.id, TermUpdate(is_active=True), db=db, current_user=admin)
    await update_term(spring.id, TermUpdate(is_active=True, active_sub_term_id=half.id), db=db, current_user=admin)
    terms = {t.name: t for t in await list_terms(db=db, current_user=admin)}
    assert terms["Spring"].is_active is True and terms["Autumn"].is_active is False   # exactly one active
    assert terms["Spring"].active_sub_term_name == "Half-Term" and terms["Spring"].active_sub_term_position == 1

    # Bad sub-term reference rejected.
    with pytest.raises(HTTPException) as ei:
        await update_term(spring.id, TermUpdate(active_sub_term_id="nope"), db=db, current_user=admin)
    assert ei.value.status_code == 422

    await delete_term(autumn.id, db=db, current_user=admin)
    assert len(await list_terms(db=db, current_user=admin)) == 1


async def test_term_period_upsert_and_deadline(db, org):
    admin = await _admin(db, org)
    sess = await _session(db, org)
    half = await create_sub_term(payload=SubTermCreate(name="Half-Term", position=1), db=db, current_user=admin)
    autumn = await create_term(payload=TermCreate(name="Autumn", position=1), db=db, current_user=admin)

    p1 = await upsert_term_period(payload=TermPeriodUpsert(
        session_id=sess.id, term_id=autumn.id, sub_term_id=half.id,
        begin_date=date(2025, 9, 8), end_date=date(2025, 10, 17), excluded_days=12, total_days=28,
        next_term_begins=date(2025, 10, 27), published_date=date(2025, 10, 28)), db=db, current_user=admin)
    assert p1.term_name == "Autumn" and p1.sub_term_name == "Half-Term" and p1.total_days == 28

    # Upsert on the same (session, term, sub-term) updates in place — no duplicate.
    p2 = await upsert_term_period(payload=TermPeriodUpsert(
        session_id=sess.id, term_id=autumn.id, sub_term_id=half.id, total_days=30), db=db, current_user=admin)
    assert p2.id == p1.id and p2.total_days == 30
    rows = await list_term_periods(session_id=sess.id, db=db, current_user=admin)
    assert len(rows) == 1

    await delete_term_period(p1.id, db=db, current_user=admin)
    assert len(await list_term_periods(session_id=sess.id, db=db, current_user=admin)) == 0

    d = await create_deadline(payload=DeadlineUpsert(
        session_id=sess.id, term_id=autumn.id, sub_term_id=half.id, status="open",
        submission_deadline=date(2025, 10, 20)), db=db, current_user=admin)
    assert d.term_name == "Autumn" and d.status == "open"
    d2 = await update_deadline(d.id, DeadlineUpsert(session_id=sess.id, term_id=autumn.id, status="closed"), db=db, current_user=admin)
    assert d2.status == "closed"
    assert len(await list_deadlines(session_id=sess.id, db=db, current_user=admin)) == 1
