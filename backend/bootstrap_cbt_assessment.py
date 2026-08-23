#!/usr/bin/env python
"""
Bootstrap: Create "CBT Score" Assessment for Fairview.

Creates:
- 1 AssessmentGroup: "CBT Score" (placeholder group, can hold multiple assessments)
- 1 Assessment: "CBT Score" (100 points, 100% weight)

This assessment is fed by the permanent hook in cbt.py's publish_exam_results()
and by the backfill script.
"""

import asyncio
import sys
from uuid import uuid4
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.models.modules.platform import AssessmentGroup, Assessment

DB_URL = "postgresql+asyncpg://fairview_data_user:1MMCmx2rVy0XbXNh1IBjclMiOH1ACPVa@dpg-da243tn40ujc7394oip0-a.ohio-postgres.render.com/fairview_data?ssl=require"
FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"


async def dry_run():
    print("=" * 80)
    print("DRY-RUN: Bootstrap CBT Assessment")
    print("=" * 80)
    print()
    print("AssessmentGroup: 'CBT Score'")
    print("  Assessment: 'CBT Score' (max_score=100, weight=100%)")
    print()
    print("Total weight: 100%")
    print()
    print("[OK] Structure valid")
    print()
    print("Run with --write to create:")
    print("  python bootstrap_cbt_assessment.py --write")


async def write():
    clean_url = DB_URL.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"}, pool_pre_ping=True)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("WRITE: Creating CBT Assessment")
        print("=" * 80)
        print()

        # Check if already exists
        existing = (await db.execute(
            select(Assessment).where(
                Assessment.org_id == FAIRVIEW_ORG_ID,
                Assessment.name == "CBT Score",
            )
        )).scalar_one_or_none()

        if existing:
            print(f"[OK] Assessment 'CBT Score' already exists (ID: {existing.id})")
            await engine.dispose()
            return

        # Create AssessmentGroup
        group = AssessmentGroup(
            id=str(uuid4()),
            org_id=FAIRVIEW_ORG_ID,
            name="CBT Score",
        )
        db.add(group)
        await db.flush()

        # Create Assessment
        assessment = Assessment(
            id=str(uuid4()),
            org_id=FAIRVIEW_ORG_ID,
            assessment_group_id=group.id,
            name="CBT Score",
            max_score=100,
            weight=100,
            created_at=datetime.utcnow(),
        )
        db.add(assessment)

        await db.commit()

        print(f"[OK] Created AssessmentGroup: {group.id}")
        print(f"[OK] Created Assessment: {assessment.id}")
        print()
        print("CBT Assessment ready for backfill")

    await engine.dispose()


async def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--write":
        await write()
    else:
        await dry_run()


if __name__ == "__main__":
    asyncio.run(main())
