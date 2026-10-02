"""The attendance figures on a report card, and where they come from.

Until now `attendance_present` and `attendance_total` were whatever a teacher
typed into Report Setup, while `attendance_punctual` beside them was COUNTED from
the daily register. Two sources on one card, which can contradict each other —
punctuality could exceed days present and nothing would object.

This derives all three from the register, and falls back to the authored figure
when the register cannot support them.

WHEN THE REGISTER WINS. Only when the term's register is COMPLETE: the number of
distinct days marked reaches `term_periods.total_days`, the denominator an admin
configured for that (session, term, sub-term).

The obvious alternative — derive as soon as ANY daily record exists — is a trap.
The first teacher to mark a single day's register would flip that pupil from
50/60 to 1/1, on a parent-facing card, with no error and no way to notice. One
click would destroy 180 authored figures. So a half-kept register never
overrides a real one, and `register_days` / `required_days` ride along on the
result so a partial register is VISIBLE rather than inferred from a number that
looks plausible.

Because `term_periods` is empty on production today, every card falls back to
the authored figure until an admin sets a denominator. That is the safe default
rather than a special case.

THE STATUS MAPPING, which is not self-evident from four enum values:

    PRESENT   present, and punctual
    LATE      present, NOT punctual
    ABSENT    absent
    EXCUSED   absent, but still a school day in the denominator

`punctual` counts PRESENT alone, which is exactly what `report_card` counted
before this service existed — so the derived figure cannot disagree with the one
already printed. EXCUSED is the conservative reading: the pupil was not there,
and dropping those days from the denominator would quietly inflate the
percentage. `AbsenceReason.is_authorized` exists if an authorized/unauthorized
split is ever wanted; it deliberately does not move the headline figure.

THE WINDOW comes from `term_periods.begin_date` / `end_date`.

It used to come from `AcademicSession.term == term_name` — a NAME match against
the session's double-duty `term` column. Production holds
`academic_sessions.term = 'Autumn'`, so on a Spring or Summer card that match
found nothing, no window was applied, and the punctuality count silently spanned
the pupil's ENTIRE roll-call history instead of the term's. The 2026/2027 session
carries `term = NULL` and would never have matched at all. Both window rules are
replaced by this one, because two rules in one function is how they drift.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class AttendanceSummary:
    """A pupil's attendance for one (session, term, sub-term), and its provenance."""
    present: int | None = None
    total: int | None = None
    absent: int | None = None
    punctual: int | None = None
    # "register"  — counted from the daily roll-call, which is complete
    # "authored"  — the figure a teacher typed, because the register is not
    # "none"      — neither exists; the card shows a dash, never a zero
    source: str = "none"
    # Carried so a partial register is visible on its own terms. A figure that
    # rests on 12 of 60 days is not the term, and the two are indistinguishable
    # once reduced to "present: 12".
    register_days: int = 0
    required_days: int | None = None
    window_start: date | None = None
    window_end: date | None = None


async def term_attendance(
    db: AsyncSession,
    org_id: str,
    student_id: str,
    *,
    session_id: str | None,
    term_id: str | None,
    sub_term_id: str | None = None,
) -> AttendanceSummary:
    """Attendance for one pupil in one (session, term), register-first.

    Returns `source="none"` rather than zeros when nothing is known. A card
    showing "0 of 0 days" asserts a fact nobody recorded.
    """
    from app.models.modules.platform import TermPeriod
    from app.models.modules.school import AttendanceRecord, AttendanceStatus, StudentReport

    out = AttendanceSummary()

    # ── the authored fallback, loaded first so it is available either way ────
    authored = None
    if session_id and term_id:
        authored = (await db.execute(select(StudentReport).where(
            StudentReport.org_id == org_id,
            StudentReport.student_id == student_id,
            StudentReport.session_id == session_id,
            StudentReport.term_id == term_id,
        ))).scalars().first()

    # ── the configured window and denominator ───────────────────────────────
    period = None
    if session_id and term_id:
        q = select(TermPeriod).where(
            TermPeriod.org_id == org_id,
            TermPeriod.session_id == session_id,
            TermPeriod.term_id == term_id,
        )
        if sub_term_id:
            q = q.where(TermPeriod.sub_term_id == sub_term_id)
        period = (await db.execute(q)).scalars().first()

    if period:
        out.required_days = period.total_days
        out.window_start, out.window_end = period.begin_date, period.end_date

    # ── count the register within the window ────────────────────────────────
    counted = {}
    if period and period.begin_date and period.end_date:
        rows = (await db.execute(
            select(AttendanceRecord.status, func.count(AttendanceRecord.id))
            .where(AttendanceRecord.org_id == org_id,
                   AttendanceRecord.student_id == student_id,
                   AttendanceRecord.date >= period.begin_date,
                   AttendanceRecord.date <= period.end_date)
            .group_by(AttendanceRecord.status)
        )).all()
        counted = {status: n for status, n in rows}
        # Distinct DAYS, not rows. Equal since migration 136, and counted this
        # way so the completeness test cannot be satisfied by duplicates if that
        # constraint is ever relaxed.
        out.register_days = (await db.execute(
            select(func.count(func.distinct(AttendanceRecord.date)))
            .where(AttendanceRecord.org_id == org_id,
                   AttendanceRecord.student_id == student_id,
                   AttendanceRecord.date >= period.begin_date,
                   AttendanceRecord.date <= period.end_date)
        )).scalar() or 0

    def _n(status) -> int:
        return int(counted.get(status, 0) or 0)

    complete = bool(
        out.required_days and out.register_days >= out.required_days)

    if complete:
        # PRESENT + LATE are both present; LATE is simply not punctual.
        out.present = _n(AttendanceStatus.PRESENT) + _n(AttendanceStatus.LATE)
        out.punctual = _n(AttendanceStatus.PRESENT)
        out.total = out.required_days
        out.absent = max(out.total - out.present, 0)
        out.source = "register"
        return out

    if authored and authored.attendance_present is not None \
            and authored.attendance_total is not None:
        out.present = authored.attendance_present
        out.total = authored.attendance_total
        out.absent = max(out.total - out.present, 0)
        # Punctuality has no authored equivalent — it was only ever counted. It
        # stays None rather than being guessed from `present`, which would
        # assert that nobody was ever late.
        out.punctual = None
        out.source = "authored"
        return out

    return out
