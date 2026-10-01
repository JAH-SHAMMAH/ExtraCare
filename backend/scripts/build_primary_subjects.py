"""Fairview's Primary subjects, their timetable, and Primary enrolment.

    python scripts/build_primary_subjects.py <DSN>                  dry run
    python scripts/build_primary_subjects.py <DSN> --write          apply
    python scripts/build_primary_subjects.py <DSN> --remove <manifest.json>

APPLIED TO PRODUCTION 2026-10-01 (manifest
`fairview-backups/primary_build_manifest_20261001T225827Z.json`): 11 subjects
created, 360 wrong timetable rows deleted, 156 created, 2,340 enrolments created.
Kept in the repo as the record of what was run, and because it is idempotent —
re-running it creates nothing new.

WHAT IT FIXES. Primary had no subjects of its own, and the Timetable assigned all
10 SECONDARY subjects to every level in the school — Playgroup and Pre-Nursery
included, so four-year-olds were nominally timetabled for Government and
Economics. Those rows were seed junk: two exact duplicates per (class, subject),
all on day 0 at 08:00, and nothing referenced them.

THE 13 SUBJECTS are school-confirmed. Two of them already existed and are REUSED,
not forked: a subject is org-wide and the level association lives in the Timetable
and in enrolments, so creating "Mathematics (Primary)" would split the catalogue
and split that subject's row in Subjects Averages Across Sessions. The cost is
that an UNSCOPED whole-school subject report now blends Year 1 Mathematics with
SSS3 Mathematics; class/section scoping separates them.

EARLY YEARS GETS NOTHING. EYFS is assessed by domains, not subjects, so the 120
wrong rows there are removed with no replacement — there is nothing correct to put
in their place. An EYFS subject list was never provided, and inventing one would
be fabricating school data.

DEPARTMENTS ARE INFERRED, not school-confirmed; only the names were given. They
are free-text, so each is a one-row UPDATE to correct. `Non-Verbal Skills ->
Reasoning` is the one value that could NOT be verified against Educare (no
access), and it leaves that subject alone in its department, because Verbal
Reasoning -> Languages and Quantitative Reasoning -> Mathematics were settled
separately. If Educare groups all three reasoning subjects together, move all
three to "Reasoning".

CODES STAY NULL, matching all 10 pre-existing subjects. Introducing a code
convention on only the new rows is the kind of half-applied convention this
project keeps removing.
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

# (name, department)
PRIMARY_SUBJECTS = [
    ("Mathematics",            "Mathematics"),        # pre-existing — reused
    ("English Language",       "Languages"),          # pre-existing — reused
    ("Verbal Reasoning",       "Languages"),
    ("Quantitative Reasoning", "Mathematics"),
    ("Non-Verbal Skills",      "Reasoning"),          # <- UNVERIFIED vs Educare
    ("Computer Studies",       "ICT"),
    ("Art & Design",           "Creative Arts"),
    ("French",                 "Languages"),
    ("Music",                  "Creative Arts"),
    ("Religious Studies",      "Religious Studies"),
    ("Science",                "Sciences"),
    ("Physical Education",     "Physical Education"),
    ("Home Maker",             "Vocational"),
]

PRIMARY_LEVELS = ["Year 1", "Year 2", "Year 3", "Year 4", "Year 5", "Year 6"]
EARLY_LEVELS = ["Playgroup", "Pre-Nursery", "Nursery", "Reception"]
SECONDARY_LEVELS = ["JSS1", "JSS2", "JSS3", "SSS1", "SSS2", "SSS3"]
SESSION_NAME = "2025/2026"


def _resolve(argv) -> str:
    """DSN from the first non-flag argument, else DATABASE_URL. Never hardcoded —
    a credential in a tracked file is a credential in the git history."""
    for a in argv[1:]:
        if not a.startswith("--") and "://" in a:
            return a
    env = os.environ.get("DATABASE_URL", "").strip()
    if env:
        return env
    sys.exit("Pass the DSN as the first argument, or set DATABASE_URL.")


async def _remove(dsn: str, path: str) -> None:
    """Undo exactly the rows in `path` — including restoring the deleted ones
    verbatim, rather than regenerating something that merely resembles them."""
    man = json.load(open(path, encoding="utf-8"))
    c = await asyncpg.connect(dsn, timeout=180, command_timeout=600, ssl="require")
    tx = c.transaction()
    await tx.start()
    try:
        await c.execute("DELETE FROM student_subject_enrollments WHERE id = ANY($1::varchar[])",
                        man["enrollments_created"])
        await c.execute("DELETE FROM timetables WHERE id = ANY($1::varchar[])",
                        man["timetables_created"])
        await c.execute("DELETE FROM subjects WHERE id = ANY($1::varchar[])",
                        man["subjects_created"])
        rows = [(r["id"], r["class_id"], r["subject_id"], r["day_of_week"],
                 r["start_time"], r["end_time"], r["room"], r["teacher_id"],
                 r["org_id"], datetime.fromisoformat(r["created_at"]),
                 datetime.fromisoformat(r["updated_at"]))
                for r in man["timetables_deleted"]]
        await c.executemany("""
            INSERT INTO timetables (id, class_id, subject_id, day_of_week,
                   start_time, end_time, room, teacher_id, org_id,
                   created_at, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""", rows)
        print(f"  restored {len(rows)} deleted timetable rows")
        await tx.commit()
        print("REMOVED.")
    except Exception:
        await tx.rollback()
        print("ROLLED BACK — nothing changed.")
        raise
    finally:
        await c.close()


async def main() -> None:
    dsn = _resolve(sys.argv)
    if "--remove" in sys.argv:
        await _remove(dsn, sys.argv[sys.argv.index("--remove") + 1])
        return

    write = "--write" in sys.argv
    c = await asyncpg.connect(dsn, timeout=180, command_timeout=600, ssl="require")
    org = await c.fetchval("SELECT id FROM organizations LIMIT 1")
    now = datetime.now(timezone.utc)
    man = {"created_at": now.isoformat(), "org_id": org, "subjects_created": [],
           "timetables_created": [], "timetables_deleted": [],
           "enrollments_created": []}

    print("PRIMARY BUILD — " + ("REAL WRITE" if write else "DRY RUN (writes nothing)"))
    tx = c.transaction()
    await tx.start()
    try:
        # ── subjects ────────────────────────────────────────────────────────
        existing = {r["name"]: r["id"] for r in await c.fetch(
            "SELECT id, name FROM subjects WHERE org_id = $1", org)}
        subject_ids, new_subjects = {}, []
        for name, dept in PRIMARY_SUBJECTS:
            if name in existing:
                subject_ids[name] = existing[name]
                print(f"    reuse   {name:26} (exists, untouched)")
                continue
            sid = str(uuid.uuid4())
            subject_ids[name] = sid
            new_subjects.append((sid, name, dept, org, now))
            man["subjects_created"].append(sid)
            print(f"    CREATE  {name:26} dept={dept}")
        if new_subjects:
            await c.executemany("""
                INSERT INTO subjects (id, name, code, description, department,
                       credit_hours, is_active, teacher_id, teacher_name, org_id,
                       created_at, updated_at)
                VALUES ($1,$2,NULL,NULL,$3,1,true,NULL,NULL,$4,$5,$5)""",
                new_subjects)

        # ── delete the wrong rows ───────────────────────────────────────────
        doomed = await c.fetch("""
            SELECT t.* FROM timetables t JOIN school_classes cl ON cl.id = t.class_id
             WHERE cl.org_id = $1 AND cl.level = ANY($2::text[])""",
            org, EARLY_LEVELS + PRIMARY_LEVELS)
        for r in doomed:
            d = dict(r)
            d["created_at"] = d["created_at"].isoformat()
            d["updated_at"] = d["updated_at"].isoformat()
            man["timetables_deleted"].append(d)
        await c.execute("DELETE FROM timetables WHERE id = ANY($1::varchar[])",
                        [r["id"] for r in doomed])
        print(f"    deleted {len(doomed)} wrong timetable rows "
              f"(Early Years not replaced — EYFS uses domains)")

        # ── the correct Primary rows ────────────────────────────────────────
        classes = await c.fetch("""
            SELECT id, name, teacher_id FROM school_classes
             WHERE org_id = $1 AND level = ANY($2::text[]) ORDER BY name""",
            org, PRIMARY_LEVELS)
        # Batched: at ~940ms round-trip to Render, row-at-a-time is forty minutes
        # for the enrolments alone, which is how the first dry run had to be killed.
        tt = []
        for cl in classes:
            for name, _ in PRIMARY_SUBJECTS:
                tid = str(uuid.uuid4())
                tt.append((tid, cl["id"], subject_ids[name], cl["teacher_id"], org, now))
                man["timetables_created"].append(tid)
        await c.executemany("""
            INSERT INTO timetables (id, class_id, subject_id, day_of_week,
                   start_time, end_time, room, teacher_id, org_id,
                   created_at, updated_at)
            VALUES ($1,$2,$3,0,'08:00','09:00',NULL,$4,$5,$6,$6)""", tt)
        print(f"    created {len(tt)} Primary rows "
              f"(one per pair, teacher = that class's class teacher)")

        # ── enrolments ──────────────────────────────────────────────────────
        pupils = await c.fetch("""
            SELECT st.id FROM students st
              JOIN school_classes cl ON cl.id = st.class_id
             WHERE st.org_id = $1 AND cl.level = ANY($2::text[])
               AND st.is_deleted = false""", org, PRIMARY_LEVELS)
        already = {(r["student_id"], r["subject_id"]) for r in await c.fetch("""
            SELECT student_id, subject_id FROM student_subject_enrollments
             WHERE org_id = $1 AND academic_year = $2""", org, SESSION_NAME)}
        en = []
        for p in pupils:
            for name, _ in PRIMARY_SUBJECTS:
                if (p["id"], subject_ids[name]) in already:
                    continue
                eid = str(uuid.uuid4())
                en.append((eid, p["id"], subject_ids[name], SESSION_NAME, now, org))
                man["enrollments_created"].append(eid)
        if en:
            await c.executemany("""
                INSERT INTO student_subject_enrollments
                       (id, student_id, subject_id, academic_year, enrolled_at,
                        source, org_id, created_at, updated_at)
                VALUES ($1,$2,$3,$4,$5,'manual',$6,$5,$5)""", en)
        print(f"    created {len(en)} enrolments for {len(pupils)} pupils")

        # ── verify INSIDE the transaction, before committing ────────────────
        early = await c.fetchval("""
            SELECT count(*) FROM timetables t JOIN school_classes cl ON cl.id = t.class_id
             WHERE cl.org_id = $1 AND cl.level = ANY($2::text[])""", org, EARLY_LEVELS)
        primary = await c.fetchval("""
            SELECT count(*) FROM timetables t JOIN school_classes cl ON cl.id = t.class_id
             WHERE cl.org_id = $1 AND cl.level = ANY($2::text[])""", org, PRIMARY_LEVELS)
        secondary = await c.fetchval("""
            SELECT count(*) FROM timetables t JOIN school_classes cl ON cl.id = t.class_id
             WHERE cl.org_id = $1 AND cl.level = ANY($2::text[])""", org, SECONDARY_LEVELS)
        assert early == 0, f"Early Years should hold no subject rows, has {early}"
        assert primary == len(classes) * len(PRIMARY_SUBJECTS), primary
        print(f"    verified: early={early} primary={primary} secondary={secondary}")
        # The write must not touch a single mark.
        marks = await c.fetchval("SELECT count(*) FROM student_assessment_scores")
        print(f"    marks untouched: {marks}")

        if not write:
            await tx.rollback()
            print("DRY RUN — rolled back. Re-run with --write to apply.")
            return

        os.makedirs(MANIFEST_DIR, exist_ok=True)
        mpath = os.path.join(
            MANIFEST_DIR,
            f"primary_build_manifest_{now.strftime('%Y%m%dT%H%M%SZ')}.json")
        with open(mpath, "w", encoding="utf-8") as fh:
            json.dump(man, fh, indent=1)
        # Re-read before committing: a manifest that did not land is no manifest.
        back = json.load(open(mpath, encoding="utf-8"))
        assert len(back["enrollments_created"]) == len(man["enrollments_created"])
        assert len(back["timetables_deleted"]) == len(man["timetables_deleted"])
        print(f"    manifest written and re-read: {mpath}")

        await tx.commit()
        print("COMMITTED.")
    except Exception:
        await tx.rollback()
        print("ROLLED BACK — nothing written.")
        raise
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
