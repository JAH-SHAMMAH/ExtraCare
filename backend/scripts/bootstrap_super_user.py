"""
Bootstrap Super User account for Fairview School organization.

Runs locally from your machine, connects to the remote database via connection string.

Usage (dry-run):
    python scripts/bootstrap_super_user.py "postgresql+asyncpg://user:pass@host/db?ssl=require"

Usage (write):
    python scripts/bootstrap_super_user.py "postgresql+asyncpg://user:pass@host/db?ssl=require" --write
"""
from __future__ import annotations

import asyncio
import sys
import os
import secrets

# Set DATABASE_URL before importing app code
if len(sys.argv) < 2:
    print("usage: python scripts/bootstrap_super_user.py <DATABASE_URL> [--write]")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.user import User, UserStatus
from app.models.organization import Organization
from app.models.role import Role
from app.core.security import hash_password, generate_secure_token


# Fairview org ID (from bootstrap_fairview_org step)
FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"
SUPER_USER_EMAIL = "director@fairviewschoolng.com"
SUPER_USER_NAME = "Shamzah Eyeoyibo"


async def main() -> int:
    write_mode = "--write" in sys.argv
    db_url = sys.argv[1]

    # Create async engine with the provided connection string
    # Strip ?ssl=require from the URL and pass it as a connect_args kwarg instead —
    # asyncpg on Windows is unreliable when ssl is passed via the URL query string.
    clean_url = db_url.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # 1. CHECK: Does the user already exist?
        existing_user = (await db.execute(
            select(User).where(
                User.email == SUPER_USER_EMAIL.lower(),
                User.org_id == FAIRVIEW_ORG_ID
            )
        )).scalar_one_or_none()

        if existing_user:
            print(f"âœ“ Super User account already exists:")
            print(f"  Email: {existing_user.email}")
            print(f"  Name: {existing_user.full_name}")
            print(f"  Status: {existing_user.status}")
            print(f"  Roles: {[r.slug for r in existing_user.roles]}")
            await engine.dispose()
            return 0

        # 2. CHECK: Does the org exist?
        org = (await db.execute(
            select(Organization).where(Organization.id == FAIRVIEW_ORG_ID)
        )).scalar_one_or_none()

        if not org:
            print(f"ERROR: Organization {FAIRVIEW_ORG_ID} not found.")
            print("Run bootstrap_fairview_org.py first.")
            await engine.dispose()
            return 1

        # 3. CHECK: Does super_user role exist for the org?
        super_role = (await db.execute(
            select(Role).where(
                Role.org_id == FAIRVIEW_ORG_ID,
                Role.slug == "super_user"
            )
        )).scalar_one_or_none()

        if not super_role:
            print(f"ERROR: super_user role not found for org {org.name}.")
            print("This should have been created by bootstrap_fairview_org.py.")
            await engine.dispose()
            return 1

        # 4. GENERATE: Random temporary password
        temp_password = generate_secure_token(length=16)  # ~21 characters, URL-safe
        hashed_password = hash_password(temp_password)

        # 5. DRY-RUN: Show what will be created
        print("=" * 70)
        print("DRY-RUN: The following Super User account will be created:")
        print("=" * 70)
        print()
        print("User Account:")
        print(f"  Email:                 {SUPER_USER_EMAIL}")
        print(f"  Full Name:             {SUPER_USER_NAME}")
        print(f"  Organization:         {org.name} ({org.slug})")
        print(f"  Status:                active")
        print(f"  Force Password Change: true (you MUST change it on first login)")
        print()
        print("Role Assignment:")
        print(f"  Role:                  super_user")
        print(f"  Scopes:                [*] (all)")
        print()
        print("Temporary Login Credentials (ONE-TIME USE):")
        print(f"  Email:     {SUPER_USER_EMAIL}")
        print(f"  Password:  {temp_password}")
        print()
        print("  âš ï¸  SAVE THIS PASSWORD NOW â€” it is only shown once!")
        print("  âš ï¸  You must change it immediately after first login.")
        print()
        print("=" * 70)

        if not write_mode:
            print()
            print("DRY-RUN ONLY â€” no changes made.")
            print("Run with --write flag to actually create the account:")
            print()
            print(f'  python scripts/bootstrap_super_user.py "{db_url}" --write')
            print()
            await engine.dispose()
            return 0

        # 6. WRITE: Create the user account
        print()
        print("Writing to database...")
        print()

        user = User(
            email=SUPER_USER_EMAIL.lower(),
            full_name=SUPER_USER_NAME,
            hashed_password=hashed_password,
            status=UserStatus.ACTIVE,
            org_id=FAIRVIEW_ORG_ID,
            force_password_change=True,
            email_verified=False,  # Admin can verify manually if needed
        )

        # 7. ASSIGN: super_user role — set BEFORE flush, while user is still
        # transient. Assigning a relationship collection on an already-flushed
        # (persistent) object forces SQLAlchemy to lazy-load the existing
        # collection first, which fails under AsyncSession outside an explicit
        # greenlet context (MissingGreenlet). Transient objects start with an
        # empty in-memory collection, so no DB read is needed here.
        user.roles = [super_role]

        db.add(user)
        await db.flush()
        await db.commit()
        print(f"âœ“ Super User account created successfully!")
        print(f"  ID:    {user.id}")
        print(f"  Email: {user.email}")
        print(f"  Name:  {user.full_name}")
        print()
        print("Temporary Login Credentials:")
        print(f"  Email:     {SUPER_USER_EMAIL}")
        print(f"  Password:  {temp_password}")
        print()
        print("  âš ï¸  SAVE THIS PASSWORD â€” it is only shown once!")
        print("  âš ï¸  You must change it immediately after first login.")
        print()
        print("Next step: Create school sections (Nursery, Primary, Secondary)")

        await engine.dispose()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))


