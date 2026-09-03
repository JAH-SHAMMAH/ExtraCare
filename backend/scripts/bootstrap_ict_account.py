#!/usr/bin/env python
"""Create the ICT Support account.

  python scripts/bootstrap_ict_account.py              # DRY-RUN
  python scripts/bootstrap_ict_account.py --write      # apply

Creates ict@fairviewschoolng.com holding the `it_support` role, with a generated
password and force_password_change=true so the holder must set their own on first
sign-in. Idempotent: an existing account is reported, never silently overwritten
(re-running must not reset a working password).

Also repairs the role's display name if it reads "It Support". The startup
self-heal that first created the row used slug.title(); sync-roles compares
permissions and never names, so nothing else corrects it.

The password is printed ONCE, here. It is not emailed — this deployment has no
email sender (DEPLOYMENT.md §11) — so hand it over out of band.
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

from app.core.security import hash_password  # noqa: E402
from app.models.role import Role, role_display_name  # noqa: E402
from app.models.user import User, UserStatus  # noqa: E402

EMAIL = "ict@fairviewschoolng.com"
FULL_NAME = "ICT Support"
ROLE_SLUG = "it_support"

_CBT = (pathlib.Path(__file__).with_name("backfill_cbt_assessments.py")).read_text()
DB_URL = re.search(r'^DB_URL = "(.+)"', _CBT, re.M).group(1)
ORG_ID = re.search(r'^FAIRVIEW_ORG_ID = "(.+)"', _CBT, re.M).group(1)


def _generate_password() -> str:
    """A password a human can retype once, then discard at first sign-in."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "Ict-" + "".join(secrets.choice(alphabet) for _ in range(14))


async def main() -> int:
    write = "--write" in sys.argv
    engine = create_async_engine(DB_URL.split("?")[0], connect_args={"ssl": "require"},
                                 pool_pre_ping=True)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("=" * 78)
    print(("WRITE" if write else "DRY-RUN") + " — ICT Support account")
    print("=" * 78)

    async with Session() as db:
        role = (await db.execute(
            select(Role).where(Role.org_id == ORG_ID, Role.slug == ROLE_SLUG)
        )).scalar_one_or_none()
        if role is None:
            print(f"ABORT: role {ROLE_SLUG!r} does not exist in this org. Deploy the "
                  f"backend (startup self-heal seeds it) or POST /organizations/"
                  f"current/sync-roles first.")
            return 1

        want_name = role_display_name(ROLE_SLUG)
        print(f"role            : {role.slug}  (id {role.id})")
        print(f"  display name  : {role.name!r}" +
              ("" if role.name == want_name else f"  -> would fix to {want_name!r}"))
        print(f"  scopes        : {len(role.permissions or [])}")
        print(f"  can escalate  : {'*' in (role.permissions or [])}  (must be False)")

        existing = (await db.execute(
            select(User).options(selectinload(User.roles)).where(
                User.email == EMAIL, User.org_id == ORG_ID
            )
        )).scalar_one_or_none()

        print(f"\naccount         : {EMAIL}")
        if existing:
            print(f"  ALREADY EXISTS: id={existing.id} status={existing.status.value} "
                  f"roles={[r.slug for r in existing.roles]}")
            print("  -> no password would be changed. Use the Reset Password action "
                  "in the app if the holder is locked out.")
        else:
            print("  does not exist -> would CREATE")
            print(f"  full_name             : {FULL_NAME}")
            print(f"  role                  : {ROLE_SLUG}")
            print("  status                : ACTIVE")
            print("  force_password_change : True")
            print("  password              : <generated, shown only on --write>")

        if not write:
            print("\n" + "=" * 78)
            todo = []
            if role.name != want_name:
                todo.append(f"rename role to {want_name!r}")
            if not existing:
                todo.append("create the account")
            print("Would do: " + ("; ".join(todo) if todo else "nothing — already in place"))
            print("Re-run with --write to apply.")
            print("=" * 78)
            await db.rollback()
            await engine.dispose()
            return 0

        # ── write ────────────────────────────────────────────────────────────
        if role.name != want_name:
            role.name = want_name
            print(f"\n[OK] role renamed to {want_name!r}")

        if existing:
            print("\n[OK] account already present — left untouched.")
            await db.commit()
        else:
            password = _generate_password()
            user = User(
                id=str(uuid.uuid4()),
                email=EMAIL,
                full_name=FULL_NAME,
                hashed_password=hash_password(password),
                status=UserStatus.ACTIVE,
                force_password_change=True,
                org_id=ORG_ID,
            )
            user.roles = [role]
            db.add(user)
            await db.commit()
            print(f"\n[OK] created {EMAIL}  (id {user.id})")
            print("\n" + "!" * 78)
            print(f"  PASSWORD: {password}")
            print("  Shown once. Hand it over out of band — this deployment sends no")
            print("  email. The holder must change it at first sign-in.")
            print("!" * 78)

    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
