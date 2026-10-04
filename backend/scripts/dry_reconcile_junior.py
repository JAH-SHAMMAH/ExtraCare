"""READ-ONLY diagnostic for the Years 7-9 mismatch. WRITES NOTHING.

DELIBERATELY UNTRACKED - do not `git add`. No credential in this file.

    python scripts/dry_reconcile_junior.py "<DATABASE_URL>"

Answers two things at once:

  (2) WHY 60 TIMETABLE ROWS AND NOT 36. `timetables` is one row per SCHEDULED
      PERIOD - (class_id, subject_id, day_of_week, start_time, end_time) - with
      no unique constraint on (class, subject). A subject taught three times a
      week is three rows, legitimately. So "6 classes x 6 subjects = 36" is not
      the expected count; this prints the actual rows-per-pair distribution so
      the 60 is explained rather than assumed.

  (3) THE PRECONDITIONS a reconciliation plan depends on, none of which can be
      answered from the repo: which terms the marks sit in, whether any report
      for these classes is PUBLISHED (a published card changing retroactively is
      the one genuinely irreversible-feeling outcome), and whether the junior
      counterparts already hold rows that a re-point would collide with.
"""
from __future__ import annotations

import asyncio
import os
import sys

import asyncpg

# The six subjects Educare does not assign to Years 7-9.
FOREIGN = ["Biology", "Chemistry", "Physics", "Economics", "Geography", "Government"]
# Only the science trio has a junior counterpart. The other three have none.
COUNTERPART = {"Biology": "L S Biology", "Chemistry": "LS Chemistry",
               "Physics": "LS Physics"}
NO_COUNTERPART = ["Economics", "Geography", "Government"]
JUNIOR_YEARS = ("Year 7", "Year 8", "Year 9")


def _dsn() -> str:
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    env = os.environ.get("DATABASE_URL", "").strip()
    if env:
        return env
    raise SystemExit('Pass the DSN as argv[1], or set DATABASE_URL.')


def _year_of(name: str) -> str | None:
    for n in (12, 11, 10, 9, 8, 7):
        if f"year {n}" in (name or "").lower():
            return f"Year {n}"
    return None


async def main() -> None:
    c = await asyncpg.connect(_dsn().replace("postgresql+asyncpg://", "postgresql://"),
                              timeout=180, command_timeout=300, ssl="require")
    try:
        org = await c.fetchval("SELECT id FROM organizations LIMIT 1")
        sec = await c.fetchval(
            "SELECT id FROM school_sections WHERE org_id=$1 AND name='Secondary'", org)
        classes = [r for r in await c.fetch(
            "SELECT id, name FROM school_classes WHERE org_id=$1 AND section_id=$2"
            " ORDER BY name", org, sec)]
        junior = [r for r in classes if _year_of(r["name"]) in JUNIOR_YEARS]
        cids = [r["id"] for r in junior]
        print("=" * 78)
        print("YEARS 7-9 RECONCILIATION DIAGNOSTIC - READ ONLY, WRITES NOTHING")
        print("=" * 78)
        print(f"\njunior classes: {len(junior)} -> "
              f"{', '.join(r['name'] for r in junior)}")

        print("\n[A] THE 60 TIMETABLE ROWS - rows per (class, subject) pair")
        rows = await c.fetch("""
            SELECT cl.name AS cls, s.name AS subj, count(*) AS n,
                   count(DISTINCT (t.day_of_week, t.start_time, t.end_time)) AS slots
              FROM timetables t
              JOIN school_classes cl ON cl.id = t.class_id
              JOIN subjects s        ON s.id = t.subject_id
             WHERE t.class_id = ANY($1::varchar[]) AND s.name = ANY($2::text[])
             GROUP BY cl.name, s.name ORDER BY cl.name, s.name""", cids, FOREIGN)
        total = sum(r["n"] for r in rows)
        print(f"    pairs that actually have rows: {len(rows)}  (not necessarily 36)")
        print(f"    total rows:                    {total}")
        print(f"      {'class':16} {'subject':12} {'rows':5} distinct day/time slots")
        for r in rows:
            flag = "  <-- SAME SLOT TWICE" if r["n"] != r["slots"] else ""
            print(f"      {r['cls'][:15]:16} {r['subj'][:11]:12} {r['n']:<5} "
                  f"{r['slots']}{flag}")
        dupes = [r for r in rows if r["n"] != r["slots"]]
        print(f"\n    TRUE DUPLICATES (same class+subject+day+time more than once): "
              f"{len(dupes)}")
        print("    Anything above with rows == slots is a subject timetabled more")
        print("    than once a week, which is normal, not duplication.")

        print("\n[B] MARKS BY SUBJECT - which can be re-pointed, which cannot")
        print(f"      {'subject':12} {'marks':7} {'enrolments':11} counterpart")
        for name in FOREIGN:
            m = await c.fetchval("""
                SELECT count(*) FROM student_assessment_scores x
                  JOIN students st ON st.id = x.student_id
                  JOIN subjects s  ON s.id = x.subject_id
                 WHERE st.class_id = ANY($1::varchar[]) AND s.name = $2""", cids, name)
            e = await c.fetchval("""
                SELECT count(*) FROM student_subject_enrollments en
                  JOIN students st ON st.id = en.student_id
                  JOIN subjects s  ON s.id = en.subject_id
                 WHERE st.class_id = ANY($1::varchar[]) AND s.name = $2""", cids, name)
            cp = COUNTERPART.get(name, "NONE - cannot be re-pointed")
            print(f"      {name:12} {m:<7} {e:<11} {cp}")

        print("\n[C] WOULD A RE-POINT COLLIDE? - do the LS counterparts already hold rows?")
        for src, dst in COUNTERPART.items():
            m = await c.fetchval("""
                SELECT count(*) FROM student_assessment_scores x
                  JOIN students st ON st.id = x.student_id
                  JOIN subjects s  ON s.id = x.subject_id
                 WHERE st.class_id = ANY($1::varchar[]) AND s.name = $2""", cids, dst)
            both = await c.fetchval("""
                SELECT count(*) FROM students st
                 WHERE st.class_id = ANY($1::varchar[])
                   AND EXISTS (SELECT 1 FROM student_assessment_scores a
                                 JOIN subjects s1 ON s1.id = a.subject_id
                                WHERE a.student_id = st.id AND s1.name = $2)
                   AND EXISTS (SELECT 1 FROM student_assessment_scores b
                                 JOIN subjects s2 ON s2.id = b.subject_id
                                WHERE b.student_id = st.id AND s2.name = $3)""",
                cids, src, dst)
            print(f"      {src:10} -> {dst:14} target already has {m:<5} marks; "
                  f"{both} pupil(s) hold BOTH")
        print("    A pupil holding both would end up with two marks in one subject")
        print("    after a re-point. That is the collision to resolve first.")

        print("\n[D] WHICH TERMS AND SESSIONS ARE AFFECTED?")
        # A mark carries NO term of its own. Both the term and the session come
        # from its ASSESSMENT: `student_assessment_scores.assessment_id` ->
        # `assessments.term_id` / `.session_id`. The first draft of this query
        # read `x.term_id` and then joined the session off `academic_terms`, and
        # BOTH were wrong -- `academic_terms` has no session_id either, because
        # terms are org-wide and shared across years (Autumn is the same row
        # every session). That is precisely what migration 134 put `session_id`
        # on `assessments` to resolve, so the session must be read from there.
        for r in await c.fetch("""
            SELECT se.name AS session, t.name AS term, count(*) AS n
              FROM student_assessment_scores x
              JOIN students st    ON st.id = x.student_id
              JOIN subjects s     ON s.id = x.subject_id
              JOIN assessments a  ON a.id = x.assessment_id
              LEFT JOIN academic_terms t     ON t.id = a.term_id
              LEFT JOIN academic_sessions se ON se.id = a.session_id
             WHERE st.class_id = ANY($1::varchar[]) AND s.name = ANY($2::text[])
             GROUP BY se.name, t.name
             ORDER BY se.name, t.name""", cids, FOREIGN):
            print(f"      {str(r['session']):12} {str(r['term']):10} {r['n']} marks")

        print("\n[E] IS ANY REPORT FOR THESE CLASSES PUBLISHED?")
        print("    (a published card changing retroactively is the real blast radius)")
        rows = await c.fetch("""
            SELECT cl.name AS cls, t.name AS term, ra.stage
              FROM report_approvals ra
              JOIN school_classes cl ON cl.id = ra.class_id
              LEFT JOIN academic_terms t ON t.id = ra.term_id
             WHERE ra.class_id = ANY($1::varchar[])
             ORDER BY cl.name, t.name""", cids)
        if not rows:
            print("      no report_approvals rows for these classes at all")
        for r in rows:
            mark = "  <-- PUBLISHED" if str(r["stage"]).lower() == "published" else ""
            print(f"      {r['cls'][:15]:16} {str(r['term']):10} {r['stage']}{mark}")

        print("\n[F] HOW MANY PUPILS ARE INVOLVED?")
        p = await c.fetchval("""
            SELECT count(DISTINCT st.id) FROM students st
             WHERE st.class_id = ANY($1::varchar[]) AND st.is_deleted = FALSE""", cids)
        print(f"      pupils in the six junior classes: {p}")
        print(f"\n[G] alembic_version: "
              f"{await c.fetchval('SELECT version_num FROM alembic_version')}")
        print("=" * 78)
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
