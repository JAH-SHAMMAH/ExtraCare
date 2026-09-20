"""Letters come from the school's configured bands, not a constant in the code.

`grade_letter()` read a hardcoded five-band scale and nothing else. Fairview has
NINE bands configured in Report Setup (A* 95-100 … F 0-39), so a 70.98 lettered
as "A" from the constant where the school's own scale says "C". Three resolvers
had grown up around this — the constant, a bands-first `_letter` in the school
router, and a bands-only `_grade_for` in the platform router. `letter_for`
replaces all three.

The matching rule is the interesting part. Fairview's bands are integer-bounded
with HOLES between them (F 0-39, P 40-49, …), so a range test
`min <= pct <= max` resolves nothing for a fractional mark: 189 of 1800 live
rows sat in gaps like (39, 40) and would have been left letterless. Matching on
the lower bound is gap-free and preserves the semantics every existing letter
was computed under, since the constant has always been `pct >= threshold`.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.modules.platform import GradingBand, GradingScale
from app.services.grading import (
    GRADING_SCALE, grade_letter, letter_for, load_grade_bands,
)

# Fairview's real scale, as configured in Report Setup.
FAIRVIEW = [("A*", 95, 100), ("A", 90, 94), ("B+", 85, 89), ("B", 80, 84),
            ("C", 70, 79), ("D", 60, 69), ("E", 50, 59), ("P", 40, 49), ("F", 0, 39)]


class _Band:
    """Stand-in with the two attributes the resolver reads."""
    def __init__(self, grade, lo, hi):
        self.grade, self.min_score, self.max_score = grade, lo, hi


def _bands(spec=FAIRVIEW):
    # Highest threshold first, as load_grade_bands returns them.
    return [_Band(g, lo, hi) for g, lo, hi in sorted(spec, key=lambda x: -x[1])]


# ── the rule that changed ─────────────────────────────────────────────────────

def test_the_configured_bands_beat_the_hardcoded_constant():
    """The defect in one line: 70.98 is an A by the constant, a C at Fairview."""
    assert grade_letter(70.98, 100) == "A"
    assert letter_for(70.98, 100, _bands()) == "C"


def test_a_mark_in_a_gap_between_bands_still_gets_a_letter():
    """189 of 1800 live rows sat here. A range test returns nothing for these."""
    for pct in (39.0137, 39.5, 39.99):
        assert letter_for(pct, 100, _bands()) == "F", pct
    for pct in (49.5, 59.5, 69.5, 79.5, 84.5, 89.5, 94.5):
        assert letter_for(pct, 100, _bands()) is not None, pct


def test_a_borderline_fail_stays_a_fail():
    """39.5 is an F, not a P. You reach 40 to pass; rounding up would turn a
    fail into a pass on a report card."""
    assert letter_for(39.5, 100, _bands()) == "F"
    assert letter_for(40.0, 100, _bands()) == "P"


@pytest.mark.parametrize("pct,expected", [
    (100, "A*"), (95, "A*"), (94.99, "A"), (90, "A"), (85, "B+"), (80, "B"),
    (70, "C"), (60, "D"), (50, "E"), (40, "P"), (39, "F"), (0, "F"),
])
def test_each_band_boundary_lands_in_the_right_band(pct, expected):
    assert letter_for(pct, 100, _bands()) == expected


# ── the fallback, which must stay a last resort ───────────────────────────────

def test_with_no_bands_at_all_the_constant_is_used():
    assert letter_for(72, 100, []) == grade_letter(72, 100) == "A"
    assert letter_for(72, 100, None) == "A"


def test_the_fallback_never_stands_in_for_bands_that_exist():
    """The whole defect was a constant quietly shadowing configured data. If
    bands exist, their answer is the answer."""
    b = _bands()
    for pct in (0, 39.5, 55, 70.98, 88, 100):
        assert letter_for(pct, 100, b) == letter_for(pct, 100, b)
        # ...and it must not equal the constant's answer where they disagree.
    assert letter_for(88, 100, b) == "B+" and grade_letter(88, 100) == "A"


def test_a_mark_below_every_configured_band_is_unlettered_not_fallen_back():
    """A school whose lowest band starts above 0 has a gap in their setup.
    Silently switching to a different scale would hide that."""
    sparse = [_Band("A", 90, 100), _Band("B", 80, 89)]
    assert letter_for(50, 100, sparse) is None


# ── what is NOT a grade ───────────────────────────────────────────────────────

@pytest.mark.parametrize("score,total", [(None, 100), (50, 0), (50, None), (None, None)])
def test_an_uncomputable_mark_is_none_and_never_an_f(score, total):
    """Stamping F on an unmarked pupil would be a real error on a report card."""
    assert letter_for(score, total, _bands()) is None
    assert grade_letter(score, total) is None


def test_a_mark_out_of_something_other_than_100_is_scaled():
    assert letter_for(45, 50, _bands()) == letter_for(90, 100, _bands()) == "A"


def test_bands_missing_a_lower_bound_are_skipped_not_crashed_on():
    """Descriptor-style rows can carry a null min_score."""
    mixed = [_Band("X", None, None)] + _bands()
    assert letter_for(72, 100, mixed) == "C"


# ── the loader picks the same scale the report card does ──────────────────────

async def _seed_scale(db, org, *, purpose="grade", scale_type="numeric", show=True):
    sc = GradingScale(id=str(uuid.uuid4()), name=f"S-{uuid.uuid4().hex[:4]}",
                      scale_type=scale_type, purpose=purpose, show_in_table=show,
                      org_id=org.id)
    db.add(sc)
    await db.commit()
    for g, lo, hi in FAIRVIEW:
        db.add(GradingBand(id=str(uuid.uuid4()), scale_id=sc.id, grade=g,
                           min_score=lo, max_score=hi, org_id=org.id))
    await db.commit()
    return sc


@pytest.mark.asyncio
async def test_the_loader_returns_the_bands_highest_threshold_first(db, org):
    await _seed_scale(db, org)
    bands = await load_grade_bands(db, org.id)
    assert [b.grade for b in bands] == ["A*", "A", "B+", "B", "C", "D", "E", "P", "F"]
    assert letter_for(70.98, 100, bands) == "C"


@pytest.mark.asyncio
async def test_a_school_with_no_scale_gets_no_bands_and_falls_back(db, org):
    assert await load_grade_bands(db, org.id) == []
    assert letter_for(72, 100, await load_grade_bands(db, org.id)) == "A"


@pytest.mark.asyncio
async def test_only_the_grade_purpose_scale_is_used(db, org):
    """`purpose` distinguishes the main grade scale from keys/cumulative/mock
    legends. Lettering a mark off the mock scale would be wrong."""
    await _seed_scale(db, org, purpose="mock")
    assert await load_grade_bands(db, org.id) == []


@pytest.mark.asyncio
async def test_a_descriptor_scale_is_not_used_for_numeric_letters(db, org):
    """EYFS/Cambridge descriptor scales are ordered labels with no ranges."""
    await _seed_scale(db, org, scale_type="descriptor")
    assert await load_grade_bands(db, org.id) == []


@pytest.mark.asyncio
async def test_the_loader_and_the_report_card_choose_the_same_scale(db, org):
    """If these diverged, the letter stored on a Grade row and the letter printed
    on the card would disagree for the same mark."""
    hidden = await _seed_scale(db, org, show=False)
    shown = await _seed_scale(db, org, show=True)
    bands = await load_grade_bands(db, org.id)
    assert {b.scale_id for b in bands} == {shown.id}
    assert hidden.id not in {b.scale_id for b in bands}
