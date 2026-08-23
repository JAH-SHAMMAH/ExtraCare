#!/usr/bin/env python
"""
DRY-RUN / WRITE: Backfill all existing CBT exams to StudentAssessmentScore.

This script:
1. Finds the "CBT Score" Assessment (created by bootstrap_cbt_assessment.py)
2. Loops over all published CBT exams
3. For each exam, calls sync_cbt_to_assessment_score() (shared with permanent hook)
4. Reports total StudentAssessmentScore rows created/updated

Usage:
  python backfill_cbt_all_exams.py              # DRY-RUN (default)
  python backfill_cbt_all_exams.py --write      # Actually write
"""

import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.models.modules.school import CBTExam
from app.models.modules.platform import Assessment
from sync_cbt_to_assessment import sync_cbt_to_assessment_score

DB_URL = "postgresql+asyncpg://fairview_data_user:1MMCmx2rVy0XbXNh1IBjclMiOH1ACPVa@dpg-da243tn40ujc7394oip0-a.ohio-postgres.render.com/fairview_data?ssl=require"
FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"
CBT_ASSESSMENT_NAME = "CBT Score"


async def get_or_create_cbt_assessment(db: AsyncSession) -> str:
    """Find the CBT Score Assessment; return its ID or None if not found."""
    assessment = (await db.execute(
        select(Assessment).where(
            Assessment.org_id == FAIRVIEW_ORG_ID,
            Assessment.name == CBT_ASSESSMENT_NAME,
        )
    )).scalar_one_or_none()

    if not assessment:
        print(f"[ERROR] Assessment '{CBT_ASSESSMENT_NAME}' not found.")
        print(f"Run: python bootstrap_cbt_assessment.py --write")
        return None

    return assessment.id


async def dry_run():
    clean_url = DB_URL.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"}, pool_pre_ping=True)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("DRY-RUN: Backfill all CBT exams to StudentAssessmentScore")
        print("=" * 80)
        print()

        assessment_id = await get_or_create_cbt_assessment(db)
        if not assessment_id:
            await engine.dispose()
            return

        # Find all published exams
        exams = (await db.execute(
            select(CBTExam).where(
                CBTExam.org_id == FAIRVIEW_ORG_ID,
                CBTExam.results_published_at.isnot(None),  # Only published exams
            ).order_by(CBTExam.created_at)
        )).scalars().all()

        print(f"Published CBT exams found: {len(exams)}")
        print()

        total_synced = 0
        for i, exam in enumerate(exams, 1):
            synced = await sync_cbt_to_assessment_score(
                db, exam.id, assessment_id, FAIRVIEW_ORG_ID
            )
            total_synced += synced
            if synced > 0:
                print(f"{i:3d}. {exam.title[:40]:40s} -> {synced:3d} rows")

        await db.rollback()  # Discard changes from sync calls (dry-run)

        print()
        print("=" * 80)
        print(f"[RESULT] Total StudentAssessmentScore rows to create/update: {total_synced}")
        print("=" * 80)
        print()
        print("Run with --write to apply these changes:")
        print("  python backfill_cbt_all_exams.py --write")

    await engine.dispose()


async def write():
    clean_url = DB_URL.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"}, pool_pre_ping=True)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("WRITE: Backfilling all CBT exams to StudentAssessmentScore")
        print("=" * 80)
        print()

        assessment_id = await get_or_create_cbt_assessment(db)
        if not assessment_id:
            await engine.dispose()
            return

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
        for i, exam in enumerate(exams, 1):
            synced = await sync_cbt_to_assessment_score(
                db, exam.id, assessment_id, FAIRVIEW_ORG_ID
            )
            total_synced += synced
            if synced > 0:
                print(f"{i:3d}. {exam.title[:40]:40s} -> {synced:3d} rows")

        await db.commit()

        print()
        print("=" * 80)
        print(f"[OK] Written {total_synced} StudentAssessmentScore rows")
        print("=" * 80)

    await engine.dispose()


async def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--write":
        await write()
    else:
        await dry_run()


if __name__ == "__main__":
    asyncio.run(main())
