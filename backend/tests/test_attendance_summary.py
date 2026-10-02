"""Where the report card's attendance figures come from (migrations 135/136).

`attendance_present` and `attendance_total` used to be whatever a teacher typed,
while `attendance_punctual` beside them was COUNTED from the daily register —
two sources on one card, free to contradict each other. All three now come from
one service that also says which source it used.

Five things are pinned:

  NO CLIFF — the register overrides the authored figure only when it is COMPLETE
    for the term. One marked day must NOT flip a pupil from 50/60 to 1/1 on a
    parent-facing card. This is the whole reason the completeness rule exists.
  THE STATUS MAPPING — PRESENT is present and punctual; LATE is present and not
    punctual; EXCUSED is absent but stays in the denominator.
  THE WINDOW BOUNDS THE COUNT — days outside the term must not be counted. The
    rule this replaces matched `AcademicSession.term` against a term name, which
    on production found nothing for Spring and silently counted a pupil's entire
    roll-call history as the term's.
  PROVENANCE IS REPORTED — `source` distinguishes counted from typed, and
    register_days/required_days make a partial register visible.
  NOTHING KNOWN MEANS NOTHING SAID — no register and no authored figure yields
    source="none" and None, never 0 of 0.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.models.modules.platform import (
    AcademicSession, AcademicSubTerm, AcademicTerm, TermPeriod,
)
from app.models.modules.school import (
    AttendanceRecord, AttendanceStatus, SchoolClass, Student, StudentReport,
)
from app.services.attendance_summary import term_attendance

pytestmark = pytest.mark.asyncio

BEGIN = date(2025, 9, 15)
END = date(2025, 12, 12)


class W:
    pass


async def _world(db, org, *, total_days: int | None = 10, with_period=True):
    w = W()
    w.session = AcademicSession(id=str(uuid.uuid4()), name="2025/2026",
                                start_date=BEGIN, end_date=END,
                                is_current=True, org_id=org.id)
    w.term = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    w.sub = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=1, org_id=org.id)
    w.cls = SchoolClass(id=str(uuid.uuid4()), name="Year 10", level="YEAR 10", org_id=org.id)
    db.add_all([w.session, w.term, w.sub, w.cls])
    await db.commit()
    w.pupil = Student(id=str(uuid.uuid4()), student_id="FSN-0001", first_name="Ada",
                      last_name="Obi", class_id=w.cls.id, org_id=org.id)
    db.add(w.pupil)
    await db.commit()
    if with_period:
        db.add(TermPeriod(id=str(uuid.uuid4()), session_id=w.session.id,
                          term_id=w.term.id, sub_term_id=w.sub.id,
                          begin_date=BEGIN, end_date=END, total_days=total_days,
                          org_id=org.id))
        await db.commit()
    return w


async def _mark(db, org, w, n, status, *, start=BEGIN, offset=0):
    """`n` consecutive school days from `start`, offset to avoid colliding with
    an earlier call (one record per pupil per day since migration 136)."""
    for i in range(n):
        db.add(AttendanceRecord(id=str(uuid.uuid4()), student_id=w.pupil.id,
                                class_id=w.cls.id,
                                date=start + timedelta(days=offset + i),
                                status=status, org_id=org.id))
    await db.commit()


async def _author(db, org, w, present, total):
    db.add(StudentReport(id=str(uuid.uuid4()), student_id=w.pupil.id,
                         term_id=w.term.id, session_id=w.session.id,
                         attendance_present=present, attendance_total=total,
                         org_id=org.id))
    await db.commit()


async def _summary(db, org, w):
    return await term_attendance(db, org.id, w.pupil.id, session_id=w.session.id,
                                 term_id=w.term.id, sub_term_id=w.sub.id)


# ── the cliff this exists to prevent ─────────────────────────────────────────

async def test_one_marked_day_does_not_overwrite_the_authored_figure(db, org):
    """THE failure mode. A teacher marks a single day's register; the card must
    still read 50/60, not 1/1."""
    w = await _world(db, org, total_days=60)
    await _author(db, org, w, 50, 60)
    await _mark(db, org, w, 1, AttendanceStatus.PRESENT)

    s = await _summary(db, org, w)
    assert s.source == "authored", "a one-day register is not the term"
    assert (s.present, s.total) == (50, 60)
    assert s.register_days == 1 and s.required_days == 60, (
        "and the partial register must be visible rather than silently ignored")


async def test_a_nearly_complete_register_still_does_not_win(db, org):
    """59 of 60 is still not the term. The threshold is completeness, not
    'mostly'."""
    w = await _world(db, org, total_days=60)
    await _author(db, org, w, 50, 60)
    await _mark(db, org, w, 59, AttendanceStatus.PRESENT)

    s = await _summary(db, org, w)
    assert s.source == "authored" and s.present == 50
    assert s.register_days == 59


async def test_a_complete_register_takes_over(db, org):
    w = await _world(db, org, total_days=10)
    await _author(db, org, w, 5, 10)
    await _mark(db, org, w, 10, AttendanceStatus.PRESENT)

    s = await _summary(db, org, w)
    assert s.source == "register", "complete, so the counted figure wins"
    assert (s.present, s.total, s.absent) == (10, 10, 0)
    assert s.punctual == 10


# ── the status mapping ───────────────────────────────────────────────────────

async def test_late_is_present_but_not_punctual(db, org):
    w = await _world(db, org, total_days=10)
    await _mark(db, org, w, 7, AttendanceStatus.PRESENT)
    await _mark(db, org, w, 3, AttendanceStatus.LATE, offset=7)

    s = await _summary(db, org, w)
    assert s.source == "register"
    assert s.present == 10, "LATE days are still days present"
    assert s.punctual == 7, "but they are not punctual"
    assert s.absent == 0


async def test_excused_is_absent_and_stays_in_the_denominator(db, org):
    """An excused day is not a day present, and dropping it from the
    denominator would quietly inflate the percentage."""
    w = await _world(db, org, total_days=10)
    await _mark(db, org, w, 6, AttendanceStatus.PRESENT)
    await _mark(db, org, w, 2, AttendanceStatus.EXCUSED, offset=6)
    await _mark(db, org, w, 2, AttendanceStatus.ABSENT, offset=8)

    s = await _summary(db, org, w)
    assert s.present == 6
    assert s.total == 10, "the denominator is the configured school days"
    assert s.absent == 4, "EXCUSED and ABSENT both count against presence"
    assert s.punctual == 6


# ── the window ───────────────────────────────────────────────────────────────

async def test_days_outside_the_term_are_not_counted(db, org):
    """The rule this replaces matched AcademicSession.term against a term NAME;
    on production that found nothing for Spring, applied no window, and counted
    a pupil's entire roll-call history as the term's."""
    w = await _world(db, org, total_days=10)
    await _mark(db, org, w, 10, AttendanceStatus.PRESENT)
    # ten more days AFTER the term ends
    await _mark(db, org, w, 10, AttendanceStatus.PRESENT,
                start=END + timedelta(days=1))

    s = await _summary(db, org, w)
    assert s.register_days == 10, "only the term's days"
    assert s.present == 10, "not 20"
    assert s.window_start == BEGIN and s.window_end == END


# ── provenance ───────────────────────────────────────────────────────────────

async def test_no_term_period_means_the_register_can_never_win(db, org):
    """Production's state today: term_periods is empty, so there is no
    denominator and no window. The authored figure stands, which is the safe
    default rather than a special case."""
    w = await _world(db, org, with_period=False)
    await _author(db, org, w, 48, 60)
    await _mark(db, org, w, 60, AttendanceStatus.PRESENT)

    s = await _summary(db, org, w)
    assert s.source == "authored" and (s.present, s.total) == (48, 60)
    assert s.required_days is None and s.register_days == 0


async def test_an_authored_figure_reports_no_punctuality(db, org):
    """Punctuality was only ever counted. Inferring it from `present` would
    assert that nobody was ever late."""
    w = await _world(db, org, total_days=60)
    await _author(db, org, w, 50, 60)
    s = await _summary(db, org, w)
    assert s.source == "authored" and s.punctual is None


async def test_nothing_known_says_nothing(db, org):
    """No register and no authored row: a dash, never '0 of 0'."""
    w = await _world(db, org, total_days=10)
    s = await _summary(db, org, w)
    assert s.source == "none"
    assert s.present is None and s.total is None and s.punctual is None


async def test_a_total_days_of_zero_does_not_satisfy_completeness(db, org):
    """0 >= 0 is true, which would make an empty register 'complete' and report
    0 of 0 as counted fact."""
    w = await _world(db, org, total_days=0)
    await _author(db, org, w, 50, 60)
    s = await _summary(db, org, w)
    assert s.source == "authored", "a zero denominator is not a complete term"


# ── the card ─────────────────────────────────────────────────────────────────

async def test_the_card_reports_the_source(db, org):
    """report_card surfaces provenance, so a typed figure is distinguishable
    from a counted one on the page itself."""
    from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
    from app.models.user import User, UserStatus
    from app.routers.modules.platform import report_card

    w = await _world(db, org, total_days=10)
    await _author(db, org, w, 5, 10)

    role = Role(id=str(uuid.uuid4()), name="org_admin", slug=f"a-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["org_admin"]), org_id=org.id,
                is_system=False)
    admin = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com",
                 full_name="Admin", status=UserStatus.ACTIVE, org_id=org.id)
    admin.roles = [role]
    db.add_all([role, admin])
    await db.commit()

    card = await report_card(student_id=w.pupil.id, term_id=w.term.id,
                             sub_term_id=w.sub.id, db=db, current_user=admin)
    assert card.attendance_source == "authored"
    assert (card.attendance_present, card.attendance_total) == (5, 10)
    assert card.attendance_absent == 5
    assert card.attendance_required_days == 10
