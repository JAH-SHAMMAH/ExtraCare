"""READ-ONLY: did the report-scope split actually land?

Run this AFTER the deploy. It issues SELECTs only -- no UPDATE, no DELETE -- and
takes the database address from a hidden prompt (or ADHOC_DATABASE_URL) rather
than from the command line, where it would be recorded in shell history and
visible in the process list.

    cd backend
    python scripts/verify_report_scope_split.py

Four questions, in the order they matter:

  1. Is alembic_version at 139_parent_report_scope? If not, the code is live and
     the data is not -- the exact failure DEPLOYMENT.md was written about, and
     the reason to read alembic_version rather than probe the API.
  2. Does any parent- or pupil-derived role still hold school:reports:read?
     Expect zero.
  3. Which roles still hold it, and are they all staff? The migration leaves
     staff roles alone by design, so a non-empty list here is correct -- but it
     should contain nothing self-service.
  4. Does every parent/pupil role now hold school:reports:own:read? A role with
     NEITHER scope cannot read its own child's card, which would be the fix
     overshooting.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from _dsn import asyncpg_kwargs, dsn  # noqa: E402

STAFF_SCOPE = "school:reports:read"
OWN_SCOPE = "school:reports:own:read"
EXPECTED_REVISION = "139_parent_report_scope"

#: Must match the migration's list exactly, or this check disagrees with the
#: thing it is checking.
SELF_SERVICE_SCOPES = {
    "payments:own:read", "school:attendance:read", "school:feedback:read",
    "school:journals:read", "school:cbt:sit", "school:classroom:read",
    "school:clubs:read", "school:lessons:read", "school:library:read",
    "school:timetable:read", "school:voting:submit",
    STAFF_SCOPE, OWN_SCOPE,
}


def _perms(raw) -> list[str]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return []
    return raw if isinstance(raw, list) else []


async def main() -> int:
    conn = await asyncpg.connect(dsn(), **asyncpg_kwargs())
    try:
        revision = await conn.fetchval("SELECT version_num FROM alembic_version")
        rows = await conn.fetch(
            "SELECT r.id, r.name, r.slug, r.permissions, r.is_system, o.slug AS org "
            "FROM roles r LEFT JOIN organizations o ON o.id = r.org_id ORDER BY o.slug, r.slug")
    finally:
        await conn.close()

    problems = 0

    print("1. MIGRATION STATE")
    ok = revision == EXPECTED_REVISION
    print(f"   alembic_version = {revision!r}")
    print(f"   expected        = {EXPECTED_REVISION!r}   -> {'OK' if ok else 'NOT APPLIED'}")
    if not ok:
        problems += 1
        print("   The code may be live with the data unmigrated. Apply it with:")
        print('     DATABASE_URL="postgresql+asyncpg://<dsn>" python -m alembic upgrade head')
    print()

    parsed = [(r["name"], r["slug"], r["org"], _perms(r["permissions"]), r["is_system"])
              for r in rows]
    self_service = [p for p in parsed if p[3] and set(p[3]) <= SELF_SERVICE_SCOPES]
    staffish = [p for p in parsed if not (p[3] and set(p[3]) <= SELF_SERVICE_SCOPES)]

    print("2. SELF-SERVICE ROLES STILL HOLDING THE STAFF SCOPE  (expect 0)")
    offenders = [p for p in self_service if STAFF_SCOPE in p[3]]
    print(f"   {len(offenders)} of {len(self_service)} self-service role(s)")
    for name, slug, org, _p, _s in offenders:
        problems += 1
        print(f"   STILL EXPOSED: {name!r} (slug={slug}, org={org})")
    print()

    print("3. STAFF ROLES HOLDING THE STAFF SCOPE  (expected, left alone by design)")
    holders = [p for p in staffish if STAFF_SCOPE in p[3]]
    print(f"   {len(holders)} role(s):")
    for name, slug, org, perms, _s in holders:
        print(f"     - {name!r} (slug={slug}, org={org}, {len(perms)} scopes)")
    print()

    print("4. SELF-SERVICE ROLES ABLE TO READ THEIR OWN CARD  (expect all)")
    blind = [p for p in self_service if OWN_SCOPE not in p[3] and STAFF_SCOPE not in p[3]]
    print(f"   {len(self_service) - len(blind)} of {len(self_service)} hold {OWN_SCOPE}")
    for name, slug, org, _p, _s in blind:
        problems += 1
        print(f"   CANNOT READ OWN CARD: {name!r} (slug={slug}, org={org}) -- the fix overshot")
    print()

    print("=" * 62)
    print("ALL CHECKS PASSED" if problems == 0 else f"{problems} PROBLEM(S) -- see above")
    print("Nothing was written: this script issues SELECTs only.")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
