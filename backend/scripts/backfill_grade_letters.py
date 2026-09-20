"""Backfill `grade_letter` and round `score` on existing Grade rows.

Both defects come from one cause. `bootstrap_secondary_cbt_feed_gradebook.py`
reimplemented the CBT gradebook feed and drifted from it, writing 1800 rows with
raw unrounded floats and no letter at all. Parents saw "62.70341089190804 / 100"
and a blank Grade column. The script now delegates to the real feed, so new rows
are correct; these are the rows it already wrote.

Letters come from the school's CONFIGURED bands via `letter_for`, not the
hardcoded fallback - that distinction is the whole point. Running this before
the resolver was corrected would have stamped 1800 rows from a five-band
constant that disagrees with Fairview's nine configured bands.

DRY RUN BY DEFAULT. Nothing is written without --write. The dry run prints the
letter distribution and every row it cannot letter, so the outcome is visible
before it is committed.

    python -m scripts.backfill_grade_letters "<DSN>"
    python -m scripts.backfill_grade_letters "<DSN>" --write

Idempotent: re-running recomputes the same values. Safe to resume after a
dropped connection - it commits in batches, like the CBT backfill, because the
link to Ohio has dropped mid-run before.
"""
from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.modules.school import Grade
from app.services.grading import letter_for, load_grade_bands

BATCH = 200


def _dsn() -> str:
    """No default: this writes, and a wrong default once pointed at the database
    Fairview had been migrated off."""
    for a in sys.argv[1:]:
        if not a.startswith("--"):
            return a.split("?")[0]
    env = os.environ.get("DATABASE_URL", "").strip()
    if env:
        return env.split("?")[0]
    sys.exit("Pass the DSN as the first argument, or set DATABASE_URL.")


def _fix(g: Grade, bands) -> tuple[float | None, str | None]:
    """The corrected (score, letter) for one row."""
    score = round(float(g.score), 2) if g.score is not None else None
    # Letter from the ROUNDED score, so the letter always agrees with the number
    # printed beside it. A raw 69.999 displayed as 70.0 must not letter as D.
    return score, letter_for(score, g.max_score, bands)


async def main() -> int:
    write = "--write" in sys.argv
    engine = create_async_engine(_dsn(), echo=False, connect_args={"ssl": "require"})
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        org_ids = [r[0] for r in (await db.execute(select(Grade.org_id).distinct())).all()]
        print(f"{'WRITE' if write else 'DRY RUN'} - organisations with grades: {len(org_ids)}\n")

        grand = Counter()
        for org_id in org_ids:
            bands = await load_grade_bands(db, org_id)
            print(f"org {org_id}")
            print(f"  configured bands : "
                  f"{', '.join(b.grade for b in bands) if bands else 'NONE (fallback scale)'}")

            rows = (await db.execute(select(Grade).where(Grade.org_id == org_id))).scalars().all()
            letters, changed, unlettered, rounded = Counter(), 0, [], 0
            for i, g in enumerate(rows, 1):
                score, letter = _fix(g, bands)
                letters[letter] += 1
                if letter is None and g.score is not None:
                    unlettered.append(g.score)
                if score != g.score:
                    rounded += 1
                if letter != g.grade_letter or score != g.score:
                    changed += 1
                    if write:
                        g.score = score
                        g.grade_letter = letter
                if write and i % BATCH == 0:
                    await db.commit()
            if write:
                await db.commit()

            print(f"  rows             : {len(rows)}")
            print(f"  scores to round  : {rounded}")
            print(f"  rows to change   : {changed}")
            print("  letters          : "
                  + ", ".join(f"{k or 'NONE'}={v}" for k, v in
                              sorted(letters.items(), key=lambda x: -x[1])))
            if unlettered:
                # Never silent: a row that cannot be lettered is a gap in the
                # school's band setup, and it renders as a blank on a card.
                print(f"  !! {len(unlettered)} row(s) matched NO band, e.g. "
                      f"{sorted(unlettered)[:3]}")
            print()
            grand.update(letters)

        print("total letters:", ", ".join(f"{k or 'NONE'}={v}" for k, v in
                                          sorted(grand.items(), key=lambda x: -x[1])))
        if not write:
            print("\nDRY RUN - nothing written. Re-run with --write to apply.")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
