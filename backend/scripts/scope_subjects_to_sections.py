"""Give every subject a section, split the shared ones, and load Educare's real
catalogues.

    python scripts/scope_subjects_to_sections.py <DSN>            dry run
    python scripts/scope_subjects_to_sections.py <DSN> --write    apply
    python scripts/scope_subjects_to_sections.py <DSN> --remove <manifest.json>

Runs AFTER migration 137 (which adds `subjects.section_id`) and BEFORE 138
(which tightens it to NOT NULL).

WHY A SCRIPT AND NOT A MIGRATION. This creates subject rows and repoints marks
between them. That is data work: it needs a backup verified by content, a
manifest of every id it touches, and a `--remove` that puts things back. A
migration can do none of those.

FOUR OPERATIONS, in one transaction:

  1. BACKFILL. Each existing subject takes the section its rows already live in.
     Nothing is guessed: a mark hangs off a student, a student off a class, a
     class off a section, and a timetable row carries a class directly. Verified
     against production — 0 marks, 0 enrolments and 0 timetable rows fail to
     resolve a section.

  2. SPLIT. Only `Mathematics` and `English Language` hold rows in more than one
     section. The existing row KEEPS the section with the most rows (Secondary
     for both), so all 1,080 marks stay on the id they are already on and NOT ONE
     mark changes subject_id. A new row is created for Primary and only Primary's
     192 rows per subject are repointed — an UPDATE, never a delete-and-recreate,
     so nothing can be lost in the move.

  3. RENAMES. Six subjects we created under names Educare spells differently.
     Without these each would sit beside a fresh duplicate with its enrolments
     stranded on the orphan:

         Art & Design      -> Arts & Design        (Primary)
         Computer Studies  -> Computing            (Primary)
         French            -> French Language      (Primary)
         Non-Verbal Skills -> NVS                  (Primary)
         Home Maker        -> Humanities           (Primary)
         English Language  -> English studies      (Secondary, after the split)

     `Home Maker` was a misreading of Educare's abbreviated "Hm" header, which is
     Humanities; Home economics exists only at Secondary. Confirmed with the
     school. Like every rename here it is a LABEL change — the id is untouched,
     so its 180 enrolments and 12 timetable rows stay attached.

  4. FRESH. The 56 subjects Educare has that we do not.

THE ARITHMETIC IS THE CHECK. 21 existing + 2 split + 56 fresh = 79, which is
exactly Educare's own total (9 + 21 + 49). If the plan is wrong, it does not add
up, and this script asserts that it does before committing.

DEPARTMENTS. Secondary's come from Educare's own column. Early Years and Primary
get NULL, because Educare shows no department for those levels — inventing one
would repeat the mistake just corrected for Secondary, where ten invented
departments were replaced by Educare's real three.
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import asyncpg

MANIFEST_DIR = os.environ.get("FAIRVIEW_BACKUPS", r"C:\Users\SHAMMAH\fairview-backups")
BACKUP_TABLES = ["subjects", "student_assessment_scores",
                 "student_subject_enrollments", "timetables"]

EARLY = ["Mathematics", "Communication, Language and Literacy",
         "Understanding the World",
         "Personal, Social and Emotional Development", "Rhymes",
         "Practical Life Skills", "Expressive Art and Design",
         "Physical Development.", "Humanities"]

PRIMARY = ["Mathematics", "English Language", "Verbal Reasoning",
           "Quantitative Reasoning", "NVS", "Computing", "Arts & Design",
           "French Language", "Hand Writing", "Music", "Religious Studies",
           "Science", "Physical Education", "Global Perspectives", "Geography",
           "Diction", "Phonics", "Reading", "Humanities", "Sport Activities",
           "Prevocational Studies"]

# (title, department) — department None where Educare shows N/A
SECONDARY = [
    ("English studies", "Language"), ("Mathematics", "Science"),
    ("L S Biology", "Science"), ("LS Chemistry", "Science"),
    ("LS Physics", "Science"), ("Basic Technology", "Science"),
    ("Business studies", "Art and Business"), ("Agricultural science", "Science"),
    ("Digital Technology", "Science"), ("Social studies", "Art and Business"),
    ("Civic education", "Art and Business"), ("Music", "Art and Business"),
    ("Cultural and creative arts", "Art and Business"),
    ("Home economics", "Science"), ("Hausa", "Language"), ("Igbo", "Language"),
    ("Yoruba", "Language"), ("C. R. S.", "Art and Business"),
    ("French", "Language"), ("PHE", "Science"), ("I. R. S.", "Art and Business"),
    ("Security Education", "Art and Business"), ("IXL Math Prep", "Science"),
    ("Biology", "Science"), ("Chemistry", "Science"), ("Physics", "Science"),
    ("Economics", "Art and Business"), ("Marketing", "Art and Business"),
    ("Government", "Art and Business"), ("Geography", "Science"),
    ("Accounting", "Art and Business"), ("Further mathematics", "Science"),
    ("Technical drawing", "Science"), ("Catering and Craft practice", "Science"),
    ("Visual Arts", "Art and Business"), ("Literature in English", "Language"),
    ("Commerce", "Art and Business"), ("History", "Art and Business"),
    ("Sociology", "Art and Business"), ("Reading Time", None),
    ("REHAERSAL", None), ("Intervention Class", "Language"),
    ("Fashion Design And Garment Making", "Art and Business"),
    ("Livestock Farming", "Science"),
    ("Computer Hardware And GSM Repairs", "Science"),
    ("Social And Citizenship Studies", "Art and Business"),
    ("Citizenship And Heritage Studies", "Art and Business"),
    ("Skill Aquisition", None), ("JAMB / WAEC Practice", None),
]

# (our name, section it ends up in) -> Educare's name
RENAMES = {
    ("Art & Design", "Primary"): "Arts & Design",
    ("Computer Studies", "Primary"): "Computing",
    ("French", "Primary"): "French Language",
    ("Non-Verbal Skills", "Primary"): "NVS",
    ("Home Maker", "Primary"): "Humanities",
    ("English Language", "Secondary"): "English studies",
}

EDUCARE_TOTAL = len(EARLY) + len(PRIMARY) + len(SECONDARY)   # 79


def _dsn() -> str:
    for a in sys.argv[1:]:
        if not a.startswith("--") and "://" in a:
            return a
    env = os.environ.get("DATABASE_URL", "").strip()
    if env:
        return env
    sys.exit("Pass the DSN as the first argument, or set DATABASE_URL.")


async def _backup(c, stamp: str) -> str:
    """Verified BY CONTENT, not by exit code: every file is re-opened and its
    rows counted against the live table."""
    d = os.path.join(MANIFEST_DIR, f"scope_subjects_{stamp}")
    os.makedirs(d, exist_ok=True)
    live, ok = {}, True
    for t in BACKUP_TABLES:
        rows = await c.fetch(f"SELECT * FROM {t}")
        live[t] = len(rows)
        with io.open(os.path.join(d, f"{t}.csv"), "w", encoding="utf-8",
                     newline="") as fh:
            if rows:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                for r in rows:
                    w.writerow({k: ("" if v is None else str(v))
                                for k, v in dict(r).items()})
    for t in BACKUP_TABLES:
        p = os.path.join(d, f"{t}.csv")
        with io.open(p, encoding="utf-8", newline="") as fh:
            n = sum(1 for _ in csv.DictReader(fh))
        good = n == live[t]
        ok = ok and good
        print(f"    {'OK  ' if good else 'FAIL'} {t:30} file={n:6} live={live[t]:6}")
    if not ok:
        raise RuntimeError("BACKUP FAILED — do not proceed")
    io.open(os.path.join(d, "VERIFIED.txt"), "w", encoding="utf-8").write(
        f"verified {stamp}\n" + "\n".join(f"{t}: {live[t]}" for t in BACKUP_TABLES))
    return d


async def _remove(dsn: str, path: str) -> None:
    man = json.load(open(path, encoding="utf-8"))
    c = await asyncpg.connect(dsn, timeout=180, command_timeout=900, ssl="require")
    tx = c.transaction()
    await tx.start()
    try:
        # repoint moved rows back to the subject they came from
        for mv in man["repointed"]:
            await c.execute(
                f"UPDATE {mv['table']} SET subject_id = $1 WHERE id = ANY($2::varchar[])",
                mv["from_subject"], mv["ids"])
        await c.execute("DELETE FROM subjects WHERE id = ANY($1::varchar[])",
                        man["created"])
        for r in man["renamed"]:
            await c.execute("UPDATE subjects SET name = $1 WHERE id = $2",
                            r["from"], r["id"])
        for b in man["backfilled"]:
            await c.execute("UPDATE subjects SET section_id = $1 WHERE id = $2",
                            b["from"], b["id"])
        print(f"  reverted: {len(man['created'])} created, "
              f"{len(man['renamed'])} renamed, {len(man['backfilled'])} backfilled, "
              f"{sum(len(m['ids']) for m in man['repointed'])} repointed")
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
    c = await asyncpg.connect(dsn, timeout=180, command_timeout=900, ssl="require")
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")

    print("SCOPE SUBJECTS TO SECTIONS — "
          + ("REAL WRITE" if write else "DRY RUN (writes nothing)"))

    if write:
        print("\n[0] BACKUP, verified by content")
        print("    " + await _backup(c, stamp))

    org = await c.fetchval("SELECT id FROM organizations LIMIT 1")
    sections = {r["name"]: r["id"] for r in await c.fetch(
        "SELECT id, name FROM school_sections WHERE org_id = $1", org)}
    for need in ("Early Years", "Primary", "Secondary"):
        if need not in sections:
            sys.exit(f"section {need!r} is missing")

    man = {"created_at": now.isoformat(), "backfilled": [], "created": [],
           "renamed": [], "repointed": []}

    tx = c.transaction()
    await tx.start()
    try:
        # ── 1. where does each existing subject's work live? ─────────────────
        print("\n[1] BACKFILL")
        subs = await c.fetch(
            "SELECT id, name, section_id FROM subjects WHERE org_id=$1 ORDER BY name",
            org)
        spread = {}
        for s in subs:
            per = await c.fetch("""
                SELECT sec.name section,
                       count(DISTINCT m.id) marks, count(DISTINCT e.id) enrol,
                       count(DISTINCT t.id) tt
                  FROM school_sections sec
                  JOIN school_classes cl ON cl.section_id = sec.id
                  LEFT JOIN students st ON st.class_id = cl.id
                  LEFT JOIN student_assessment_scores m
                         ON m.student_id = st.id AND m.subject_id = $2
                  LEFT JOIN student_subject_enrollments e
                         ON e.student_id = st.id AND e.subject_id = $2
                  LEFT JOIN timetables t ON t.class_id = cl.id AND t.subject_id = $2
                 WHERE sec.org_id = $1 GROUP BY sec.name
                HAVING count(DISTINCT m.id)+count(DISTINCT e.id)
                      +count(DISTINCT t.id) > 0
                 ORDER BY sec.name""", org, s["id"])
            spread[s["id"]] = {"name": s["name"], "old_section": s["section_id"],
                               "per": [dict(p) for p in per]}

        for sid, info in sorted(spread.items(), key=lambda kv: kv[1]["name"]):
            if not info["per"]:
                sys.exit(f"{info['name']!r} has no rows anywhere — cannot place it")
            best = max(info["per"],
                       key=lambda x: (x["marks"] + x["enrol"] + x["tt"], x["section"]))
            info["keeps"] = best["section"]
            man["backfilled"].append({"id": sid, "name": info["name"],
                                      "from": info["old_section"],
                                      "to": best["section"]})
            await c.execute("UPDATE subjects SET section_id=$1, updated_at=$2 "
                            "WHERE id=$3", sections[best["section"]], now, sid)
            tag = " (majority of 2)" if len(info["per"]) > 1 else ""
            print(f"    {info['name']:26} -> {best['section']}{tag}")

        # ── 2. split the shared ones ────────────────────────────────────────
        print("\n[2] SPLIT")
        moved_marks = 0
        for sid, info in sorted(spread.items(), key=lambda kv: kv[1]["name"]):
            if len(info["per"]) < 2:
                continue
            for x in info["per"]:
                if x["section"] == info["keeps"]:
                    continue
                new_id = str(uuid.uuid4())
                # The new row takes Educare's name for that section when it
                # differs — Primary's "English Language" beside Secondary's
                # "English studies" are two different Educare subjects.
                new_name = info["name"]
                dept = None
                if x["section"] == "Secondary":
                    dept = dict(SECONDARY).get(new_name)
                await c.execute("""
                    INSERT INTO subjects (id, name, code, description, department,
                           credit_hours, is_active, teacher_id, teacher_name,
                           section_id, org_id, created_at, updated_at)
                    VALUES ($1,$2,NULL,NULL,$3,1,true,NULL,NULL,$4,$5,$6,$6)""",
                    new_id, new_name, dept, sections[x["section"]], org, now)
                man["created"].append(new_id)

                n_moved = 0
                for table, join in (
                    ("student_assessment_scores",
                     "JOIN students st ON st.id = {t}.student_id "
                     "JOIN school_classes cl ON cl.id = st.class_id"),
                    ("student_subject_enrollments",
                     "JOIN students st ON st.id = {t}.student_id "
                     "JOIN school_classes cl ON cl.id = st.class_id"),
                    ("timetables",
                     "JOIN school_classes cl ON cl.id = {t}.class_id"),
                ):
                    ids = [r["id"] for r in await c.fetch(f"""
                        SELECT {table}.id FROM {table}
                          {join.format(t=table)}
                         WHERE {table}.subject_id = $1 AND cl.section_id = $2""",
                        sid, sections[x["section"]])]
                    if ids:
                        await c.execute(
                            f"UPDATE {table} SET subject_id=$1 "
                            f"WHERE id = ANY($2::varchar[])", new_id, ids)
                        man["repointed"].append({"table": table,
                                                 "from_subject": sid,
                                                 "to_subject": new_id, "ids": ids})
                        n_moved += len(ids)
                        if table == "student_assessment_scores":
                            moved_marks += len(ids)
                print(f"    {info['name']:26} new {x['section']} row, "
                      f"{n_moved} rows repointed")
        print(f"    marks that changed subject_id: {moved_marks}")

        # ── 3. renames ──────────────────────────────────────────────────────
        print("\n[3] RENAMES")
        for (old_name, sec), new_name in RENAMES.items():
            row = await c.fetchrow("""
                SELECT s.id, s.name FROM subjects s
                 WHERE s.org_id=$1 AND s.name=$2 AND s.section_id=$3""",
                org, old_name, sections[sec])
            if row is None:
                print(f"    {old_name!r} in {sec}: absent, skipped")
                continue
            clash = await c.fetchval("""
                SELECT count(*) FROM subjects
                 WHERE org_id=$1 AND name=$2 AND section_id=$3""",
                org, new_name, sections[sec])
            if clash:
                sys.exit(f"{new_name!r} already exists in {sec}")
            man["renamed"].append({"id": row["id"], "from": old_name,
                                   "to": new_name, "section": sec})
            await c.execute("UPDATE subjects SET name=$1, updated_at=$2 WHERE id=$3",
                            new_name, now, row["id"])
            print(f"    {sec:12} {old_name!r} -> {new_name!r} (id unchanged)")

        # ── 4. the subjects Educare has and we do not ───────────────────────
        print("\n[4] FRESH SUBJECTS")
        wanted = {"Early Years": [(n, None) for n in EARLY],
                  "Primary": [(n, None) for n in PRIMARY],
                  "Secondary": SECONDARY}
        for sec, items in wanted.items():
            have = {r["name"] for r in await c.fetch(
                "SELECT name FROM subjects WHERE org_id=$1 AND section_id=$2",
                org, sections[sec])}
            fresh = [(n, d) for n, d in items if n not in have]
            rows = []
            for n, d in fresh:
                nid = str(uuid.uuid4())
                rows.append((nid, n, d, sections[sec], org, now))
                man["created"].append(nid)
            if rows:
                await c.executemany("""
                    INSERT INTO subjects (id, name, code, description, department,
                           credit_hours, is_active, teacher_id, teacher_name,
                           section_id, org_id, created_at, updated_at)
                    VALUES ($1,$2,NULL,NULL,$3,1,true,NULL,NULL,$4,$5,$6,$6)""",
                    rows)
            print(f"    {sec:12} created {len(rows)} (now {len(have) + len(rows)}, "
                  f"Educare has {len(items)})")

        # ── verify INSIDE the transaction ───────────────────────────────────
        print("\n[5] VERIFY BEFORE COMMIT")
        nulls = await c.fetchval(
            "SELECT count(*) FROM subjects WHERE org_id=$1 AND section_id IS NULL", org)
        print(f"    subjects with no section: {nulls}")
        assert nulls == 0, "migration 138 would fail on these"

        total = await c.fetchval("SELECT count(*) FROM subjects WHERE org_id=$1", org)
        print(f"    catalogue total: {total} (Educare's own: {EDUCARE_TOTAL})")
        assert total == EDUCARE_TOTAL, (
            f"the arithmetic does not close: {total} != {EDUCARE_TOTAL}. The "
            f"mapping is incomplete — a duplicate or a missing rename.")

        for sec, items in wanted.items():
            n = await c.fetchval(
                "SELECT count(*) FROM subjects WHERE org_id=$1 AND section_id=$2",
                org, sections[sec])
            print(f"    {sec:12} {n} (Educare {len(items)})")
            assert n == len(items)

        marks = await c.fetchval("SELECT count(*) FROM student_assessment_scores")
        enrol = await c.fetchval("SELECT count(*) FROM student_subject_enrollments")
        tt = await c.fetchval("SELECT count(*) FROM timetables")
        print(f"    marks={marks} enrolments={enrol} timetables={tt} "
              f"(totals must be unchanged — rows were repointed, never deleted)")
        assert marks == 5399 and enrol == 4140 and tt == 376

        orphan = await c.fetchval("""
            SELECT count(*) FROM student_assessment_scores s
             WHERE NOT EXISTS (SELECT 1 FROM subjects su WHERE su.id = s.subject_id)""")
        print(f"    marks pointing at a missing subject: {orphan}")
        assert orphan == 0

        # every mark must sit on a subject whose section matches its pupil's
        mismatch = await c.fetchval("""
            SELECT count(*) FROM student_assessment_scores s
              JOIN subjects su ON su.id = s.subject_id
              JOIN students st ON st.id = s.student_id
              JOIN school_classes cl ON cl.id = st.class_id
             WHERE su.section_id IS DISTINCT FROM cl.section_id""")
        print(f"    marks whose subject's section != the pupil's section: {mismatch}")
        assert mismatch == 0, "the split left a mark on the wrong section's subject"

        if not write:
            await tx.rollback()
            print("\nDRY RUN — rolled back. Re-run with --write to apply.")
            return

        p = os.path.join(MANIFEST_DIR, f"scope_subjects_manifest_{stamp}.json")
        json.dump(man, open(p, "w", encoding="utf-8"), indent=1)
        back = json.load(open(p, encoding="utf-8"))
        assert len(back["created"]) == len(man["created"])
        assert len(back["repointed"]) == len(man["repointed"])
        print(f"\n    manifest written and re-read: {p}")
        print(f"      backfilled {len(man['backfilled'])}, created "
              f"{len(man['created'])}, renamed {len(man['renamed'])}, "
              f"repointed {sum(len(m['ids']) for m in man['repointed'])} rows")

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
