"""
Bootstrap academic terms and sub-terms for Fairview School.

Creates the three main terms (Term 1, Term 2, Term 3) and two sub-terms
(Half-Term, Full-Term) that structure the academic year for grading and
reporting purposes. One term is marked as active (current).

Runs locally from your machine, connects to the remote database via connection string.

Usage (dry-run):
    python -m scripts.bootstrap_academic_terms "postgresql+asyncpg://user:pass@host/db?ssl=require"

Usage (write):
    python -m scripts.bootstrap_academic_terms "postgresql+asyncpg://user:pass@host/db?ssl=require" --write
"""
from __future__ import annotations

import asyncio
import sys
import os
import uuid

if len(sys.argv) < 2:
    print("usage: python -m scripts.bootstrap_academic_terms <DATABASE_URL> [--write]")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.modules.platform import AcademicTerm, AcademicSubTerm

FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"

TERMS = [
    ("Term 1", 1),
    ("Term 2", 2),
    ("Term 3", 3),
]

SUB_TERMS = [
    ("Half-Term", 1),
    ("Full-Term", 2),
]


async def main() -> int:
    write_mode = "--write" in sys.argv
    db_url = sys.argv[1]

    # Create async engine with proper SSL handling
    clean_url = db_url.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Check for existing terms (idempotent)
        existing_terms = (await db.execute(
            select(AcademicTerm).where(AcademicTerm.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        existing_sub_terms = (await db.execute(
            select(AcademicSubTerm).where(AcademicSubTerm.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all()

        if existing_terms and existing_sub_terms:
            print(f"Found existing terms and sub-terms — nothing to do.")
            await engine.dispose()
            return 0

        print("=" * 70)
        print("DRY-RUN: Academic terms and sub-terms will be created for Fairview")
        print("=" * 70)
        print()
        print("Terms:")
        for name, position in TERMS:
            print(f"  - {name} (position {position})")
        print()
        print("Sub-terms:")
        for name, position in SUB_TERMS:
            print(f"  - {name} (position {position})")
        print()
        print("Term 1 will be marked as ACTIVE (current term)")
        print()
        print("=" * 70)
        print()

        if not write_mode:
            print("DRY-RUN ONLY — no changes made.")
            print("Run with --write flag to actually create these terms:")
            print()
            print(f'  python -m scripts.bootstrap_academic_terms "{db_url}" --write')
            print()
            await engine.dispose()
            return 0

        print("Writing to database...")
        print()

        # Create terms
        term_objs = {}
        for name, position in TERMS:
            term = AcademicTerm(
                id=str(uuid.uuid4()),
                org_id=FAIRVIEW_ORG_ID,
                name=name,
                position=position,
                is_active=(position == 1),  # Mark Term 1 as active
            )
            db.add(term)
            term_objs[name] = term

        await db.flush()

        # Create sub-terms
        for name, position in SUB_TERMS:
            sub_term = AcademicSubTerm(
                id=str(uuid.uuid4()),
                org_id=FAIRVIEW_ORG_ID,
                name=name,
                position=position,
            )
            db.add(sub_term)

        await db.commit()

        print(f"[OK] Created {len(TERMS)} terms and {len(SUB_TERMS)} sub-terms!")
        print()
        print("Terms created:")
        for name, position in TERMS:
            active = " (ACTIVE)" if position == 1 else ""
            print(f"  [+] {name}{active}")
        print()
        print("Sub-terms created:")
        for name, position in SUB_TERMS:
            print(f"  [+] {name}")
        print()

        await engine.dispose()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
