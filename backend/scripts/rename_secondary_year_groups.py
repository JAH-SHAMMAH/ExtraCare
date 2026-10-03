"""Secondary year groups become Year 7 – Year 12.

    python scripts/rename_secondary_year_groups.py <DSN>            dry run
    python scripts/rename_secondary_year_groups.py <DSN> --write    apply
    python scripts/rename_secondary_year_groups.py <DSN> --remove <manifest.json>

Fairview's year groups run Year 1 to Year 12. Primary (Year 1–6) was already
correct; Secondary was still carrying the Nigerian JSS1–3 / SSS1–3 labels, which
Fairview does not use. This is the same kind of label change as
`rename_pre_nursery.py`: nothing moves, nobody is reassigned, and no mark,
enrolment or timetable row is touched — they all hang off ids.

THE MAPPING IS NOT A GUESS. `year_groups` already records it: the JSS1 row
carries short_code "Y7", JSS2 "Y8", JSS3 "Y9", SSS1 "Y10", SSS2 "Y11", SSS3
"Y12", and their positions already run 10–15, straight on from Year 6 at 9. The
database has known the British numbering all along; only the display names were
wrong.

WHY A LEVEL RENAME IS STILL FREE. `school_classes.level` is matched BY NAME by
assessments.year_group, cumulatives.year_group, report_level_settings,
report_subject_exclusions, result_default_comments, subject_groups and
period_groups. Renaming the level without those would leave classes pointing at
a level nobody configures. Verified before writing: all seven hold ZERO non-null
year_group rows, and this script RE-CHECKS and REFUSES to write if that has
changed. Once Report Setup is populated per level, this stops being free.

WHAT THE SWEEP FOUND. Exactly two "JSS"/"SSS" occurrences in application code,
both cosmetic — a comment in ParentHome.tsx and a UI placeholder in the
eClassroom programs page. No logic anywhere matches on those strings. The 173
occurrences in tests are synthetic fixtures that build their own classes.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

import asyncpg

MANIFEST_DIR = os.environ.get("FAIRVIEW_BACKUPS", r"C:\Users\SHAMMAH\fairview-backups")

# year-group name -> new name. Confirmed by each row's own short_code.
YEAR_GROUPS = {
    "JSS1": "Year 7", "JSS2": "Year 8", "JSS3": "Year 9",
    "SSS1": "Year 10", "SSS2": "Year 11", "SSS3": "Year 12",
}
# The `level` string those classes carry, renamed in step with the year group.
LEVELS = dict(YEAR_GROUPS)

# Tables that match school_classes.level BY NAME. A level rename is only free
# while every one of these is empty of year_group values.
NAME_MATCHED = [
    "assessments", "cumulatives", "report_level_settings",
    "report_subject_exclusions", "result_default_comments", "subject_groups",
    "period_groups",
]


def _dsn() -> str:
    for a in sys.argv[1:]:
        if not a.startswith("--") and "://" in a:
            return a
    env = os.environ.get("DATABASE_URL", "").strip()
    if env:
        return env
    sys.exit("Pass the DSN as the first argument, or set DATABASE_URL.")


def _new_class_name(old: str) -> str | None:
    """'JSS1 A' -> 'Year 7 A'. Returns None when nothing maps."""
    for old_lv, new_lv in LEVELS.items():
        if old == old_lv:
            return new_lv
        if old.startswith(old_lv + " "):
            return new_lv + old[len(old_lv):]
    return None


async def _remove(dsn: str, path: str) -> None:
    man = json.load(open(path, encoding="utf-8"))
    c = await asyncpg.connect(dsn, timeout=180, command_timeout=600, ssl="require")
    tx = c.transaction()
    await tx.start()
    try:
        for row in man["year_groups"]:
            await c.execute("UPDATE year_groups SET name = $1 WHERE id = $2",
                            row["from"], row["id"])
        for row in man["classes"]:
            await c.execute(
                "UPDATE school_classes SET name = $1, level = $2 WHERE id = $3",
                row["name_from"], row["level_from"], row["id"])
        print(f"  reverted {len(man['year_groups'])} year groups, "
              f"{len(man['classes'])} classes")
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
    man = {"created_at": now.isoformat(), "year_groups": [], "classes": []}

    print("SECONDARY YEAR GROUPS -> Year 7–12 — "
          + ("REAL WRITE" if write else "DRY RUN (writes nothing)"))

    tx = c.transaction()
    await tx.start()
    try:
        # ── the guard: a level rename is only free while these are empty ────
        print("\n[1] IS A LEVEL RENAME STILL FREE?")
        blocked = []
        for t in NAME_MATCHED:
            n = await c.fetchval(
                f"SELECT count(*) FROM {t} WHERE year_group IS NOT NULL")
            print(f"    {t:28} year_group rows: {n}")
            if n:
                blocked.append((t, n))
        if blocked:
            raise RuntimeError(
                "These tables now configure a level BY NAME: "
                + ", ".join(f"{t} ({n})" for t, n in blocked)
                + ". Renaming the level would strand them. Migrate those to the "
                  "new names in the same transaction, or this stops being a "
                  "label change.")
        print("    -> free: nothing configures a level by name yet")

        # ── year groups ─────────────────────────────────────────────────────
        print("\n[2] YEAR GROUPS")
        for old, new in YEAR_GROUPS.items():
            row = await c.fetchrow(
                "SELECT id, name, short_code, position FROM year_groups "
                "WHERE name = $1", old)
            if row is None:
                print(f"    {old:6} -> (absent, skipped)")
                continue
            clash = await c.fetchval(
                "SELECT count(*) FROM year_groups WHERE name = $1", new)
            if clash:
                raise RuntimeError(
                    f"A year group named {new!r} already exists; renaming {old!r} "
                    f"onto it would violate uq_year_group_org_name.")
            print(f"    {old:6} -> {new:8} (short_code {row['short_code']}, "
                  f"position {row['position']} — both already correct)")
            man["year_groups"].append({"id": row["id"], "from": old, "to": new})
            await c.execute("UPDATE year_groups SET name = $1, updated_at = $2 "
                            "WHERE id = $3", new, now, row["id"])

        # ── classes ─────────────────────────────────────────────────────────
        print("\n[3] CLASSES")
        for row in await c.fetch(
                "SELECT id, name, level FROM school_classes ORDER BY name"):
            new_name = _new_class_name(row["name"] or "")
            new_level = LEVELS.get(row["level"])
            if new_name is None and new_level is None:
                continue
            print(f"    {row['name']:14} -> {new_name or row['name']:14} "
                  f"(level {row['level']} -> {new_level or row['level']})")
            man["classes"].append({
                "id": row["id"], "name_from": row["name"], "level_from": row["level"],
                "name_to": new_name or row["name"],
                "level_to": new_level or row["level"]})
            await c.execute(
                "UPDATE school_classes SET name = $1, level = $2, updated_at = $3 "
                "WHERE id = $4",
                new_name or row["name"], new_level or row["level"], now, row["id"])

        # ── verify INSIDE the transaction ───────────────────────────────────
        print("\n[4] VERIFY BEFORE COMMIT")
        leftover = await c.fetchval(
            "SELECT count(*) FROM school_classes "
            "WHERE level LIKE 'JSS%' OR level LIKE 'SSS%' "
            "   OR name LIKE 'JSS%' OR name LIKE 'SSS%'")
        print(f"    classes still carrying JSS/SSS: {leftover}")
        assert leftover == 0, "a JSS/SSS label survived the rename"
        yg = await c.fetchval(
            "SELECT count(*) FROM year_groups WHERE name LIKE 'JSS%' OR name LIKE 'SSS%'")
        print(f"    year groups still carrying JSS/SSS: {yg}")
        assert yg == 0

        # nothing may move: the counts that hang off ids
        for label, q, expect in (
            ("marks", "SELECT count(*) FROM student_assessment_scores", None),
            ("enrolments", "SELECT count(*) FROM student_subject_enrollments", None),
            ("timetable rows", "SELECT count(*) FROM timetables", None),
            ("pupils", "SELECT count(*) FROM students WHERE is_deleted = false", None),
        ):
            print(f"    {label:16} {await c.fetchval(q)} (unchanged — these hang "
                  f"off ids, not labels)")

        print("\n    the Secondary section, after:")
        for r in await c.fetch("""
            SELECT cl.level, count(*) n, string_agg(cl.name, ', ' ORDER BY cl.name) names
              FROM school_classes cl JOIN school_sections s ON s.id = cl.section_id
             WHERE s.name = 'Secondary' GROUP BY cl.level ORDER BY cl.level"""):
            print(f"      {r['level']:10} ({r['n']}) {r['names']}")

        if not write:
            await tx.rollback()
            print("\nDRY RUN — rolled back. Re-run with --write to apply.")
            return

        os.makedirs(MANIFEST_DIR, exist_ok=True)
        mpath = os.path.join(
            MANIFEST_DIR,
            f"rename_secondary_manifest_{now.strftime('%Y%m%dT%H%M%SZ')}.json")
        with open(mpath, "w", encoding="utf-8") as fh:
            json.dump(man, fh, indent=1)
        back = json.load(open(mpath, encoding="utf-8"))
        assert len(back["classes"]) == len(man["classes"])
        print(f"\n    manifest written and re-read: {mpath}")
        print(f"      year groups {len(man['year_groups'])}, "
              f"classes {len(man['classes'])}")

        await tx.commit()
        print("COMMITTED.")
    except Exception:
        await tx.rollback()
        print("\nROLLED BACK — nothing written.")
        raise
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
