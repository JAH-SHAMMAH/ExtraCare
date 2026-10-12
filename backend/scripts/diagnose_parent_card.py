"""READ-ONLY: why can a given parent not see a given child's report card?

Answers the step-1 questions for a real account, in the order they decide the
outcome. SELECTs only -- no UPDATE, no DELETE -- and the database address comes
from a hidden prompt (or ADHOC_DATABASE_URL), never from the command line,
where it would be recorded in shell history and visible in the process list.

    cd backend
    python scripts/diagnose_parent_card.py "Chukwuma Yusuf" "Musa Yusuf" Autumn

Names are matched case-insensitively on full_name / first+last. Pass an email
instead of the parent's name if two people share one. No password, token or
connection string is printed by this script at any point.
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
RELEASED_STAGE = "published"


def _perms(raw) -> list[str]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return []
    return raw if isinstance(raw, list) else []


async def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    parent_q, child_q = sys.argv[1], sys.argv[2]
    term_q = sys.argv[3] if len(sys.argv) > 3 else None

    conn = await asyncpg.connect(dsn(), **asyncpg_kwargs())
    try:
        revision = await conn.fetchval("SELECT version_num FROM alembic_version")

        parent = await conn.fetchrow(
            "SELECT id, full_name, email, org_id, status FROM users "
            "WHERE lower(full_name) = lower($1) OR lower(email) = lower($1) LIMIT 1",
            parent_q)
        child = await conn.fetchrow(
            "SELECT id, first_name, last_name, class_id, user_id, org_id FROM students "
            "WHERE lower(first_name || ' ' || last_name) = lower($1) LIMIT 1", child_q)

        print("0. MIGRATION STATE")
        print(f"   alembic_version = {revision!r}  "
              f"({'OK' if revision == EXPECTED_REVISION else 'NOT at ' + EXPECTED_REVISION})")
        if revision != EXPECTED_REVISION:
            print("   -> the backfill has not run; roles still carry the old scope")
        print()

        print("1. THE TWO RECORDS")
        print(f"   parent {parent_q!r}: {'FOUND' if parent else 'NOT FOUND'}"
              + (f"  (status={parent['status']})" if parent else ""))
        print(f"   child  {child_q!r}: {'FOUND' if child else 'NOT FOUND'}")
        if not parent or not child:
            print("   -> cannot continue without both records")
            return 1
        print()

        print("2. THE PARENT-STUDENT LINK")
        link = await conn.fetchrow(
            "SELECT relationship_type, is_primary FROM parent_guardians "
            "WHERE user_id = $1 AND student_id = $2", parent["id"], child["id"])
        print(f"   parent_guardians row: {'FOUND' if link else 'MISSING'}")
        if link:
            print(f"     relationship={link['relationship_type']} primary={link['is_primary']}")
        else:
            print("   -> _ensure_student_visible refuses, and the card 403/404s "
                  "regardless of scopes. THIS would be the cause.")
        same_org = parent["org_id"] == child["org_id"]
        print(f"   same organisation: {same_org}")
        print()

        print("3. THE PARENT'S ROLES AND SCOPES")
        roles = await conn.fetch(
            "SELECT r.name, r.slug, r.permissions FROM roles r "
            "JOIN user_roles ur ON ur.role_id = r.id WHERE ur.user_id = $1", parent["id"])
        held: set[str] = set()
        for r in roles:
            perms = _perms(r["permissions"])
            held |= set(perms)
            print(f"   - {r['name']!r} (slug={r['slug']}, {len(perms)} scopes)")
        print(f"   holds {OWN_SCOPE}: {OWN_SCOPE in held}"
              + ("" if OWN_SCOPE in held else "   <- the card route refuses without it"))
        print(f"   holds {STAFF_SCOPE}: {STAFF_SCOPE in held}"
              + ("   <- staff scope; the backfill has not reached this role"
                 if STAFF_SCOPE in held else ""))
        print()

        print("4. THE CLASS AND ITS REPORT STAGE")
        if not child["class_id"]:
            print("   the child has NO class -- the endpoint fails closed and shows nothing")
        else:
            klass = await conn.fetchrow(
                "SELECT name, level FROM school_classes WHERE id = $1", child["class_id"])
            print(f"   class: {klass['name'] if klass else '(missing row)'}")
            approvals = await conn.fetch(
                "SELECT ra.stage, ra.academic_year, t.name AS term "
                "FROM report_approvals ra LEFT JOIN academic_terms t ON t.id = ra.term_id "
                "WHERE ra.class_id = $1 ORDER BY t.name", child["class_id"])
            if not approvals:
                print("   NO report_approvals rows for this class -- nothing is released, "
                      "so a parent sees an empty card for every term")
            for a in approvals:
                mark = "RELEASED" if a["stage"] == RELEASED_STAGE else a["stage"]
                hit = "  <- the term asked about" if term_q and a["term"] == term_q else ""
                print(f"     term={a['term']!r} year={a['academic_year']!r} stage={mark}{hit}")
        print()

        if term_q:
            print(f"5. PUBLISHED MARKS FOR {term_q!r}")
            n = await conn.fetchval(
                "SELECT count(*) FROM grades WHERE student_id = $1 AND term = $2 "
                "AND status = 'PUBLISHED'", child["id"], term_q)
            total = await conn.fetchval(
                "SELECT count(*) FROM grades WHERE student_id = $1 AND term = $2",
                child["id"], term_q)
            print(f"   {n} published of {total} grade row(s)")
            if total and not n:
                print("   -> marks exist but are still DRAFT; a parent sees none of them")
            print()

        print("Nothing was written: this script issues SELECTs only.")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
