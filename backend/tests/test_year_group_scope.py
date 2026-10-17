"""Report columns scoped to a year group.

~~~ WHAT THIS UNLOCKS, AND WHAT IT RISKS ~~~
`assessments` and `cumulatives` have carried a `year_group` since they were
created (NULL = all levels), but `load_term_setup` filtered on (session, term)
ONLY. So every configured column was visible at every level, and Educare's two
column sets could not coexist: Junior prints CA 1 / PRJ / C.E / Exam while
Secondary prints CA 1 / CA 2 / Exam. Adding Secondary's CA 2 would have put it on
a Year 2 card.

THE RISK IS THE FILTER'S SHAPE, not the feature. Production holds 4 assessments
and 5 cumulatives, every one of them UNSCOPED — measured twice, against the
head-138 dump and against the live database. So:

    year_group IS NULL OR lower(year_group) = lower(level)   -> nothing changes
    year_group = level                                        -> EVERY column on
                                                                 EVERY card in the
                                                                 school disappears

`test_the_production_shape_is_unchanged` is that regression lock, and it is the
most important test in this file.

~~~ THE CASE TRAP ~~~
`school_classes.level` holds 'Year 7' (title case, all 31 production classes).
The documented and seeded form of `year_group` is 'YEAR 7' (upper). A
case-sensitive comparison in PostgreSQL matches NEITHER direction, which would
blank the card while looking like a filtering bug rather than a collation one.
`test_case_does_not_matter` fails if the fold is ever dropped.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, Assessment, Cumulative, CumulativeComponent,
)
from app.services.session_scope import load_term_setup

pytestmark = pytest.mark.asyncio


class World:
    pass


@pytest_asyncio.fixture
async def w(db, org, session) -> World:
    """One session, one term, two sub-terms. Columns are added per test."""
    x = World()
    x.org, x.session = org, session
    x.term = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    x.full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    x.half = AcademicSubTerm(id=str(uuid.uuid4()), name="Half-Term", position=1, org_id=org.id)
    db.add_all([x.term, x.full, x.half])
    await db.commit()

    async def assessment(name, year_group=None, sub=None, max_score=100):
        a = Assessment(id=str(uuid.uuid4()), name=name, max_score=max_score,
                       session_id=x.session.id, term_id=x.term.id,
                       sub_term_id=(sub or x.full).id, year_group=year_group,
                       org_id=org.id)
        db.add(a)
        await db.commit()
        return a

    async def cumulative(name, year_group=None, sub=None, components=()):
        c = Cumulative(id=str(uuid.uuid4()), name=name, session_id=x.session.id,
                       term_id=x.term.id, sub_term_id=(sub or x.full).id,
                       year_group=year_group, cumul_type="score", org_id=org.id)
        db.add(c)
        await db.commit()
        for i, a in enumerate(components):
            db.add(CumulativeComponent(id=str(uuid.uuid4()), org_id=org.id,
                                       cumulative_id=c.id, ref_type="assessment",
                                       ref_id=a.id, position=i))
        await db.commit()
        return c

    x.assessment, x.cumulative = assessment, cumulative
    return x


async def _setup(db, w, **kw):
    return await load_term_setup(db, w.org.id, w.session.id, w.term.id, **kw)


def _names(setup):
    return ({a.name for a in setup.assessments.values()},
            {c.name for c in setup.cumulatives})


# ── the regression lock ──────────────────────────────────────────────────────

async def test_the_production_shape_is_unchanged(db, w):
    """Production's 9 rows are all unscoped, so they must be visible at EVERY
    level. If this fails, shipping the filter blanks every card in the school."""
    await w.assessment("Continuous Assessment", max_score=40)
    await w.assessment("CBT Exam Score")
    await w.cumulative("CA")
    await w.cumulative("Exam")
    await w.cumulative("TOTAL")

    unfiltered = _names(await _setup(db, w))
    assert unfiltered == ({"Continuous Assessment", "CBT Exam Score"},
                          {"CA", "Exam", "TOTAL"})

    for level in ("Year 7", "Year 2", "Reception", "Playgroup"):
        assert _names(await _setup(db, w, level=level)) == unfiltered, (
            f"an unscoped column vanished at level {level!r} — this is the "
            f"strict-equality mistake, and it empties every card"
        )


async def test_omitting_the_level_does_not_filter(db, w):
    """Whole-school callers — `report_insight`, and `analyse_term` with neither
    class nor section — have no level to scope by, and must keep seeing
    everything. The parameter's absence is a THIRD state, distinct from
    `level=None`."""
    await w.assessment("All Levels")
    await w.assessment("Year 7 Only", year_group="YEAR 7")
    asmts, _ = _names(await _setup(db, w))
    assert asmts == {"All Levels", "Year 7 Only"}


# ── scoping ──────────────────────────────────────────────────────────────────

async def test_a_scoped_column_appears_only_at_its_own_level(db, w):
    await w.assessment("CA 2", year_group="YEAR 7")

    assert _names(await _setup(db, w, level="Year 7"))[0] == {"CA 2"}
    assert _names(await _setup(db, w, level="Year 6"))[0] == set(), (
        "a Secondary column reached a Primary card — the thing this phase exists "
        "to prevent"
    )


async def test_case_does_not_matter(db, w):
    """THE COLLATION TRAP. Config is seeded 'YEAR 7'; every production class row
    holds 'Year 7'. A case-sensitive comparison matches neither way round."""
    await w.assessment("CA 2", year_group="YEAR 7")
    assert _names(await _setup(db, w, level="Year 7"))[0] == {"CA 2"}
    assert _names(await _setup(db, w, level="year 7"))[0] == {"CA 2"}
    assert _names(await _setup(db, w, level="YEAR 7"))[0] == {"CA 2"}


async def test_unscoped_and_scoped_columns_coexist(db, w):
    """Educare's real shape: shared components plus one per-level extra."""
    await w.assessment("CA 1")                               # both levels
    await w.assessment("Exam")                               # both levels
    await w.assessment("C.E", year_group="YEAR 6")           # Junior only
    await w.assessment("CA 2", year_group="YEAR 7")          # Secondary only

    assert _names(await _setup(db, w, level="Year 6"))[0] == {"CA 1", "Exam", "C.E"}
    assert _names(await _setup(db, w, level="Year 7"))[0] == {"CA 1", "Exam", "CA 2"}


async def test_a_class_with_no_level_sees_only_the_shared_columns(db, w):
    """`level=None` means the class carries no level, so no year group can be
    matched. The honest answer is the columns that apply to all levels — not
    every level's columns at once, which would mix Junior's C.E into a card that
    cannot say it is Junior."""
    await w.assessment("CA 1")
    await w.assessment("CA 2", year_group="YEAR 7")
    assert _names(await _setup(db, w, level=None))[0] == {"CA 1"}


async def test_an_unknown_level_still_gets_the_shared_columns(db, w):
    """A level that matches no configured year group — 'Playgroup' against a
    Secondary-only config. The card must fall back to the shared columns rather
    than coming back empty and reading as "not set up"."""
    await w.assessment("CA 1")
    await w.assessment("CA 2", year_group="YEAR 7")
    assert _names(await _setup(db, w, level="Playgroup"))[0] == {"CA 1"}


# ── the display column must not cross levels ────────────────────────────────

async def test_display_cumulative_does_not_cross_year_groups(db, w):
    """`_pick_display_cumulative` prefers a cumulative named TOTAL and otherwise
    falls back by position. Fed a scoped set it can only ever see this level's,
    so a Year 10 TOTAL cannot become a Year 6 card's display column."""
    from app.routers.modules.platform import _pick_display_cumulative

    await w.cumulative("TOTAL", year_group="YEAR 10")

    senior = await _setup(db, w, level="Year 10")
    junior = await _setup(db, w, level="Year 6")

    assert _pick_display_cumulative(senior.cumulatives, w.full.id) is not None
    assert _pick_display_cumulative(junior.cumulatives, w.full.id) is None, (
        "the Year 10 TOTAL became the display column for a Year 6 class"
    )


async def test_components_still_resolve_for_a_scoped_cumulative(db, w):
    """The component map is scoped to the cumulatives loaded. Narrowing by year
    group must not strand a surviving cumulative's components — that is the
    failure recorded in session_scope.py, where scoping the map emptied the
    Sessional Score with no error."""
    ca = await w.assessment("CA 1", year_group="YEAR 7")
    exam = await w.assessment("Exam", year_group="YEAR 7")
    total = await w.cumulative("TOTAL", year_group="YEAR 7", components=(ca, exam))

    setup = await _setup(db, w, level="Year 7")
    assert setup.components.get(total.id) == [
        ("assessment", ca.id), ("assessment", exam.id)]


async def test_scoping_out_a_cumulative_drops_its_components_too(db, w):
    """The mirror: a cumulative filtered away must not leave its components in
    the map, or the evaluator could resolve a tree whose root is not on the
    card."""
    ca = await w.assessment("CA 2", year_group="YEAR 7")
    total = await w.cumulative("TOTAL", year_group="YEAR 7", components=(ca,))

    setup = await _setup(db, w, level="Year 6")
    assert setup.cumulatives == []
    assert total.id not in setup.components


# ── interaction with the existing filters ───────────────────────────────────

async def test_the_session_filter_still_applies(db, w, org):
    """Year-group scoping is ADDITIONAL. A row from another session must stay
    invisible however the levels line up — mixing two years of marks is the
    failure migration 134 exists to prevent, and it does not raise."""
    from app.models.modules.platform import AcademicSession

    other = AcademicSession(id=str(uuid.uuid4()), name="2024/2025", org_id=org.id)
    db.add(other)
    await db.commit()
    db.add(Assessment(id=str(uuid.uuid4()), name="Last Year", max_score=100,
                      session_id=other.id, term_id=w.term.id,
                      sub_term_id=w.full.id, year_group="YEAR 7", org_id=org.id))
    await db.commit()

    assert _names(await _setup(db, w, level="Year 7"))[0] == set()


async def test_no_session_still_returns_empty(db, w):
    """`session_id` of None cannot select any row, and must not be widened into
    "every year at once" by the new parameter."""
    setup = await load_term_setup(db, w.org.id, None, w.term.id, level="Year 7")
    assert setup.assessments == {} and setup.cumulatives == []
