"""
Bootstrap one HR Manager and one Accountant login for Fairview School.

Role slugs are `hr_manager` and `accountant` -- NOT "hr" or "hr_admin", which do
not exist. Both are verified present on the org (44 roles from the Educare role
catalogue) before anything is written.

Emails are on @fairviewschoolng.com because SINGLE_SCHOOL_MODE gates login to that
domain (app/config.py :: email_allowed) -- an account on any other domain could
not sign in at all.

Idempotent: an existing account for either email is reported and left untouched,
so a re-run never resets a password someone is already using.

Usage (dry-run):
    python -m scripts.bootstrap_staff_accounts "postgresql+asyncpg://user:pass@host/db?ssl=require"

Usage (write):
    python -m scripts.bootstrap_staff_accounts "postgresql+asyncpg://user:pass@host/db?ssl=require" --write
"""
from __future__ import annotations

import asyncio
import sys
import os

if len(sys.argv) < 2:
    print("usage: python -m scripts.bootstrap_staff_accounts <DATABASE_URL> [--write]")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import selectinload

from app.models.user import User, UserStatus
from app.models.role import Role
from app.core.security import hash_password, generate_secure_token

FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"
EMAIL_DOMAIN = "fairviewschoolng.com"

# (role_slug, full_name, email_local_part, human label)
ACCOUNTS = [
    ("hr_manager", "Adaeze Nwosu", "adaeze.nwosu", "HR Manager"),
    ("accountant", "Oluwaseun Balogun", "oluwaseun.balogun", "Accountant"),
]


async def main() -> int:
    write_mode = "--write" in sys.argv
    db_url = sys.argv[1]

    engine = create_async_engine(db_url.split("?")[0], echo=False,
                                 connect_args={"ssl": "require"}, pool_pre_ping=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        print("=" * 78)
        print(f"{'WRITE' if write_mode else 'DRY-RUN'}: HR Manager + Accountant accounts")
        print("=" * 78)
        print()

        roles = {
            r.slug: r for r in (await db.execute(
                select(Role).where(Role.org_id == FAIRVIEW_ORG_ID)
            )).scalars().all()
        }

        plan = []
        for slug, full_name, local, label in ACCOUNTS:
            email = f"{local}@{EMAIL_DOMAIN}".lower()
            role = roles.get(slug)
            existing = (await db.execute(
                select(User).options(selectinload(User.roles)).where(User.email == email)
            )).scalar_one_or_none()
            plan.append((slug, full_name, email, label, role, existing,
                         generate_secure_token(length=16)))

        blocked = False
        for slug, full_name, email, label, role, existing, _pw in plan:
            print(f"{label} ({slug})")
            print(f"   name  : {full_name}")
            print(f"   email : {email}")
            if role is None:
                print(f"   ROLE  : !! '{slug}' NOT FOUND on this org -- cannot create")
                blocked = True
            else:
                print(f"   role  : found, {len(role.permissions or [])} permission(s)")
                for p in sorted(role.permissions or []):
                    print(f"             {p}")
            if existing:
                print(f"   STATUS: already exists (id={existing.id[:8]}…) -- will be LEFT UNTOUCHED")
            else:
                print(f"   STATUS: will be created, force_password_change=true")
            print()

        to_create = [p for p in plan if p[5] is None and p[4] is not None]

        print("=" * 78)
        print(f"to create        : {len(to_create)}")
        print(f"already existing : {sum(1 for p in plan if p[5] is not None)}")
        print(f"blocked (no role): {sum(1 for p in plan if p[4] is None)}")
        print("=" * 78)

        if blocked:
            print()
            print("Refusing to continue: a required role is missing on this org.")
            await engine.dispose()
            return 1

        if not write_mode:
            print()
            print("DRY-RUN ONLY -- nothing written. Passwords are generated at write time.")
            print(f'  python -m scripts.bootstrap_staff_accounts "{db_url}" --write')
            await engine.dispose()
            return 0

        if not to_create:
            print()
            print("Nothing to create.")
            await engine.dispose()
            return 0

        print()
        for slug, full_name, email, label, role, _existing, pw in to_create:
            u = User(
                email=email,
                full_name=full_name,
                hashed_password=hash_password(pw),
                status=UserStatus.ACTIVE,
                org_id=FAIRVIEW_ORG_ID,
                force_password_change=True,
                email_verified=False,
            )
            u.roles = [role]
            db.add(u)
        await db.commit()

        print("=" * 78)
        print("LOGINS (save these -- passwords are not recoverable):")
        print("=" * 78)
        for slug, full_name, email, label, _role, _existing, pw in to_create:
            print(f"  {label:<12} {full_name}")
            print(f"    email    : {email}")
            print(f"    password : {pw}")
            print(f"    role     : {slug}  (force_password_change=true)")
            print()

    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
