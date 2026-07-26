"""
One-off bootstrap: grant the FIRST Super User on an existing org.

Why this exists
---------------
The role-assignment escalation guard (app/core/permissions.py) deliberately
prevents an org_admin from granting itself (or anyone) the `super_user` role —
that is what keeps the sensitive `finance_admin:*` tier out of reach of ordinary
admins. But an org created BEFORE the "org creator is Super User" bootstrap fix
(app/routers/auth.py) has no Super User at all, and the guard means the UI/API
can't mint the first one. This script does it directly through the ORM, which
runs BELOW the HTTP guard — the safe, intended escape hatch.

What it does (and does NOT do)
------------------------------
  • Ensures the org's system roles are synced, so `super_user` exists with the
    current preset (`["*"]`) — same refresh as POST /organizations/current/sync-roles.
  • ADDS the `super_user` role to the target user (keeps their existing roles).
  • Idempotent — safe to run twice; a no-op if the user is already Super User.
  • Never touches passwords, never deletes anything.

Usage
-----
    cd backend
    venv/Scripts/python -m scripts.bootstrap_super_user  you@example.com
    # If the same email exists in more than one org, disambiguate by org slug:
    venv/Scripts/python -m scripts.bootstrap_super_user  you@example.com  fairview

On Render: open the backend service Shell and run the same command (it uses the
service's DATABASE_URL, i.e. prod Postgres). Run POST-migrate.
"""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal, init_db
from app.models.user import User
from app.models.role import Role
from app.models.organization import Organization
from app.routers.organizations import _sync_system_roles_for_org


async def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m scripts.bootstrap_super_user <email> [org_slug]")
        return 2
    email = sys.argv[1].strip().lower()
    org_slug = sys.argv[2].strip().lower() if len(sys.argv) > 2 else None

    await init_db()

    async with AsyncSessionLocal() as db:
        # Resolve the user (case-insensitive email), disambiguating by org if asked.
        q = select(User).options(selectinload(User.roles)).where(User.email.ilike(email))
        users = (await db.execute(q)).scalars().all()
        if org_slug:
            org = (await db.execute(select(Organization).where(Organization.slug == org_slug))).scalar_one_or_none()
            if not org:
                print(f"ERROR: no org with slug '{org_slug}'.")
                return 1
            users = [u for u in users if u.org_id == org.id]

        if not users:
            where = f" in org '{org_slug}'" if org_slug else ""
            print(f"ERROR: no user with email '{email}'{where}.")
            return 1
        if len(users) > 1:
            orgs = ", ".join(sorted({u.org_id for u in users}))
            print(f"ERROR: '{email}' exists in multiple orgs ({orgs}). Re-run with an org slug.")
            return 1

        user = users[0]
        org = (await db.execute(select(Organization).where(Organization.id == user.org_id))).scalar_one_or_none()
        if not org:
            print(f"ERROR: user's org '{user.org_id}' not found.")
            return 1

        print(f"user:   {user.full_name} <{user.email}>  (org: {org.name} / {org.slug})")
        print(f"before: roles={[r.slug for r in user.roles]}")

        # 1) Make sure super_user exists with the current preset ["*"] (+ refresh all).
        await _sync_system_roles_for_org(db, org)
        await db.flush()

        super_role = (await db.execute(
            select(Role).where(Role.org_id == org.id, Role.slug == "super_user")
        )).scalar_one_or_none()
        if not super_role:
            print("ERROR: super_user role missing even after sync — check presets.")
            return 1

        # 2) Add it (additive — keep existing roles). Idempotent.
        if any(r.id == super_role.id for r in user.roles):
            print("note:   user is ALREADY Super User — nothing to change.")
        else:
            user.roles = list(user.roles) + [super_role]
            await db.commit()
            # reload for the printout
            user = (await db.execute(q.where(User.id == user.id))).scalars().first()

        perms = sorted(user.permissions)
        print(f"after:  roles={[r.slug for r in user.roles]}")
        print(f"perms:  {perms}   (has '*': {'*' in perms})")
        print("OK — this account is now Super User." if "*" in perms else "WARNING: '*' not present; check super_user preset.")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
