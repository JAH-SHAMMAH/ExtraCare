"""READ-ONLY dry run: what would per-year subject lists refuse, if anything enforced them?

WRITES NOTHING. No migration, no gate, no row touched, no table created.
DELIBERATELY UNTRACKED — do not `git add` this file. It sits in scripts/ only so
it can be run from the backend folder.

    python scripts/dry_per_year_subjects.py "<DATABASE_URL>"
    DATABASE_URL=... python scripts/dry_per_year_subjects.py

The DSN comes from argv or the environment. There is no credential in this file
and none must ever be added to it.

THE QUESTION IT ANSWERS. Our Secondary classes carry subjects that marks,
enrolments and timetable rows already reference. If a gate ever said "Year 8
cannot be marked in Economics", existing data could fall outside the allowed
list and mark entry would break for real classes. This reports exactly how much,
before anything is built.

THE LISTS ARE CONFIRMED, not provisional. Source: Educare → Assign to Classes,
the "Subjects in Level" column read top-to-bottom for each of Years 7–12,
screenshots dated 4 October 2026. Three spellings are reconciled to OUR
catalogue, which transcribes Educare's own misspellings faithfully:

    Rehearsal          -> REHAERSAL
    Skill Acquisition  -> Skill Aquisition
    Fashion Design     -> Fashion Design And Garment Making

`Computer Hardware And GSM Repairs` is unassigned in all six years — it stays in
the catalogue and belongs to no year's list, so this script expects it to appear
under "our subjects in NO year's list" and that is CORRECT, not a gap.
"""
from __future__ import annotations

import asyncio
import os
import sys

import asyncpg

# ── The six lists, as read off Educare ───────────────────────────────────────
# Years 7-9 share one list exactly (8 and 9 are identical; 7 adds three).
JUNIOR = [
    "English studies", "Mathematics",
    "L S Biology", "LS Chemistry", "LS Physics",
    "Basic Technology", "Business studies", "Agricultural science",
    "Digital Technology", "Social studies", "Civic education", "Music",
    "Cultural and creative arts", "Home economics",
    "Hausa", "Igbo", "Yoruba", "C. R. S.", "French", "PHE", "I. R. S.",
    "Security Education", "IXL Math Prep", "History",
    "Reading Time", "REHAERSAL", "Intervention Class",
]
# Years 10-12 share this; the standalone sciences replace the LS ones, and the
# junior vocational/language block is gone.
SENIOR = [
    "English studies", "Mathematics", "Agricultural science",
    "Digital Technology", "Civic education", "C. R. S.", "French", "I. R. S.",
    "Biology", "Chemistry", "Physics",
    "Economics", "Marketing", "Government", "Geography", "Accounting",
    "Further mathematics", "Technical drawing", "Catering and Craft practice",
    "Visual Arts", "Literature in English", "Commerce",
    "Reading Time", "REHAERSAL", "Intervention Class", "Skill Aquisition",
]

YEAR_SUBJECTS: dict[str, list[str]] = {
    # +3 trade/citizenship subjects that Years 8 and 9 do not take
    "Year 7": JUNIOR + ["Fashion Design And Garment Making",
                        "Livestock Farming",
                        "Social And Citizenship Studies"],
    "Year 8": JUNIOR,
    "Year 9": JUNIOR,                       # identical to Year 8
    "Year 10": SENIOR + ["Sociology",
                         "Fashion Design And Garment Making",
                         "Livestock Farming",
                         "Citizenship And Heritage Studies"],
    "Year 11": SENIOR + ["IXL Math Prep"],
    # Year 12 is Year 11 plus JAMB / WAEC Practice, and drops nothing.
    "Year 12": SENIOR + ["IXL Math Prep", "JAMB / WAEC Practice"],
}
# 30 / 27 / 27 / 30 / 27 / 28
EXPECTED_SIZES = {"Year 7": 30, "Year 8": 27, "Year 9": 27,
                  "Year 10": 30, "Year 11": 27, "Year 12": 28}


def _dsn() -> str:
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    env = os.environ.get("DATABASE_URL", "").strip()
    if env:
        return env
    raise SystemExit(
        'Pass the DSN as the first argument, or set DATABASE_URL.\n'
        '  python scripts/dry_per_year_subjects.py "postgresql://..."')


def _year_of(class_name: str, level: str | None) -> str | None:
    """Map a class to one of the six years, or None if it cannot be placed.

    Conservative on purpose: matches an explicit "Year <n>" token and nothing
    else, checking 12..7 so "Year 1" can never swallow "Year 12". A class it
    cannot place is REPORTED, never guessed at — an unplaceable class is itself
    a reason not to build the gate yet.
    """
    for n in (12, 11, 10, 9, 8, 7):
        if f"year {n}" in (class_name or "").lower():
            return f"Year {n}"
    return None


async def main() -> None:
    dsn = _dsn().replace("postgresql+asyncpg://", "postgresql://")
    c = await asyncpg.connect(dsn, timeout=180, command_timeout=300, ssl="require")
    try:
        org = await c.fetchval("SELECT id FROM organizations LIMIT 1")
        sec = await c.fetchval(
            "SELECT id FROM school_sections WHERE org_id=$1 AND name='Secondary'", org)

        print("=" * 78)
        print("READ-ONLY DRY RUN — per-year subject lists vs the data we hold")
        print("lists CONFIRMED from Educare → Assign to Classes, 4 October 2026")
        print("=" * 78)

        bad = {y: (len(v), EXPECTED_SIZES[y]) for y, v in YEAR_SUBJECTS.items()
               if len(v) != EXPECTED_SIZES[y] or len(set(v)) != len(v)}
        print(f"\n[0] LIST INTEGRITY: {'OK' if not bad else 'MISMATCH ' + str(bad)}")
        for y, v in YEAR_SUBJECTS.items():
            print(f"    {y:9} {len(v)} subjects")

        subs = {r["id"]: r["name"] for r in await c.fetch(
            "SELECT id, name FROM subjects WHERE org_id=$1 AND section_id=$2", org, sec)}
        by_name = {v: k for k, v in subs.items()}

        print("\n[1] DO THE LISTED NAMES RESOLVE TO OUR CATALOGUE?")
        every = sorted({n for v in YEAR_SUBJECTS.values() for n in v})
        missing = [n for n in every if n not in by_name]
        print(f"    our Secondary catalogue:        {len(subs)}")
        print(f"    distinct names listed:          {len(every)}")
        print(f"    resolve to a Secondary subject: {len(every) - len(missing)}")
        print(f"    DO NOT RESOLVE:                 {len(missing)} {missing or ''}")
        unlisted = sorted(set(subs.values()) - set(every))
        print(f"    our subjects in NO year's list: {len(unlisted)} {unlisted or ''}")
        print("      (expected: exactly ['Computer Hardware And GSM Repairs'])")

        print("\n[2] CLASSES — CAN EACH BE PLACED IN A YEAR?")
        classes = await c.fetch(
            "SELECT id, name, level, section_id FROM school_classes "
            "WHERE org_id=$1 ORDER BY name", org)
        placed, unplaceable, non_sec = {}, [], 0
        for cl in classes:
            if cl["section_id"] != sec:
                non_sec += 1
                continue
            y = _year_of(cl["name"], cl["level"])
            if y:
                placed[cl["id"]] = (cl["name"], y)
            else:
                unplaceable.append(cl["name"])
        print(f"    Secondary classes:   {len(placed) + len(unplaceable)}")
        print(f"    placed in a year:    {len(placed)}")
        print(f"    UNPLACEABLE:         {len(unplaceable)} {unplaceable or ''}")
        print(f"    (non-Secondary classes ignored: {non_sec})")

        print("\n[3] PER CLASS — WHICH OF ITS CURRENT SUBJECTS WOULD BE REFUSED?")
        print("    'current' = the class has a mark, enrolment or timetable row")
        print("    for that subject. Refused = not in that year's list.")
        print(f"      {'class':16} {'year':9} {'allow':6} {'REFUSED':8} refused subjects")
        tot_allowed = tot_refused = 0
        blocked = []
        for cid, (cname, year) in sorted(placed.items(), key=lambda kv: kv[1][0]):
            rows = await c.fetch("""
                SELECT DISTINCT s.name
                  FROM subjects s
                 WHERE s.org_id = $1
                   AND (
                        EXISTS (SELECT 1
                                  FROM student_assessment_scores m
                                  JOIN students st ON st.id = m.student_id
                                 WHERE m.subject_id = s.id
                                   AND st.class_id = $2)
                     OR EXISTS (SELECT 1
                                  FROM student_subject_enrollments e
                                  JOIN students st2 ON st2.id = e.student_id
                                 WHERE e.subject_id = s.id
                                   AND st2.class_id = $2)
                     OR EXISTS (SELECT 1
                                  FROM timetables t
                                 WHERE t.subject_id = s.id
                                   AND t.class_id = $2)
                       )
                 ORDER BY s.name""", org, cid)
            current = sorted(r["name"] for r in rows)
            allowed_set = set(YEAR_SUBJECTS[year])
            refused = [n for n in current if n not in allowed_set]
            tot_allowed += len(current) - len(refused)
            tot_refused += len(refused)
            if refused:
                blocked.append(cname)
            print(f"      {cname[:15]:16} {year:9} {len(current) - len(refused):<6} "
                  f"{len(refused):<8} {', '.join(refused) or '-'}")
        print(f"\n    totals: allowed {tot_allowed}   REFUSED {tot_refused}")
        print(f"    classes with at least one refused subject: {len(blocked)}")

        print("\n[4] HOW MUCH DATA SITS OUTSIDE THE LISTS?")
        print("    (the number that decides whether a gate is safe to arm)")
        marks_out = enrol_out = tt_out = 0
        for cid, (cname, year) in placed.items():
            allowed = YEAR_SUBJECTS[year]
            marks_out += await c.fetchval("""
                SELECT count(*) FROM student_assessment_scores m
                  JOIN students st ON st.id = m.student_id
                  JOIN subjects s  ON s.id = m.subject_id
                 WHERE st.class_id = $1 AND NOT (s.name = ANY($2::text[]))""",
                cid, allowed)
            enrol_out += await c.fetchval("""
                SELECT count(*) FROM student_subject_enrollments e
                  JOIN students st ON st.id = e.student_id
                  JOIN subjects s  ON s.id = e.subject_id
                 WHERE st.class_id = $1 AND NOT (s.name = ANY($2::text[]))""",
                cid, allowed)
            tt_out += await c.fetchval("""
                SELECT count(*) FROM timetables t
                  JOIN subjects s ON s.id = t.subject_id
                 WHERE t.class_id = $1 AND NOT (s.name = ANY($2::text[]))""",
                cid, allowed)
        print(f"    marks outside its year's list:      {marks_out}")
        print(f"    enrolments outside its year's list: {enrol_out}")
        print(f"    timetable rows outside:             {tt_out}")
        print("\n    Any non-zero number is work to reconcile BEFORE a gate —")
        print("    not a reason to skip the gate.")

        print("\n[5] SCHEMA (unchanged — this script writes nothing)")
        print(f"    alembic_version: "
              f"{await c.fetchval('SELECT version_num FROM alembic_version')}")
        print("=" * 78)
    finally:
        await c.close()


if __name__ == "__main__":
    # Guarded so `_year_of` and the lists can be imported and checked without
    # opening a connection — the year matcher is the one place a silent bug
    # could hide ("Year 1" must not swallow "Year 12"), so it must be testable.
    asyncio.run(main())
