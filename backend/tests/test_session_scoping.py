"""Session-scoped report setup: the year a mark belongs to (migration 134).

Terms are ORG-WIDE and shared across years — "Autumn" is one row in
`academic_terms`, reused every session. Before this, `assessments` and
`cumulatives` were scoped to (term, sub-term) and nothing else, so 2026/2027's
Autumn marks would have landed on the very same assessment rows as 2025/2026's,
and nothing afterwards could have told the two years apart.

Four things are pinned here:

  BACKFILL — every pre-existing row belongs to the one session that existed.
  ISOLATION — two sessions sharing a term name do not see each other's setup or
    each other's marks. This is the one that matters: the failure it guards
    against is silent, and produces a plausible-looking wrong number.
  THE DELETE GUARD — a session holding results cannot be deleted, because
    `assessments.term_id` cascades to marks and a cascading session FK would put
    a whole year one request away.
  ARCHIVE REACHABILITY — the point of keeping the year on the row is that last
    year stays readable after the school rolls over. An implicit
    current-session-only rule would have made a 2025/2026 card unprintable the
    moment 2026/2027 began.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.modules.platform import (
    AcademicSession, AcademicSubTerm, AcademicTerm, Assessment, Cumulative,
    CumulativeComponent, StudentAssessmentScore,
)
from app.models.modules.school import SchoolClass, Student, Subject
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.services.result_analysis import analyse_term
from app.services.session_scope import (
    load_term_setup, resolve_session_id, session_or_current,
)
from tests.conftest import ensure_section


async def _admin(db, org) -> User:
    role = Role(id=str(uuid.uuid4()), name="org_admin", slug=f"a-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["org_admin"]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@example.com",
             full_name="Admin", status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _year(db, org, name: str, *, current: bool) -> AcademicSession:
    s = AcademicSession(
        id=str(uuid.uuid4()), name=name, term="Autumn",
        start_date=date(int(name[:4]), 9, 15), end_date=date(int(name[:4]) + 1, 7, 10),
        is_current=current, org_id=org.id)
    db.add(s)
    await db.commit()
    return s


async def _setup_for(db, org, sess, term, sub, subject, pupil, *, score):
    """One assessment + one TOTAL cumulative for `sess`, and a mark for `pupil`.

    The term and sub-term rows are SHARED between sessions on purpose — that is
    the real schema, and the whole reason session_id has to exist.
    """
    a = Assessment(id=str(uuid.uuid4()), name="CBT Exam Score", max_score=Decimal("100"),
                   session_id=sess.id, term_id=term.id, sub_term_id=sub.id, org_id=org.id)
    db.add(a)
    await db.commit()
    c = Cumulative(id=str(uuid.uuid4()), name="TOTAL", cumul_type="percentage",
                   session_id=sess.id, term_id=term.id, sub_term_id=sub.id, org_id=org.id)
    db.add(c)
    await db.commit()
    db.add(CumulativeComponent(id=str(uuid.uuid4()), cumulative_id=c.id,
                               ref_type="assessment", ref_id=a.id, position=0,
                               org_id=org.id))
    db.add(StudentAssessmentScore(id=str(uuid.uuid4()), student_id=pupil.id,
                                  subject_id=subject.id, assessment_id=a.id,
                                  score=Decimal(score), source="entry", org_id=org.id))
    await db.commit()
    return a, c


async def _two_years(db, org):
    """2025/2026 (not current) and 2026/2027 (current), same term, same pupil.

    The pupil scores 40 in the old year and 90 in the new one, so any bleed
    between them shows up as an average nobody recorded.
    """
    term = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    sub = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=1, org_id=org.id)
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="JSS1", org_id=org.id)
    _sec = await ensure_section(db, org)
    subject = Subject(id=str(uuid.uuid4()), name="Mathematics", section_id=_sec.id, org_id=org.id)
    db.add_all([term, sub, cls, subject])
    await db.commit()
    pupil = Student(id=str(uuid.uuid4()), student_id="FSN-0001", first_name="Ada",
                    last_name="Obi", class_id=cls.id, org_id=org.id)
    db.add(pupil)
    await db.commit()

    old = await _year(db, org, "2025/2026", current=False)
    new = await _year(db, org, "2026/2027", current=True)
    await _setup_for(db, org, old, term, sub, subject, pupil, score=40)
    await _setup_for(db, org, new, term, sub, subject, pupil, score=90)
    return dict(term=term, sub=sub, cls=cls, subject=subject, pupil=pupil,
                old=old, new=new)


# ── the backfill ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_single_session_is_the_only_candidate_for_the_backfill(db, org):
    """Migration 134's premise: with one session, no row's year is a guess.

    The resolver and the migration use the same preference order, so this is the
    same choice the backfill made against production.
    """
    only = await _year(db, org, "2025/2026", current=True)
    assert await resolve_session_id(db, org.id) == only.id

    # And with the flag unset it still resolves, because there is one session to
    # mean — the fallback `resolve_academic_year` has always had.
    only.is_current = False
    await db.commit()
    assert await resolve_session_id(db, org.id) == only.id


@pytest.mark.asyncio
async def test_two_sessions_with_no_current_one_resolves_to_nothing(db, org):
    """Ambiguity returns None rather than picking. A wrong year silently blends
    two years of marks; no year renders an honest "not configured"."""
    await _year(db, org, "2025/2026", current=False)
    await _year(db, org, "2026/2027", current=False)
    assert await resolve_session_id(db, org.id) is None


# ── cross-session isolation: the one that matters ────────────────────────────

@pytest.mark.asyncio
async def test_two_sessions_sharing_a_term_do_not_see_each_others_setup(db, org):
    w = await _two_years(db, org)

    old = await load_term_setup(db, org.id, w["old"].id, w["term"].id)
    new = await load_term_setup(db, org.id, w["new"].id, w["term"].id)

    assert len(old.assessments) == 1 and len(new.assessments) == 1
    assert set(old.assessments) & set(new.assessments) == set(), (
        "the two years share a TERM row but must not share assessment rows")
    assert len(old.cumulatives) == 1 and len(new.cumulatives) == 1
    assert old.cumulatives[0].id != new.cumulatives[0].id

    # The component map must be scoped too: loading one year must not carry the
    # other year's components, which is what an org-wide load would have done.
    assert set(old.components) == {old.cumulatives[0].id}
    assert set(new.components) == {new.cumulatives[0].id}


@pytest.mark.asyncio
async def test_a_pupils_marks_do_not_bleed_between_sessions(db, org):
    """40 last year, 90 this year. Either figure appearing under the other
    year — or an 65 average of the two — is the failure this guards."""
    w = await _two_years(db, org)

    this_year = await analyse_term(db, org.id, w["term"].id, w["sub"].id,
                                   class_id=w["cls"].id, session_id=w["new"].id)
    last_year = await analyse_term(db, org.id, w["term"].id, w["sub"].id,
                                   class_id=w["cls"].id, session_id=w["old"].id)

    assert not this_year.not_configured and not last_year.not_configured
    got_new = this_year.pupils[0].subject_pct[w["subject"].id]
    got_old = last_year.pupils[0].subject_pct[w["subject"].id]
    assert got_new == Decimal("90"), f"this year should be 90, got {got_new}"
    assert got_old == Decimal("40"), f"last year should be 40, got {got_old}"


@pytest.mark.asyncio
async def test_an_omitted_session_means_the_current_one_not_every_one(db, org):
    """The default has to be this year, never a blend. A caller that forgets gets
    the current year's answer, not an average across the school's history."""
    w = await _two_years(db, org)

    defaulted = await analyse_term(db, org.id, w["term"].id, w["sub"].id,
                                   class_id=w["cls"].id)
    assert defaulted.pupils[0].subject_pct[w["subject"].id] == Decimal("90")


@pytest.mark.asyncio
async def test_another_orgs_session_id_is_not_honoured(db, org):
    """A query string must not select another tenant's year."""
    from app.models.organization import Organization, IndustryType

    other = Organization(id=str(uuid.uuid4()), name="Other School",
                         slug=f"other-{uuid.uuid4().hex[:8]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    await db.commit()
    theirs = AcademicSession(id=str(uuid.uuid4()), name="2025/2026",
                             is_current=True, org_id=other.id)
    db.add(theirs)
    await db.commit()

    mine = await _year(db, org, "2026/2027", current=True)

    # REFUSED, not silently swapped for our own current year. Falling back would
    # answer a different question than the one asked — "here are 2026/2027's
    # numbers" in response to a request for another year — without saying so.
    # None renders as "not configured", which is honest.
    assert await session_or_current(db, org.id, theirs.id) is None, (
        "a foreign session id must not be honoured")

    # An id that IS ours is honoured, so the check above is about ownership and
    # not about rejecting everything.
    assert await session_or_current(db, org.id, mine.id) == mine.id
    # And omitting it still defaults to our current year.
    assert await session_or_current(db, org.id, None) == mine.id


# ── the delete guard ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_session_holding_results_cannot_be_deleted(db, org):
    from app.routers.modules.platform import delete_session

    w = await _two_years(db, org)
    admin = await _admin(db, org)

    with pytest.raises(HTTPException) as e:
        await delete_session(w["old"].id, db, admin)
    assert e.value.status_code == 409
    detail = str(e.value.detail)
    # The refusal has to say what it is protecting, in counts.
    assert "2025/2026" in detail
    assert "1 assessment" in detail and "1 recorded mark" in detail

    still_there = (await db.execute(select(AcademicSession).where(
        AcademicSession.id == w["old"].id))).scalar_one_or_none()
    assert still_there is not None, "the refusal must not have deleted anything"


@pytest.mark.asyncio
async def test_an_empty_session_still_deletes(db, org):
    """The guard protects results, not sessions. A year created by mistake, with
    no setup under it, must still be removable."""
    from app.routers.modules.platform import delete_session

    admin = await _admin(db, org)
    spare = await _year(db, org, "2027/2028", current=False)

    await delete_session(spare.id, db, admin)
    await db.commit()
    gone = (await db.execute(select(AcademicSession).where(
        AcademicSession.id == spare.id))).scalar_one_or_none()
    assert gone is None


# ── archive reachability ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_last_years_card_is_still_readable_after_the_rollover(db, org):
    """2026/2027 is current; 2025/2026 must remain printable.

    This is the whole reason sessioning is explicit rather than implicit. A
    school needs last year's results for transcripts, appeals and leaver
    references long after the year has turned over.
    """
    w = await _two_years(db, org)

    assert await resolve_session_id(db, org.id) == w["new"].id, "this year is current"

    archived = await load_term_setup(db, org.id, w["old"].id, w["term"].id)
    assert archived.assessments, "last year's setup must still load"
    assert archived.cumulatives

    analysis = await analyse_term(db, org.id, w["term"].id, w["sub"].id,
                                  class_id=w["cls"].id, session_id=w["old"].id)
    assert not analysis.not_configured
    assert analysis.pupils[0].subject_pct[w["subject"].id] == Decimal("40")
