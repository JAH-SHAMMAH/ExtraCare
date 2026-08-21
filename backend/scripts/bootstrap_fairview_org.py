"""
Bootstrap Fairview School organization on a fresh database.

Runs locally from your machine, connects to the remote database via connection string.

Usage (dry-run):
    python scripts/bootstrap_fairview_org.py "postgresql+asyncpg://user:pass@host/db?ssl=require"

Usage (write):
    python scripts/bootstrap_fairview_org.py "postgresql+asyncpg://user:pass@host/db?ssl=require" --write
"""
from __future__ import annotations

import asyncio
import sys
import os

# Set DATABASE_URL before importing app code
if len(sys.argv) < 2:
    print("usage: python scripts/bootstrap_fairview_org.py <DATABASE_URL> [--write]")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.organization import Organization, IndustryType, SubscriptionTier
from app.routers.organizations import _sync_system_roles_for_org
from app.models.base import Base


async def main() -> int:
    write_mode = "--write" in sys.argv
    db_url = sys.argv[1]

    # Create async engine with the provided connection string
    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # 1. CHECK: Does Fairview already exist?
        existing = (await db.execute(
            select(Organization).where(Organization.slug == "fairview")
        )).scalar_one_or_none()

        if existing:
            print(f"✓ Organization already exists:")
            print(f"  Name: {existing.name}")
            print(f"  Slug: {existing.slug}")
            print(f"  ID: {existing.id}")
            print(f"  Timezone: {existing.timezone}")
            print(f"  Currency: {existing.currency}")
            await engine.dispose()
            return 0

        # 2. DRY-RUN: Show what will be created
        print("=" * 70)
        print("DRY-RUN: The following organization will be created:")
        print("=" * 70)
        print()
        print("Organization:")
        print(f"  Name:              Fairview School")
        print(f"  Slug:              fairview")
        print(f"  Industry:          school")
        print(f"  Subscription Tier: free")
        print(f"  Timezone:          Africa/Lagos")
        print(f"  Currency:          NGN")
        print(f"  Country:           Nigeria")
        print()
        print("System Roles (auto-synced):")
        print(f"  - super_user       [*]")
        print(f"  - org_admin        [school:*, finance:*, hr:*]")
        print(f"  - teacher          [classroom:read, classroom:teach]")
        print(f"  - student          [student:*]")
        print(f"  - staff            [staff:*]")
        print(f"  - parent           [parent:*]")
        print()
        print("=" * 70)

        if not write_mode:
            print()
            print("DRY-RUN ONLY — no changes made.")
            print("Run with --write flag to actually create the organization:")
            print()
            print(f'  python scripts/bootstrap_fairview_org.py "{db_url}" --write')
            print()
            await engine.dispose()
            return 0

        # 3. WRITE: Create the organization
        print()
        print("Writing to database...")
        print()

        org = Organization(
            name="Fairview School",
            slug="fairview",
            industry=IndustryType.SCHOOL,
            subscription_tier=SubscriptionTier.FREE,
            timezone="Africa/Lagos",
            currency="NGN",
            country="Nigeria",
            email="admin@fairviewschoolng.com",
            modules_enabled=[
                "hr", "payroll", "school", "cbt", "pastoral", "reports",
                "library", "attendance", "eclassroom", "voting", "clubs",
                "timetable", "wallet", "facility", "news_feed"
            ],
        )
        db.add(org)
        await db.flush()

        # Sync system roles for this org
        await _sync_system_roles_for_org(db, org)
        await db.commit()

        print(f"✓ Organization created successfully!")
        print(f"  ID:   {org.id}")
        print(f"  Name: {org.name}")
        print(f"  Slug: {org.slug}")
        print()
        print("Next step: Create your Super User account (director@fairviewschoolng.com)")

        await engine.dispose()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))