"""Letter grades — one resolver, reading the school's configured bands.

The authority is `grading_bands`, configured in Report Setup. GRADING_SCALE
below is a LAST-RESORT fallback for a school that has configured none at all;
it is not the scheme, and it must never quietly stand in for one that exists.

That distinction was not always honoured. `grade_letter()` read the constant and
nothing else, so at Fairview — nine configured bands (A* 95-100 … F 0-39) — a
70.98 lettered as "A" from the constant where the school's own scale says "C".
Three different resolvers had grown up around this: the constant here, a
bands-first `_letter` in the school router, and a bands-only `_grade_for` in the
platform router. `letter_for` replaces all three.

MATCHING IS BY LOWER BOUND, not by range, and that is load-bearing. Fairview's
bands are integer-bounded with holes between them (F 0-39, P 40-49, …), so a
range test `min <= pct <= max` resolves nothing for a fractional mark: 189 of
1800 live rows sat in gaps like (39, 40). Taking the highest band whose
`min_score` the mark reaches is gap-free, treats a band list as the ladder of
thresholds it reads as, and preserves the semantics every existing letter was
computed under (the constant has always been `pct >= threshold`).

It also means a borderline 39.5 is an F, not a P. That is deliberate: you reach
40 to pass, and rounding it up would turn a fail into a pass.
"""
from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Last-resort only: used when a school has configured NO bands.
GRADING_SCALE = [(70, "A"), (60, "B"), (50, "C"), (45, "D"), (40, "E")]  # else "F"


async def load_grade_bands(db: AsyncSession, org_id: str) -> list[Any]:
    """The org's numeric grade bands, highest threshold first.

    Loaded ONCE per operation and passed into `letter_for`, never fetched per
    mark: the CBT feed and the exam-results path both letter a whole class in a
    loop, and a query inside that loop is an N+1 over every pupil.

    Picks the same scale the report card does — numeric, purpose 'grade',
    preferring one shown in the report table — so the letter stored on a Grade
    row and the letter printed on the card cannot disagree.
    """
    from app.models.modules.platform import GradingBand, GradingScale

    scale = (await db.execute(
        select(GradingScale)
        .where(
            GradingScale.org_id == org_id,
            GradingScale.scale_type == "numeric",
            GradingScale.purpose == "grade",
        )
        .order_by(GradingScale.show_in_table.desc())
    )).scalars().first()
    if not scale:
        return []

    bands = (await db.execute(
        select(GradingBand).where(
            GradingBand.scale_id == scale.id, GradingBand.org_id == org_id
        )
    )).scalars().all()
    # Highest lower bound first, so the first match is the best band earned.
    return sorted(bands, key=lambda b: float(b.min_score or 0), reverse=True)


def letter_for(
    score: float | None,
    total: float | None,
    bands: Sequence[Any] | None = None,
) -> str | None:
    """Letter for score/total against `bands`, else the fallback scale.

    Returns None when the mark cannot be computed — no score, or a total of
    zero. A missing mark is not an F; it is the absence of one, and stamping F
    on an unmarked pupil would be a real error on a report card.
    """
    if score is None or not total or float(total) <= 0:
        return None
    pct = (float(score) / float(total)) * 100

    if bands:
        for b in bands:
            if b.min_score is None:
                continue
            if pct >= float(b.min_score):
                return b.grade
        # Below every configured band. Only reachable if the school's lowest
        # band starts above 0, which is a gap in their setup rather than
        # something to paper over with the fallback scale.
        return None

    for threshold, letter in GRADING_SCALE:
        if pct >= threshold:
            return letter
    return "F"


def grade_letter(score: float | None, total: float | None) -> str | None:
    """Fallback-only letter. DEPRECATED — prefer `letter_for` with real bands.

    Kept so callers that genuinely have no database session still work, and so
    the fallback behaviour stays covered by tests. Every path that CAN load
    bands should, or it will contradict the school's own grading scale.
    """
    return letter_for(score, total, None)
