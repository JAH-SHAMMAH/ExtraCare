#!/usr/bin/env python
"""
One-time backfill: sync all published CBT exams to StudentAssessmentScore.

Usage:
  python backfill_cbt_assessments.py              # DRY-RUN (shows what will happen)
  python backfill_cbt_assessments.py --write      # Apply changes

This script:
1. Finds all published CBT exams (results_published_at IS NOT NULL)
2. For each exam, calls sync_cbt_to_assessment_score() (same function used by permanent hook)
3. Reports total StudentAssessmentScore rows created/updated
4. Uses the exact same idempotent logic as the permanent hook in publish_exam_results()

Expected: ~1800 StudentAssessmentScore rows (180 students × 10 subjects)
"""

import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.models.modules.school import CBTExam
from app.services.cbt_assessment_sync import sync_cbt_to_assessment_score

# Same database as production
DB_URL = "postgresql+asyncpg://fairview_data_user:1MMCmx2rVy0XbXNh1IBjclMiOH1ACPVa@dpg-da243tn40ujc7394oip0-a.ohio-postgres.render.com/fairview_data?ssl=require"
FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"


def _resolve_db_url() -> str:
    """First non-flag argument wins, else the default above. Without this the
    passed URL is silently ignored and the hardcoded one used instead."""
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            return arg
    return DB_URL


async def dry_run():
    """Count how many StudentAssessmentScore rows would be created/updated."""
    clean_url = _resolve_db_url().split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"}, pool_pre_ping=True)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("DRY-RUN: Backfill CBT exams to StudentAssessmentScore")
        print("=" * 80)
        print()

        # Find all published exams
        exams = (await db.execute(
            select(CBTExam).where(
                CBTExam.org_id == FAIRVIEW_ORG_ID,
                CBTExam.results_published_at.isnot(None),
            ).order_by(CBTExam.created_at)
        )).scalars().all()

        print(f"Published CBT exams found: {len(exams)}")
        print()

        total_synced = 0
        success_count = 0
        skip_count = 0

        for i, exam in enumerate(exams, 1):
            synced, reason = await sync_cbt_to_assessment_score(db, exam.id, FAIRVIEW_ORG_ID)
            total_synced += synced

            status = "OK" if reason is None else f"SKIP ({reason})"
            if reason is None:
                success_count += 1
            else:
                skip_count += 1

            if synced > 0 or i <= 5 or i > len(exams) - 3:  # Show first 5 and last 3 always
                print(f"{i:3d}. {exam.title[:50]:50s} {status:25s} {synced:3d} rows")

        await db.rollback()  # Discard all changes (dry-run)

        print()
        print("=" * 80)
        print(f"Exams processed: {len(exams)}")
        print(f"  - Synced: {success_count}")
        print(f"  - Skipped: {skip_count} (missing term/subject/results)")
        print(f"Total StudentAssessmentScore rows (create+update): {total_synced}")
        print("=" * 80)
        print()
        print("To apply changes, run:")
        print("  python backfill_cbt_assessments.py --write")

    await engine.dispose()


async def write():
    """Actually write StudentAssessmentScore rows."""
    clean_url = _resolve_db_url().split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"}, pool_pre_ping=True)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("WRITE: Backfilling CBT exams to StudentAssessmentScore")
        print("=" * 80)
        print()

        # Find all published exams
        exams = (await db.execute(
            select(CBTExam).where(
                CBTExam.org_id == FAIRVIEW_ORG_ID,
                CBTExam.results_published_at.isnot(None),
            ).order_by(CBTExam.created_at)
        )).scalars().all()

        print(f"Processing {len(exams)} published exams...")
        print()

        total_synced = 0
        success_count = 0

        for i, exam in enumerate(exams, 1):
            synced, reason = await sync_cbt_to_assessment_score(db, exam.id, FAIRVIEW_ORG_ID)
            total_synced += synced

            # Commit PER EXAM, not once after the loop. The link to Ohio has
            # dropped mid-run repeatedly; an all-or-nothing transaction discards
            # every completed exam when that happens. Each exam is independent,
            # so a crash keeps the work already done and a plain rerun resumes:
            # sync_cbt_to_assessment_score() UPDATEs rows it wrote earlier, and
            # uq_student_assessment_score(org,student,subject,assessment) makes a
            # duplicate INSERT impossible rather than merely unlikely.
            await db.commit()

            if reason is None:
                success_count += 1
                if synced > 0 or i <= 5 or i > len(exams) - 3:
                    print(f"{i:3d}. {exam.title[:50]:50s} {synced:3d} rows  [committed]")

        print()
        print("=" * 80)
        print(f"[OK] Backfill complete")
        print(f"  - Exams processed: {len(exams)}")
        print(f"  - StudentAssessmentScore rows written: {total_synced}")
        print("=" * 80)
        print()
        print("Next: Ngozi and other teachers can now use Make Report.")
        print("CBT results will continue to auto-sync with the permanent hook.")

    await engine.dispose()


async def main():
    # Flag may appear at ANY position — the optional DB URL is also positional,
    # so checking sys.argv[1] alone silently downgrades `<url> --write` to a dry-run.
    if "--write" in sys.argv:
        await write()
    else:
        await dry_run()


if __name__ == "__main__":
    asyncio.run(main())
