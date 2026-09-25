"""Step 3: the Sessional Score, and the band-gap fix it depends on.

Two things are covered here, and they are related. `sessional_average` is the
unweighted mean of a session's per-term averages. `_grade_for` is what turns any
such percentage into a letter, and it used to range-match, which returns NO
grade for a mark that falls in a gap between two bands. Fairview's bands have
exactly those gaps, so introducing a cumulative -- which is what makes
percentages fractional -- would have exposed it immediately.
"""
from decimal import Decimal

import pytest

from app.routers.modules.platform import _grade_for
from app.services.report_engine import sessional_average


class _Band:
    def __init__(self, grade, lo, hi):
        self.grade, self.min_score, self.max_score = grade, Decimal(str(lo)), Decimal(str(hi))
        self.remark = None


# Fairview's real nine, integer-bounded WITH the holes between them.
FAIRVIEW = [
    _Band("A*", 95, 100), _Band("A", 90, 94), _Band("B+", 85, 89),
    _Band("B", 80, 84), _Band("C", 70, 79), _Band("D", 60, 69),
    _Band("E", 50, 59), _Band("P", 40, 49), _Band("F", 0, 39),
]


# ── sessional_average ────────────────────────────────────────────────────────

def test_mean_of_three_terms_is_unweighted():
    val, n = sessional_average([Decimal("60"), Decimal("70"), Decimal("80")])
    assert val == Decimal("70")
    assert n == 3


def test_a_term_without_marks_is_skipped_not_counted_as_zero():
    """The whole point of the (value, counted) pair. Averaging None in as 0
    would halve a pupil's score because the school year is not over yet."""
    val, n = sessional_average([Decimal("60"), None, Decimal("80")])
    assert val == Decimal("70"), "the empty term must not drag the mean down"
    assert n == 2
    assert val != Decimal("140") / 3


def test_no_terms_at_all_is_none_not_zero():
    val, n = sessional_average([None, None, None])
    assert val is None
    assert n == 0


def test_empty_input():
    assert sessional_average([]) == (None, 0)


def test_terms_weigh_equally_regardless_of_subject_count():
    """A mean of per-term averages, not of every subject across the session.
    A term with more subjects must not pull the session score toward itself."""
    busy_term = Decimal("50")     # imagine 10 subjects
    light_term = Decimal("90")    # imagine 2
    val, _ = sessional_average([busy_term, light_term])
    assert val == Decimal("70")


def test_accepts_floats_and_ints():
    val, n = sessional_average([60, 70.0, Decimal("80")])
    assert val == Decimal("70")
    assert n == 3


# ── _grade_for: the gap bug ──────────────────────────────────────────────────

@pytest.mark.parametrize("pct,expected", [
    (100, "A*"), (95, "A*"), (94, "A"), (90, "A"),
    (85, "B+"), (80, "B"), (70, "C"), (60, "D"), (50, "E"), (40, "P"),
    (39, "F"), (0, "F"),
])
def test_exact_band_edges(pct, expected):
    assert _grade_for(Decimal(str(pct)), FAIRVIEW) == expected


@pytest.mark.parametrize("pct,expected", [
    (Decimal("94.5"), "A"),    # between A (…94) and A* (95…)
    (Decimal("39.5"), "F"),    # between F (…39) and P (40…) — must NOT pass
    (Decimal("49.9"), "P"),
    (Decimal("69.99"), "D"),
    (Decimal("84.5"), "B"),
])
def test_marks_in_the_gaps_still_grade(pct, expected):
    """These are what range-matching returned None for. A card printing a blank
    grade for 39.5 is the bug; 39.5 is an F because you reach 40 to pass."""
    assert _grade_for(pct, FAIRVIEW) == expected


def test_zero_is_f_not_none():
    """The status quo the fix must not regress: with no cumulative configured
    every pct is 0, and 0 is a legitimate F rather than an absent grade."""
    assert _grade_for(Decimal("0"), FAIRVIEW) == "F"


def test_no_bands_configured_falls_back_rather_than_crashing():
    assert _grade_for(Decimal("75"), []) == "A"   # last-resort GRADING_SCALE


def test_band_order_does_not_matter():
    """The caller sorts by -max_score; _grade_for must not depend on that
    happening to coincide with min_score order."""
    shuffled = [FAIRVIEW[4], FAIRVIEW[0], FAIRVIEW[8], FAIRVIEW[2]]
    assert _grade_for(Decimal("96"), shuffled) == "A*"
    assert _grade_for(Decimal("72"), shuffled) == "C"
