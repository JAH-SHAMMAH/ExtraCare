"""
Align GradingBand remarks with the Educare reference (Fairview's live model).

The band LETTERS and RANGES already match the reference exactly; only the remark
text differs. This is a pure data update to rows that already exist, so it is a
script rather than a migration -- and it can reach production without waiting on
the blocked 108-123 migration queue.

    current                     ->  target
    A*  Excellent               ->  Distinction
    A   Very Good               ->  Excellent
    B+  Good                    ->  Upper Credit
    B   Credit                  ->  Credit          (already correct)
    C   Pass                    ->  Upper Merit
    D   Pass with supplement    ->  Merit
    E   Pass (weak)             ->  Lower Merit
    P   Pass (very weak)        ->  Pass
    F   Fail                    ->  Fail            (already correct)

Matches bands by grade letter within each numeric grading scale, so it is safe to
re-run and it leaves descriptor scales (EYFS etc.) untouched. Idempotent.

Usage (dry-run):
    python -m scripts.fix_grading_remarks "postgresql+asyncpg://user:pass@host/db?ssl=require"

Usage (write):
    python -m scripts.fix_grading_remarks "postgresql+asyncpg://user:pass@host/db?ssl=require" --write
"""
from __future__ import annotations

import asyncio
import sys
import os

if len(sys.argv) < 2:
    print("usage: python -m scripts.fix_grading_remarks <DATABASE_URL> [--write]")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.modules.platform import GradingScale, GradingBand

FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"

# Educare's remark for each band letter. Keyed by grade letter (case-insensitive).
TARGET_REMARKS = {
    "A*": "Distinction",
    "A": "Excellent",
    "B+": "Upper Credit",
    "B": "Credit",
    "C": "Upper Merit",
    "D": "Merit",
    "E": "Lower Merit",
    "P": "Pass",
    "F": "Fail",
}


async def main() -> int:
    write_mode = "--write" in sys.argv
    db_url = sys.argv[1]

    engine = create_async_engine(db_url.split("?")[0], echo=False,
                                 connect_args={"ssl": "require"}, pool_pre_ping=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        print("=" * 76)
        print(f"{'WRITE' if write_mode else 'DRY-RUN'}: Align GradingBand remarks with Educare")
        print("=" * 76)
        print()

        scales = (await db.execute(
            select(GradingScale).where(GradingScale.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        changes = 0
        already = 0
        unknown = 0

        for sc in scales:
            bands = sorted((await db.execute(
                select(GradingBand).where(
                    GradingBand.scale_id == sc.id, GradingBand.org_id == FAIRVIEW_ORG_ID)
            )).scalars().all(), key=lambda b: (b.position or 0))
            if not bands:
                continue

            print(f"SCALE: {sc.name!r}  (type={sc.scale_type}, purpose={sc.purpose}, {len(bands)} bands)")
            for b in bands:
                target = TARGET_REMARKS.get((b.grade or "").strip().upper())
                rng = f"{b.min_score if b.min_score is not None else 0:g}-{b.max_score if b.max_score is not None else 100:g}"
                if target is None:
                    print(f"   {b.grade:<4} {rng:>9}   {b.remark!r:<26} -- no target for this letter, LEFT ALONE")
                    unknown += 1
                    continue
                if (b.remark or "") == target:
                    print(f"   {b.grade:<4} {rng:>9}   {b.remark!r:<26} == already correct")
                    already += 1
                    continue
                print(f"   {b.grade:<4} {rng:>9}   {b.remark!r:<26} -> {target!r}")
                if write_mode:
                    b.remark = target
                changes += 1
            print()

        print("=" * 76)
        print(f"bands to change     : {changes}")
        print(f"already correct     : {already}")
        print(f"left alone (no map) : {unknown}")
        print("=" * 76)

        if not write_mode:
            print()
            print("DRY-RUN ONLY -- nothing written.")
            print(f'  python -m scripts.fix_grading_remarks "{db_url}" --write')
            await engine.dispose()
            return 0

        await db.commit()
        print()
        print(f"[OK] {changes} band remark(s) updated.")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
