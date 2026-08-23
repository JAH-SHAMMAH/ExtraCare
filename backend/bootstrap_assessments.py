#!/usr/bin/env python
"""
Bootstrap AssessmentGroup and Assessment rows for Fairview Secondary.

Creates:
- 1 AssessmentGroup: "Continuous Assessment" (CA)
  - 2 Assessment components: "1st CA" (20pts), "2nd CA" (20pts)
- 1 AssessmentGroup: "Examination" (Exam)
  - 1 Assessment: "Final Exam" (60pts)

This allows the Make Report grid to render and accept scores for Term 1.
Weights sum to 100 (CA=40%, Exam=60%).
"""

import asyncio
from uuid import uuid4
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.modules.platform import AssessmentGroup, Assessment

DB_URL = "postgresql+asyncpg://fairview_data_user:1MMCmx2rVy0XbXNh1IBjclMiOH1ACPVa@dpg-da243tn40ujc7394oip0-a.ohio-postgres.render.com/fairview_data?ssl=require"
FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"

ASSESSMENTS = [
    {
        "group_name": "Continuous Assessment",
        "assessments": [
            {"name": "1st CA", "max_score": 20, "weight": 20},
            {"name": "2nd CA", "max_score": 20, "weight": 20},
        ],
    },
    {
        "group_name": "Examination",
        "assessments": [
            {"name": "Final Exam", "max_score": 60, "weight": 60},
        ],
    },
]


async def dry_run():
    print("=" * 80)
    print("DRY-RUN: Bootstrap Assessment structure for Fairview Secondary")
    print("=" * 80)
    print()

    total_groups = len(ASSESSMENTS)
    total_assessments = sum(len(g["assessments"]) for g in ASSESSMENTS)

    print(f"AssessmentGroups to create: {total_groups}")
    print(f"Assessments to create: {total_assessments}")
    print()

    for group in ASSESSMENTS:
        print(f"Group: {group['group_name']}")
        total_weight = sum(a["weight"] for a in group["assessments"])
        for a in group["assessments"]:
            print(f"  - {a['name']}: {a['max_score']} pts (weight: {a['weight']}%)")
        print(f"  Total weight in group: {total_weight}%")
        print()

    total_weight = sum(
        sum(a["weight"] for a in g["assessments"])
        for g in ASSESSMENTS
    )
    print(f"Total weight across all assessments: {total_weight}%")
    print()

    if total_weight != 100:
        print(f"[WARNING] Total weight should be 100, got {total_weight}")
    else:
        print("[OK] Weights sum to 100%")


async def write():
    clean_url = DB_URL.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"}, pool_pre_ping=True)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("WRITE: Creating Assessment structure")
        print("=" * 80)
        print()

        created_groups = 0
        created_assessments = 0

        for group_data in ASSESSMENTS:
            # Create AssessmentGroup
            group = AssessmentGroup(
                id=str(uuid4()),
                org_id=FAIRVIEW_ORG_ID,
                name=group_data["group_name"],
                description=f"Assessment group: {group_data['group_name']}",
                created_at=datetime.utcnow(),
            )
            db.add(group)
            await db.flush()
            created_groups += 1

            # Create Assessment components
            for a_data in group_data["assessments"]:
                assessment = Assessment(
                    id=str(uuid4()),
                    org_id=FAIRVIEW_ORG_ID,
                    assessment_group_id=group.id,
                    name=a_data["name"],
                    max_score=a_data["max_score"],
                    weight=a_data["weight"],
                    created_at=datetime.utcnow(),
                )
                db.add(assessment)
                created_assessments += 1

        await db.commit()

        print(f"[OK] Created {created_groups} AssessmentGroups")
        print(f"[OK] Created {created_assessments} Assessments")
        print()
        print("Assessment structure ready for Make Report")

    await engine.dispose()


async def main():
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--write":
        await write()
    else:
        await dry_run()
        print()
        print("Run with --write to create assessments:")
        print("  python bootstrap_assessments.py --write")


if __name__ == "__main__":
    asyncio.run(main())
