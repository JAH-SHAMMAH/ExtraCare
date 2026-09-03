#!/usr/bin/env python
"""Dedicated load-test logins — created, used, then removed.

  python scripts/bootstrap_loadtest_accounts.py            # DRY-RUN
  python scripts/bootstrap_loadtest_accounts.py --write    # create
  python scripts/bootstrap_loadtest_accounts.py --remove   # delete them again

Load testing needs working credentials, and the real staff/parent logins have
none we can retrieve (bootstrap passwords are generated and shown once). Resetting
a real user's password to get in would lock them out mid-term, so these exist
instead.

Every account is flagged `is_seed_account=True`, which the codebase already
honours to keep non-real logins out of the staff list, HR/PIM and search — so they
do not appear as staff, employees or search hits while they exist.

They are READ-ONLY subjects: the flows exercised against them are login,
dashboard, exam list and report card. Nothing here writes school data.

The pupil gets its OWN class, never a real one. `is_seed_account` lives on User
and hides the login from staff lists, HR and search — but the grade math runs on
Student, where no such flag exists. `_class_position` counts every non-deleted
pupil in the class, so a test pupil dropped into JSS1 A would turn "position 3 of
15" into "3 of 16" on fifteen real report cards, silently and parent-visibly.

A throwaway class costs an extra row in the class picker while it exists, which is
obvious and harmless. Corrupting a real class's size is neither. Remove them when
the run is done.
"""
from __future__ import annotations

import asyncio
import pathlib
import re
import secrets
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.orm import selectinload, sessionmaker  # noqa: E402

# Full model sweep: SchoolClass.section_id points at school_sections, so a partial
# import cannot resolve the FK when a class row is flushed.
from app.models import user, organization, role, audit, import_job  # noqa: E402,F401
from app.models import hrm, support, payment, hr_extended  # noqa: E402,F401
from app.models.modules import (  # noqa: E402,F401
    school, hospital, business, admissions, academics, pastoral, finance,
    wallet, operations, platform, remita,
)
from app.core.security import hash_password  # noqa: E402
from app.models.modules.school import ParentGuardian, SchoolClass, Student  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.models.user import User, UserStatus  # noqa: E402

PREFIX = "loadtest."
CLASS_NAME = "ZZ Load Test (temporary)"
DOMAIN = "fairviewschoolng.com"
ACCOUNTS = [
    ("teacher", "Load Test Teacher", "teacher"),
    ("student", "Load Test Student", "student"),
    ("parent", "Load Test Parent", "parent"),
]

_CBT = (pathlib.Path(__file__).with_name("backfill_cbt_assessments.py")).read_text()
DB_URL = re.search(r'^DB_URL = "(.+)"', _CBT, re.M).group(1)
ORG_ID = re.search(r'^FAIRVIEW_ORG_ID = "(.+)"', _CBT, re.M).group(1)


def _password() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "Load-" + "".join(secrets.choice(alphabet) for _ in range(14))


async def main() -> int:
    write, remove = "--write" in sys.argv, "--remove" in sys.argv
    mode = "REMOVE" if remove else ("WRITE" if write else "DRY-RUN")
    engine = create_async_engine(DB_URL.split("?")[0], connect_args={"ssl": "require"},
                                 pool_pre_ping=True)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("=" * 78)
    print(f"{mode} — load-test accounts")
    print("=" * 78)

    async with Session() as db:
        emails = [f"{PREFIX}{k}@{DOMAIN}" for k, _, _ in ACCOUNTS]
        found = {
            u.email: u for u in (await db.execute(
                select(User).options(selectinload(User.roles)).where(
                    User.email.in_(emails), User.org_id == ORG_ID)
            )).scalars().all()
        }

        # ── remove ───────────────────────────────────────────────────────────
        if remove:
            stu = (await db.execute(select(Student).where(
                Student.email == f"{PREFIX}student@{DOMAIN}", Student.org_id == ORG_ID
            ))).scalar_one_or_none()
            if stu:
                links = (await db.execute(select(ParentGuardian).where(
                    ParentGuardian.student_id == stu.id))).scalars().all()
                for link in links:
                    await db.delete(link)
                print(f"   removing ParentGuardian links : {len(links)}")
                await db.delete(stu)
                print(f"   removing Student row          : {stu.student_id}")
            for email, u in found.items():
                await db.delete(u)
                print(f"   removing User                 : {email}")
            cls = (await db.execute(select(SchoolClass).where(
                SchoolClass.org_id == ORG_ID, SchoolClass.name == CLASS_NAME
            ))).scalar_one_or_none()
            if cls:
                await db.delete(cls)
                print(f"   removing throwaway class      : {CLASS_NAME}")
            if not found and not stu and not cls:
                print("   nothing to remove.")
            await db.commit()
            print("\n[OK] load-test accounts removed.")
            await engine.dispose()
            return 0

        # ── report / create ──────────────────────────────────────────────────
        roles = {
            r.slug: r for r in (await db.execute(
                select(Role).where(Role.org_id == ORG_ID,
                                   Role.slug.in_([s for _, _, s in ACCOUNTS]))
            )).scalars().all()
        }
        missing_roles = [s for _, _, s in ACCOUNTS if s not in roles]
        if missing_roles:
            print(f"ABORT: roles not present in this org: {missing_roles}")
            return 1

        cls = (await db.execute(select(SchoolClass).where(
            SchoolClass.org_id == ORG_ID, SchoolClass.name == CLASS_NAME
        ))).scalar_one_or_none()
        print(f"class for the test pupil : {CLASS_NAME} "
              f"({'exists' if cls else 'would CREATE — never a real class'})")

        for key, name, slug in ACCOUNTS:
            email = f"{PREFIX}{key}@{DOMAIN}"
            state = "ALREADY EXISTS" if email in found else "would CREATE"
            print(f"   {email:<45} role={slug:<9} {state}")
        print("   pupil also gets a Student row + the parent a ParentGuardian link")
        print("   all flagged is_seed_account=True (hidden from staff list, HR, search)")

        if not write:
            print("\nRe-run with --write to create, or --remove to delete them later.")
            await db.rollback()
            await engine.dispose()
            return 0

        password = _password()
        created = []
        for key, name, slug in ACCOUNTS:
            email = f"{PREFIX}{key}@{DOMAIN}"
            if email in found:
                print(f"   skip (exists): {email}")
                continue
            u = User(id=str(uuid.uuid4()), email=email, full_name=name,
                     hashed_password=hash_password(password), status=UserStatus.ACTIVE,
                     force_password_change=False,   # must be usable non-interactively
                     is_seed_account=True, org_id=ORG_ID)
            u.roles = [roles[slug]]
            db.add(u)
            created.append((email, slug, u))
        await db.flush()

        if cls is None:
            cls = SchoolClass(id=str(uuid.uuid4()), name=CLASS_NAME, level="Secondary",
                              org_id=ORG_ID)
            db.add(cls)
            await db.flush()
            print(f"   created throwaway class: {CLASS_NAME}")

        stu_user = next((u for e, s, u in created if s == "student"), None)
        par_user = next((u for e, s, u in created if s == "parent"), None)
        if stu_user and cls:
            stu = Student(id=str(uuid.uuid4()), student_id="LOADTEST-01",
                          first_name="Load", last_name="Test",
                          email=stu_user.email, user_id=stu_user.id,
                          class_id=cls.id, org_id=ORG_ID)
            db.add(stu)
            await db.flush()
            print(f"   Student row created: {stu.student_id} in {cls.name}")
            if par_user:
                db.add(ParentGuardian(id=str(uuid.uuid4()), user_id=par_user.id,
                                      student_id=stu.id, relationship_type="parent",
                                      is_primary=True, org_id=ORG_ID))
                print("   ParentGuardian link created")
        await db.commit()

        print("\n" + "!" * 78)
        print(f"  PASSWORD (all three): {password}")
        print("  Shown once. Delete these accounts with --remove when the run is done.")
        print("!" * 78)

    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
