"""Which academic session a request is working in, and the setup for it.

Migration 134 gave `assessments` and `cumulatives` a `session_id`, because terms
are org-wide and shared across years: "Autumn" is one row in `academic_terms`,
reused every session. Everything that reads report setup therefore has to say
WHICH year it means, and there were 34 places doing that read.

TWO THINGS LIVE HERE.

`resolve_session_id` answers "which year, when nobody said". Sessioning is
EXPLICIT — every report endpoint takes an optional `session_id` and falls back to
this — because the whole point of keeping the year on the row is that last year
stays reachable. An implicit current-session-only rule would make a 2025/2026
card unprintable the moment 2026/2027 began, and a school needs those for
transcripts, appeals and leaver references.

`load_term_setup` is the read itself. Five functions — `analyse_term`,
`component_coverage`, `report_broadsheet`, `report_card` and `report_insight` —
each had their own near-identical copy of this block. Five copies meant five
places to add the session filter and five chances to miss one, and a missed one
does not raise: it silently mixes two years of marks. One loader, one filter.

It also fixes a wart the copies shared: they all loaded `CumulativeComponent`
ORG-WIDE and unscoped. Harmless while one year existed — the map is keyed by
cumulative_id, so foreign entries were simply never looked up — but it would have
grown every past year's components into every card render. Scoped to the
cumulatives actually loaded.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


# ── which session ────────────────────────────────────────────────────────────

async def resolve_session_id(db: AsyncSession, org_id: str) -> str | None:
    """The session to use when a request did not name one.

    Current first, then the only session when exactly one exists, then None.
    Deliberately the same preference order as
    `subject_enrollment.resolve_academic_year`, so this column and the session
    STRING that enrolment has been keyed on since migration 128 cannot disagree
    about which year it is.

    Returns None rather than raising: the readers below turn that into an
    explicit "not configured" answer, which a report can render honestly. The
    write paths are the ones that must insist on a concrete year, and they do,
    via the NOT NULL column.
    """
    from app.models.modules.platform import AcademicSession

    cur = (await db.execute(
        select(AcademicSession.id).where(
            AcademicSession.org_id == org_id,
            AcademicSession.is_current == True,  # noqa: E712
        )
    )).scalars().first()
    if cur:
        return cur

    rows = (await db.execute(
        select(AcademicSession.id).where(AcademicSession.org_id == org_id)
    )).scalars().all()
    return rows[0] if len(rows) == 1 else None


async def session_or_current(db: AsyncSession, org_id: str,
                             session_id: str | None) -> str | None:
    """A caller-supplied session, validated, else the current one.

    An id that is not a session of this org resolves to None rather than being
    trusted — a report must not be assembled from another tenant's setup because
    a query string said so.
    """
    if not session_id:
        return await resolve_session_id(db, org_id)

    from app.models.modules.platform import AcademicSession

    ok = (await db.execute(select(AcademicSession.id).where(
        AcademicSession.id == session_id, AcademicSession.org_id == org_id,
    ))).scalars().first()
    return ok or None


# ── the setup for one (session, term) ────────────────────────────────────────

@dataclass
class TermSetup:
    """Report setup for one (session, term): the four things every reader needs."""
    assessments: dict = field(default_factory=dict)      # id -> Assessment
    cumulatives: list = field(default_factory=list)      # ordered Cumulative rows
    cumul_by_id: dict = field(default_factory=dict)      # id -> Cumulative
    components: dict = field(default_factory=dict)       # cumulative_id -> [(ref_type, ref_id)]

    # Deliberately NO `configured` convenience. The real test each caller makes
    # is `not display or not assessments`, and `display` comes from
    # `_pick_display_cumulative(cumulatives, sub_term_id)`, which can be None
    # even when `cumulatives` is non-empty — no column matches that sub-term. A
    # property that looked like the check but was subtly weaker would eventually
    # get used instead of it, and the failure would be a card full of F grades.


async def load_session_setup(db: AsyncSession, org_id: str,
                             session_id: str | None) -> TermSetup:
    """Every term's setup for one session — no term filter.

    For the card's Sessional Score, which averages a pupil's terms into a yearly
    figure and therefore has to resolve cumulative trees across ALL of the
    session's terms, not just the one being viewed.

    This exists because consolidating the loaders broke it. The old copies read
    `CumulativeComponent` ORG-WIDE, so the sessional block silently relied on
    that breadth to resolve other terms' components; scoping the map to the
    viewed term made `evaluate_cumulative` find no components for the other
    terms and the Sessional Score came back empty — with no error, just a
    missing number on a report card. The breadth it needs is "this session",
    which is a thing worth naming rather than inheriting by accident.
    """
    return await _load(db, org_id, session_id, term_id=None)


async def load_term_setup(db: AsyncSession, org_id: str, session_id: str | None,
                          term_id: str) -> TermSetup:
    """Assessments, cumulatives and their components for one (session, term).

    `session_id` of None means no session could be resolved, which cannot select
    any row now that the column is NOT NULL — so it returns empty rather than
    quietly falling back to every year at once.
    """
    return await _load(db, org_id, session_id, term_id=term_id)


async def _load(db: AsyncSession, org_id: str, session_id: str | None,
                term_id: str | None) -> TermSetup:
    """The shared read. `term_id` of None means every term of the session."""
    from app.models.modules.platform import Assessment, Cumulative, CumulativeComponent

    if not session_id:
        return TermSetup()

    a_where = [Assessment.org_id == org_id, Assessment.session_id == session_id]
    c_where = [Cumulative.org_id == org_id, Cumulative.session_id == session_id]
    if term_id is not None:
        a_where.append(Assessment.term_id == term_id)
        c_where.append(Cumulative.term_id == term_id)

    assessments = {a.id: a for a in (await db.execute(
        select(Assessment).where(*a_where))).scalars().all()}

    cumulatives = (await db.execute(select(Cumulative).where(*c_where)
                   .order_by(Cumulative.position, Cumulative.name))).scalars().all()

    setup = TermSetup(assessments=assessments, cumulatives=list(cumulatives),
                      cumul_by_id={c.id: c for c in cumulatives})

    # Scoped to the cumulatives just loaded. A cumulative can reference ANOTHER
    # cumulative, and the evaluator walks that tree, so the map has to cover the
    # whole set it was given — but no other year's.
    if setup.cumul_by_id:
        for cr in (await db.execute(select(CumulativeComponent).where(
                CumulativeComponent.org_id == org_id,
                CumulativeComponent.cumulative_id.in_(list(setup.cumul_by_id)),
        ).order_by(CumulativeComponent.position))).scalars().all():
            setup.components.setdefault(cr.cumulative_id, []).append(
                (cr.ref_type, cr.ref_id))

    return setup
