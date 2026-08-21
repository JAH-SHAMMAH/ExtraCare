"""
Bootstrap standard grading scale for Fairview School Secondary reports.

Creates a single GradingScale with the standard Nigerian Secondary grading
system (A/B/C/D/F bands with percentage cutoffs) as defined by the Secondary
Report pipeline. This scale is used to convert percentage scores to letter
grades on report cards.

Grading bands (Nigerian standard):
  A* (95-100) – Excellent
  A (90-94)   – Very Good
  B+ (85-89)  – Good
  B (80-84)   – Credit
  C (70-79)   – Pass
  D (60-69)   – Pass (with supplement)
  E (50-59)   – Pass (pass + weak)
  P (40-49)   – Pass (very weak)
  F (0-39)    – Fail

Runs locally from your machine, connects to the remote database via connection string.

Usage (dry-run):
    python -m scripts.bootstrap_secondary_grading_scale "postgresql+asyncpg://user:pass@host/db?ssl=require"

Usage (write):
    python -m scripts.bootstrap_secondary_grading_scale "postgresql+asyncpg://user:pass@host/db?ssl=require" --write
"""
from __future__ import annotations

import asyncio
import sys
import os

if len(sys.argv) < 2:
    print("usage: python -m scripts.bootstrap_secondary_grading_scale <DATABASE_URL> [--write]")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.modules.platform import GradingScale, GradingBand

FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"

# Nigerian Secondary grading scale
GRADING_SCALE_NAME = "Nigerian Secondary (A*-F)"
GRADING_SCALE_PURPOSE = "grade"  # For converting percentages to letter grades

# Bands: (letter_grade, min_score, max_score, description)
BANDS = [
    ("A*", 95, 100, "Excellent"),
    ("A", 90, 94, "Very Good"),
    ("B+", 85, 89, "Good"),
    ("B", 80, 84, "Credit"),
    ("C", 70, 79, "Pass"),
    ("D", 60, 69, "Pass with supplement"),
    ("E", 50, 59, "Pass (weak)"),
    ("P", 40, 49, "Pass (very weak)"),
    ("F", 0, 39, "Fail"),
]


async def main() -> int:
    write_mode = "--write" in sys.argv
    db_url = sys.argv[1]

    # Create async engine with proper SSL handling
    clean_url = db_url.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Check for existing grading scale (idempotent)
        existing = (await db.execute(
            select(GradingScale).where(
                GradingScale.org_id == FAIRVIEW_ORG_ID,
                GradingScale.name == GRADING_SCALE_NAME
            )
        )).scalar_one_or_none()

        if existing:
            print(f"Found existing grading scale '{GRADING_SCALE_NAME}' — nothing to do.")
            await engine.dispose()
            return 0

        print("=" * 70)
        print(f"DRY-RUN: {GRADING_SCALE_NAME} grading scale will be created for Fairview")
        print("=" * 70)
        print()
        print(f"Scale: {GRADING_SCALE_NAME}")
        print(f"Purpose: {GRADING_SCALE_PURPOSE} (for converting % scores to letter grades)")
        print()
        print("Grading bands:")
        for letter, min_score, max_score, description in BANDS:
            print(f"  {letter:<2} ({min_score:>3}-{max_score:<3}%)  {description}")
        print()
        print("=" * 70)
        print()

        if not write_mode:
            print("DRY-RUN ONLY — no changes made.")
            print("Run with --write flag to actually create this scale:")
            print()
            print(f'  python -m scripts.bootstrap_secondary_grading_scale "{db_url}" --write')
            print()
            await engine.dispose()
            return 0

        print("Writing to database...")
        print()

        # Create the grading scale
        scale = GradingScale(
            org_id=FAIRVIEW_ORG_ID,
            name=GRADING_SCALE_NAME,
            purpose=GRADING_SCALE_PURPOSE,
            show_in_table=True,
        )
        db.add(scale)
        await db.flush()  # Generate ID before creating bands

        # Create the grading bands
        for letter, min_score, max_score, description in BANDS:
            band = GradingBand(
                scale_id=scale.id,
                org_id=FAIRVIEW_ORG_ID,
                grade=letter,
                min_score=min_score,
                max_score=max_score,
                remark=description,
            )
            db.add(band)

        await db.commit()

        print(f"[OK] Created grading scale '{GRADING_SCALE_NAME}' with {len(BANDS)} bands!")
        print()
        print("Grading bands created:")
        for letter, min_score, max_score, description in BANDS:
            print(f"  [+] {letter:<2} ({min_score:>3}-{max_score:<3}%) {description}")
        print()
        print("Next step: Run bootstrap_secondary_cbt_exams.py to create CBT exams")
        print()

        await engine.dispose()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
