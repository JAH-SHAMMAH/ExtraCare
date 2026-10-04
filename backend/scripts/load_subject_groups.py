"""Educare's subject groups, including the lower-school science progression.

    python scripts/load_subject_groups.py <DSN>            dry run
    python scripts/load_subject_groups.py <DSN> --write    apply
    python scripts/load_subject_groups.py <DSN> --remove <manifest.json>

No migration: `subject_groups` already exists (name, year_group, subject_ids,
section_id) and is empty.

TWO KINDS OF GROUP, and the difference matters.

1. THE SCIENCE PROGRESSION, one row PER YEAR. Educare carries both
   `L S Biology / LS Chemistry / LS Physics` (grouped as "LS Science") and
   standalone `Biology / Chemistry / Physics`. It does not model a subject that
   splits — it keeps two parallel sets, and which one a year group takes is the
   fact being recorded here.

   ✅ ALL SIX YEARS ARE VERIFIED AGAINST EDUCARE.
   Source: Educare → Assign to Classes, pages for Years 7–12, checked
   4 October 2026. Years 7, 8 and 9 take `L S Biology / LS Chemistry /
   LS Physics`; Years 10, 11 and 12 take the standalone `Biology / Chemistry /
   Physics`. This was previously the school's verbal statement rather than a
   reading of the system — it has now been read off Educare directly, year by
   year, and the rows as loaded were correct.

   Note WHERE it was verified: the subject-group COLUMN on the subject list shows
   only that a group exists, never which years take it. Assign to Classes is the
   page that carries the per-year assignment, which is why the boundary could not
   be confirmed from the earlier screenshots.

   One row per year rather than a year_from/year_to range, deliberately: a range
   silently assumes the set is contiguous. It happens to be contiguous (7–9 and
   10–12), but the per-year shape is also what the fuller per-year subject lists
   need, so it stays.

2. THE OTHER SEVEN GROUPS, year_group = NULL. Basic Science, Pre-Vocational
   Studies, National Value Education, Cultural, Nigerian Language, Religion and
   Trade Subject are visible in Educare's own column as permanent
   categorisations, with nothing indicating a year range. NO YEAR RANGE IS
   INVENTED for them — NULL means "not year-scoped", not "unknown".

WHAT THE Assign-to-Classes PAGES ALSO SHOWED, and what these rows do NOT record.
Educare assigns a DIFFERENT FULL SUBJECT LIST TO EVERY SECONDARY YEAR — not one
list per level, and not one junior plus one senior list. There is a large shared
core, but each of the six years adds or drops subjects relative to its
neighbours, and `JAMB / WAEC Practice` is taken by YEAR 12 ONLY. Year 12 also
drops several subjects the other senior years keep (History, PHE, Security
Education, Sociology and the trade subjects).

`subject_groups` captures only the science progression and the seven permanent
categorisations. It does NOT capture a year's full subject list, and was never
meant to. Recording those lists is a separate, planned piece of work.

NOTHING CONSUMES THIS YET. The timetable router has CRUD for subject_groups, but
no report, enrolment path or mark-entry gate reads it. These rows RECORD the
curriculum structure; they do not enforce it. Making them load-bearing — gating
which subjects a Year 8 class can be marked in, say — is a separate decision with
its own blast radius.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import asyncpg

MANIFEST_DIR = os.environ.get("FAIRVIEW_BACKUPS", r"C:\Users\SHAMMAH\fairview-backups")

LOWER_YEARS = ["Year 7", "Year 8", "Year 9"]
UPPER_YEARS = ["Year 10", "Year 11", "Year 12"]

LS_SCIENCE = ["L S Biology", "LS Chemistry", "LS Physics"]
STANDALONE_SCIENCE = ["Biology", "Chemistry", "Physics"]

# name -> member subject titles. year_group stays NULL for all of these.
FLAT_GROUPS = {
    "Basic Science": ["Basic Technology", "PHE"],
    "Pre-Vocational Studies": ["Agricultural science", "Home economics"],
    "National Value Education": ["Social studies", "Civic education",
                                 "Security Education"],
    "Cultural": ["Music", "Cultural and creative arts"],
    "Nigerian Language": ["Hausa", "Igbo", "Yoruba"],
    "Religion": ["C. R. S.", "I. R. S."],
    "Trade Subject": ["Fashion Design And Garment Making", "Livestock Farming",
                      "Computer Hardware And GSM Repairs"],
}

SECTION = "Secondary"


def _dsn() -> str:
    for a in sys.argv[1:]:
        if not a.startswith("--") and "://" in a:
            return a
    env = os.environ.get("DATABASE_URL", "").strip()
    if env:
        return env
    sys.exit("Pass the DSN as the first argument, or set DATABASE_URL.")


async def _remove(dsn: str, path: str) -> None:
    man = json.load(open(path, encoding="utf-8"))
    c = await asyncpg.connect(dsn, timeout=180, command_timeout=600, ssl="require")
    tx = c.transaction()
    await tx.start()
    try:
        await c.execute("DELETE FROM subject_groups WHERE id = ANY($1::varchar[])",
                        man["created"])
        print(f"  removed {len(man['created'])} subject group rows")
        await tx.commit()
        print("REMOVED.")
    except Exception:
        await tx.rollback()
        print("ROLLED BACK — nothing changed.")
        raise
    finally:
        await c.close()


async def main() -> None:
    dsn = _dsn()
    if "--remove" in sys.argv:
        await _remove(dsn, sys.argv[sys.argv.index("--remove") + 1])
        return

    write = "--write" in sys.argv
    c = await asyncpg.connect(dsn, timeout=180, command_timeout=600, ssl="require")
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")

    print("LOAD SUBJECT GROUPS — "
          + ("REAL WRITE" if write else "DRY RUN (writes nothing)"))

    org = await c.fetchval("SELECT id FROM organizations LIMIT 1")
    sec_id = await c.fetchval(
        "SELECT id FROM school_sections WHERE org_id=$1 AND name=$2", org, SECTION)
    if not sec_id:
        sys.exit(f"no {SECTION!r} section")

    subjects = {r["name"]: r["id"] for r in await c.fetch(
        "SELECT id, name FROM subjects WHERE org_id=$1 AND section_id=$2",
        org, sec_id)}
    print(f"\n[0] {len(subjects)} Secondary subjects on file")

    existing = await c.fetchval(
        "SELECT count(*) FROM subject_groups WHERE org_id=$1", org)
    print(f"    subject_groups rows today: {existing}")

    # ── resolve every member before writing anything ────────────────────────
    print("\n[1] MEMBER RESOLUTION — every named subject must exist")
    missing = []
    for label, names in [("LS Science", LS_SCIENCE),
                         ("Sciences", STANDALONE_SCIENCE)] + list(FLAT_GROUPS.items()):
        got = [n for n in names if n in subjects]
        lost = [n for n in names if n not in subjects]
        missing += lost
        flag = "" if not lost else f"   MISSING: {', '.join(lost)}"
        print(f"    {label:26} {len(got)}/{len(names)}{flag}")
    if missing:
        sys.exit(f"{len(missing)} subject(s) named here do not exist in "
                 f"{SECTION}. Load the catalogue first.")

    # ── the plan ────────────────────────────────────────────────────────────
    plan = []
    for y in LOWER_YEARS:
        plan.append(("LS Science", y, LS_SCIENCE, True))
    for y in UPPER_YEARS:
        plan.append(("Sciences", y, STANDALONE_SCIENCE, True))
    for name, names in FLAT_GROUPS.items():
        plan.append((name, None, names, False))

    print("\n[2] THE SCIENCE PROGRESSION — one row per year")
    print("    (VERIFIED against Educare for all six years. Source: Assign to")
    print("     Classes, pages for Years 7-12, checked 4 October 2026. Years 7-9")
    print("     take the LS sciences; Years 10-12 take the standalone ones.)")
    for name, year, names, _ in plan:
        if year:
            print(f"      {name:12} {year:9} {', '.join(names)}")

    print("\n[3] THE OTHER SEVEN — year_group NULL, no range invented")
    for name, year, names, _ in plan:
        if not year:
            print(f"      {name:26} (no year scope) {', '.join(names)}")

    print(f"\n[4] TOTAL: {len(plan)} rows "
          f"({sum(1 for p in plan if p[1])} year-scoped, "
          f"{sum(1 for p in plan if not p[1])} not)")

    tx = c.transaction()
    await tx.start()
    man = {"created_at": now.isoformat(), "created": []}
    try:
        for name, year, names, year_scoped in plan:
            dupe = await c.fetchval("""
                SELECT count(*) FROM subject_groups
                 WHERE org_id=$1 AND name=$2
                   AND year_group IS NOT DISTINCT FROM $3""", org, name, year)
            if dupe:
                print(f"    {name!r}/{year}: already present, skipped")
                continue
            gid = str(uuid.uuid4())
            await c.execute("""
                INSERT INTO subject_groups (id, name, year_group, subject_ids,
                       section_id, org_id, created_at, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$7)""",
                gid, name, year,
                json.dumps([subjects[n] for n in names]), sec_id, org, now)
            man["created"].append(gid)

        print("\n[5] VERIFY BEFORE COMMIT")
        total = await c.fetchval(
            "SELECT count(*) FROM subject_groups WHERE org_id=$1", org)
        print(f"    subject_groups now: {total} (expected {existing + len(man['created'])})")
        assert total == existing + len(man["created"])

        # Every stored id must be a real Secondary subject. Collected into ONE
        # query rather than one per member: at ~940ms round-trip to Render, 23
        # separate lookups kept the transaction open long enough that the
        # connection dropped mid-write on the first attempt.
        all_ids: list[str] = []
        for r in await c.fetch(
                "SELECT name, year_group, subject_ids FROM subject_groups WHERE org_id=$1", org):
            ids = r["subject_ids"]
            if isinstance(ids, str):
                ids = json.loads(ids)
            all_ids += list(ids or [])
        good = {r["id"] for r in await c.fetch(
            "SELECT id FROM subjects WHERE section_id=$1 AND id = ANY($2::varchar[])",
            sec_id, all_ids)}
        bad = [i for i in all_ids if i not in good]
        print(f"    member ids checked: {len(all_ids)}; "
              f"not a Secondary subject: {len(bad)}")
        assert not bad

        n_year = await c.fetchval("""SELECT count(*) FROM subject_groups
             WHERE org_id=$1 AND year_group IS NOT NULL""", org)
        n_flat = await c.fetchval("""SELECT count(*) FROM subject_groups
             WHERE org_id=$1 AND year_group IS NULL""", org)
        print(f"    year-scoped {n_year}, not year-scoped {n_flat}")

        # nothing reads these yet, so nothing else may have moved
        for lbl, q, exp in (("subjects", "SELECT count(*) FROM subjects", 79),
                            ("marks", "SELECT count(*) FROM student_assessment_scores", 5399),
                            ("timetables", "SELECT count(*) FROM timetables", 376)):
            g = await c.fetchval(q)
            print(f"    {'OK  ' if g == exp else 'CHANGED'} {lbl:12} {g} (expected {exp})")

        if not write:
            await tx.rollback()
            print("\nDRY RUN — rolled back. Re-run with --write to apply.")
            return

        os.makedirs(MANIFEST_DIR, exist_ok=True)
        p = os.path.join(MANIFEST_DIR, f"subject_groups_manifest_{stamp}.json")
        json.dump(man, open(p, "w", encoding="utf-8"), indent=1)
        assert len(json.load(open(p, encoding="utf-8"))["created"]) == len(man["created"])
        print(f"\n    manifest written and re-read: {p} ({len(man['created'])} rows)")
        await tx.commit()
        print("COMMITTED.")
    except Exception:
        # A rollback on an already-dead connection raises InterfaceError, which
        # REPLACES the original exception and hides why the write failed — that
        # is exactly what happened on the first attempt here. The server rolls
        # an abandoned transaction back on its own, so the only job in this
        # handler is to not lose the cause.
        try:
            await tx.rollback()
            print("\nROLLED BACK — nothing written.")
        except Exception as rb:
            print(f"\nconnection already gone ({type(rb).__name__}); the server "
                  f"rolls the transaction back by itself — VERIFY before retrying.")
        raise
    finally:
        try:
            await c.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
