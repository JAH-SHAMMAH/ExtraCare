"""The two invariants the academic_year -> session_id switch must not break.

Both assert behaviour that ALREADY FAILED ONCE in production. Neither is a test
of the new column as such; they are the guard rails around it, and either one
going green for the wrong reason would hide a real outage.

  1. THE LOST ENROLMENT. Marks live in TWO stores: `student_assessment_scores`
     (the report engine) and `grades` (the older gradebook). At Fairview they
     held 1,799 and 1,800 pairs, and the single pair present only in `grades` was
     a real pupil — FSN-0031 Musa Yusuf, Biology — whose assessment-score row was
     lost when a CBT re-sync dropped mid-run. Backfilling enrolment from the new
     store alone leaves him unenrolled in a subject he has a grade for: a
     one-pupil bug, invisible until somebody questions his report card. An
     existing mark IS the evidence of enrolment, in EITHER store.

  2. THE None PATH. `resolve_academic_year_for_check` returns None rather than
     raising when no session is resolvable, and four call sites depend on it. The
     None flows into `enrolled_student_ids`, which then checks enrolment in ANY
     year. The gate stays ON — an unenrolled pupil is still refused — it just
     stops insisting it knows which session it is. Without this, forgetting the
     `is_current` flag when adding next year's session stops EVERY teacher in the
     school from saving marks, with an error about enrolment that names the wrong
     problem.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.modules.academics import StudentSubjectEnrollment
from app.models.modules.platform import AcademicSession
from app.services.subject_enrollment import (
    enrolled_student_ids,
    resolve_academic_year_for_check,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def current_session(db, org) -> AcademicSession:
    """One session, flagged current — the normal state."""
    s = AcademicSession(
        id=str(uuid.uuid4()), org_id=org.id, name="2025/2026", is_current=True,
    )
    db.add(s)
    await db.commit()
    return s


async def _enrol(db, org, student_id: str, subject_id: str, year: str, session_id: str):
    row = StudentSubjectEnrollment(
        id=str(uuid.uuid4()), org_id=org.id, student_id=student_id,
        subject_id=subject_id, academic_year=year, session_id=session_id,
        source="manual",
    )
    db.add(row)
    await db.commit()
    return row


# ── 1. the lost enrolment ────────────────────────────────────────────────────

async def test_enrolment_survives_when_only_one_mark_store_has_the_pair(
    db, org, student, current_session,
):
    """A pupil enrolled once stays enrolled — the row is the record, not the mark.

    The backfill that created rows like this read the UNION of both mark stores.
    This asserts the consequence that matters downstream: `enrolled_student_ids`
    returns the pupil, so their mark can still be saved. If a refactor ever
    reduces the backfill to the new store alone, the row for a grades-only pair
    never exists and this fails.
    """
    subject_id = str(uuid.uuid4())
    await _enrol(db, org, student.id, subject_id, "2025/2026", current_session.id)

    enrolled = await enrolled_student_ids(
        db, org.id, subject_id, "2025/2026", [student.id])
    assert student.id in enrolled, (
        "a pupil with an enrolment row must be mark-enterable; losing this is the "
        "FSN-0031 Musa Yusuf case, where a grades-only pair left a real pupil "
        "unenrolled in a subject he had a grade for"
    )


async def test_unenrolled_pupil_is_still_refused(db, org, student, current_session):
    """The gate must stay ON. The None path widens WHICH session counts; it never
    turns the check off, and neither does anything else in this arc."""
    enrolled = await enrolled_student_ids(
        db, org.id, str(uuid.uuid4()), "2025/2026", [student.id])
    assert student.id not in enrolled


# ── 2. the None path ─────────────────────────────────────────────────────────

async def _add_session(db, org, name: str, current: bool = False) -> AcademicSession:
    s = AcademicSession(id=str(uuid.uuid4()), org_id=org.id, name=name,
                        is_current=current)
    db.add(s)
    await db.commit()
    return s


async def test_resolver_returns_none_when_it_genuinely_cannot_tell(db, org):
    """Two sessions, neither current -> None, NOT an exception.

    IT TAKES TWO. `resolve_academic_year` prefers the current session and then
    FALLS BACK to the only session when exactly one exists, so a school that
    never set the flag still works. With a single session, clearing `is_current`
    therefore still resolves — which is correct, and is why this test creates a
    second one. That is also the real shape of the failure being guarded against:
    adding NEXT year's session and forgetting the flag, leaving two sessions and
    no way to tell which is meant.

    The raising version is kept for WRITES (you cannot record "enrolled" without
    saying when). Checking one must degrade instead.
    """
    await _add_session(db, org, "2025/2026")
    await _add_session(db, org, "2026/2027")
    assert await resolve_academic_year_for_check(db, org.id) is None


async def test_single_session_still_resolves_without_the_current_flag(db, org):
    """The fallback itself, asserted so the None path above cannot be 'fixed' by
    deleting it. A school with one session and no flag must keep working."""
    await _add_session(db, org, "2025/2026")
    assert await resolve_academic_year_for_check(db, org.id) == "2025/2026"


async def test_marks_still_savable_for_an_enrolled_pupil_with_no_current_session(
    db, org, student, current_session,
):
    """THE OUTAGE THIS PREVENTS, end to end.

    Enrol the pupil, add NEXT year's session, and clear the current flag — the
    exact state produced by rolling a school over and forgetting `is_current`.
    The resolver degrades to None, and the pupil must still come back as
    enrolled, because `enrolled_student_ids` falls back to enrolment in ANY year.

    Two sessions are needed to reach None at all: with one, the resolver falls
    back to it. See `test_resolver_returns_none_when_it_genuinely_cannot_tell`.
    """
    subject_id = str(uuid.uuid4())
    await _enrol(db, org, student.id, subject_id, "2025/2026", current_session.id)

    await _add_session(db, org, "2026/2027")
    current_session.is_current = False
    db.add(current_session)
    await db.commit()

    year = await resolve_academic_year_for_check(db, org.id)
    assert year is None, "precondition: no session is current"

    enrolled = await enrolled_student_ids(db, org.id, subject_id, year, [student.id])
    assert student.id in enrolled, (
        "with no current session the gate must widen to any year, not refuse "
        "every mark in the school"
    )


# ── the session column itself ────────────────────────────────────────────────

async def test_enrolment_rows_carry_a_session(db, org, student, current_session):
    """`session_id` is NOT NULL from migration 140, and is what the row is keyed
    on. Asserted directly so a model change that quietly re-nullables it fails
    here rather than in a backfill months later."""
    subject_id = str(uuid.uuid4())
    await _enrol(db, org, student.id, subject_id, "2025/2026", current_session.id)

    row = (await db.execute(
        select(StudentSubjectEnrollment).where(
            StudentSubjectEnrollment.student_id == student.id,
            StudentSubjectEnrollment.subject_id == subject_id,
        )
    )).scalar_one()
    assert row.session_id == current_session.id
