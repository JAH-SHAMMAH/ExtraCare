"""Re-tag a free-text term name across EVERY table that stores one.

Fairview adopted Autumn/Spring/Summer as its permanent term names, but the data
written before that still says 'Term 1'. Term is not a foreign key in most
places (see docs/future-features.md section 6): it is a string matched by value,
in five different tables. Moving one and not the others does not fix the drift,
it multiplies it:

  cbt_exams.term       -> sync_cbt_to_assessment_score resolves AcademicTerm by
                          this name; a miss is why CBT scores stopped arriving.
  report_approvals.term-> find_published_block matches on it. If exams move and
                          this does not, the publish freeze silently STOPS
                          matching and 12 approved reports quietly reopen.
  grades.term          -> the live report card computes marks from these rows.
  student_reports.term -> per-student comments/attendance, unique on
                          (student, term), joined to the card by name.
  academic_sessions.term -> the org's current term; useCurrentTerm() seeds the
                          UI's term defaults from it.

So the rename is atomic across all five or it is wrong.

DRY RUN BY DEFAULT. Nothing is written without --write, and --write refuses
unless the destination AcademicTerm already exists.

    python scripts/retag_term.py <DSN> --from "Term 1" --to Autumn
    python scripts/retag_term.py <DSN> --from "Term 1" --to Autumn --write
"""
from __future__ import annotations

import argparse
import asyncio
import sys

# Every table holding a free-text term name, with how it is used. Order matters
# for --write: see the note in `apply` about the freeze window.
TABLES = [
    ("cbt_exams", "term", "CBT exams (drives the Make Report sync)"),
    ("grades", "term", "gradebook rows behind the live report card"),
    ("student_reports", "term", "per-student comments + attendance"),
    ("academic_sessions", "term", "the org's current term"),
    ("report_approvals", "term", "publish workflow - THE FREEZE"),
]


def _normalise(url: str) -> str:
    url = url.strip()
    for prefix in ("postgresql+asyncpg://", "postgres+asyncpg://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix):]
            break
    return url.replace("?ssl=require", "?sslmode=require")


async def survey(conn, old: str, new: str):
    """What is there now, and what a re-tag would touch. Reads only."""
    print(f"re-tag {old!r} -> {new!r}\n")

    terms = await conn.fetch("SELECT name FROM academic_terms ORDER BY name")
    names = [r["name"] for r in terms]
    print(f"AcademicTerm rows that exist : {', '.join(names) or '(none)'}")
    print(f"  destination {new!r} exists : {'YES' if new in names else 'NO  <-- must exist first'}")
    print(f"  source {old!r} exists      : {'yes' if old in names else 'no (already gone)'}")
    print()

    total = 0
    print(f"{'table':<22} {'rows to re-tag':>14}   what it drives")
    print("-" * 78)
    for table, col, what in TABLES:
        n = await conn.fetchval(f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" = $1', old)
        other = await conn.fetchval(
            f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" IS NOT NULL AND "{col}" <> $1', old
        )
        flag = f"   (+{other} row(s) on other names)" if other else ""
        print(f"{table:<22} {n:>14}   {what}{flag}")
        total += n
    print("-" * 78)
    print(f"{'TOTAL':<22} {total:>14}\n")
    return total


async def freeze_effect(conn, old: str, new: str):
    """The question that decides whether this is safe: what happens to the freeze."""
    rows = await conn.fetch(
        """
        SELECT sc.name, ra.stage FROM report_approvals ra
        LEFT JOIN school_classes sc ON sc.id = ra.class_id
        WHERE ra.term = $1 AND ra.stage = 'published' ORDER BY sc.name
        """,
        old,
    )
    print(f"FREEZE: {len(rows)} class(es) published under {old!r}")
    for r in rows:
        print(f"  - {r['name']}")
    if rows:
        print(
            "\n  Re-tagging exams WITHOUT report_approvals would leave these matching\n"
            "  nothing, so find_published_block would stop firing and CBT marks could\n"
            "  be written behind reports already released to parents.\n"
            "  Re-tagging BOTH keeps the freeze intact - and then the CBT sync is\n"
            "  correctly refused for these classes until they are retracted."
        )
    print()


async def recovery_forecast(conn):
    """How many StudentAssessmentScore rows a re-sync should produce."""
    row = await conn.fetchrow(
        """
        SELECT COUNT(DISTINCT e.id) AS exams,
               COUNT(*)             AS expected_rows,
               COUNT(DISTINCT e.class_id) AS classes
        FROM cbt_exams e
        JOIN cbt_attempts a
          ON a.exam_id = e.id AND a.status = 'GRADED' AND a.superseded_at IS NULL
        WHERE e.results_published_at IS NOT NULL
          AND e.subject_id IS NOT NULL AND e.term IS NOT NULL
        """
    )
    have = await conn.fetchval("SELECT COUNT(*) FROM student_assessment_scores")
    print("RECOVERY FORECAST (re-running the CBT -> Make Report sync)")
    print(f"  publishable exams with graded attempts : {row['exams']}")
    print(f"  across classes                         : {row['classes']}")
    print(f"  StudentAssessmentScore rows expected   : {row['expected_rows']}")
    print(f"  rows present right now                 : {have}")
    print(f"  shortfall to recover                   : {row['expected_rows'] - have}")
    print(
        "\n  One row per (student, subject) per exam: the sync keeps each student's\n"
        "  BEST graded attempt, so a student with two attempts still yields one row.\n"
    )
    return row["expected_rows"]


async def per_class(conn):
    """The full list, so nobody has to take 'every affected class' on trust."""
    rows = await conn.fetch(
        """
        SELECT sc.name AS class_name,
               COUNT(DISTINCT e.id) AS exams,
               COUNT(*)             AS expected_rows
        FROM cbt_exams e
        JOIN school_classes sc ON sc.id = e.class_id
        JOIN cbt_attempts a
          ON a.exam_id = e.id AND a.status = 'GRADED' AND a.superseded_at IS NULL
        WHERE e.results_published_at IS NOT NULL AND e.subject_id IS NOT NULL
        GROUP BY sc.name ORDER BY sc.name
        """
    )
    print(f"{'class':<16} {'exams':>6} {'rows expected':>14}")
    print("-" * 40)
    for r in rows:
        print(f"{r['class_name']:<16} {r['exams']:>6} {r['expected_rows']:>14}")
    print("-" * 40)
    print(f"{'classes: ' + str(len(rows)):<16} "
          f"{sum(r['exams'] for r in rows):>6} {sum(r['expected_rows'] for r in rows):>14}\n")


async def apply(conn, old: str, new: str):
    """The real write. One transaction: all five tables move together or none do."""
    exists = await conn.fetchval("SELECT COUNT(*) FROM academic_terms WHERE name = $1", new)
    if not exists:
        sys.exit(f"REFUSED: no AcademicTerm named {new!r}. Create it before re-tagging, "
                 f"or the sync will resolve nothing and this changes one broken name "
                 f"for another.")

    async with conn.transaction():
        moved = {}
        for table, col, _what in TABLES:
            before = await conn.fetchval(
                f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" = $1', old
            )
            # asyncpg returns the tag, e.g. "UPDATE 120" — the authoritative count
            # of rows this statement actually changed, rather than a re-count that
            # could quietly disagree with it.
            tag = await conn.execute(
                f'UPDATE "{table}" SET "{col}" = $1 WHERE "{col}" = $2', new, old
            )
            changed = int(tag.rsplit(" ", 1)[-1])
            left = await conn.fetchval(
                f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" = $1', old
            )
            if changed != before or left:
                raise RuntimeError(
                    f"{table}: expected to move {before}, moved {changed}, "
                    f"{left} still on {old!r} — rolling back."
                )
            moved[table] = changed
            print(f"  {table:<22} {changed:>6} row(s) moved to {new!r}")

    print(f"\n[OK] {sum(moved.values())} row(s) re-tagged in one transaction.")
    return moved


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dsn")
    ap.add_argument("--from", dest="old", required=True)
    ap.add_argument("--to", dest="new", required=True)
    ap.add_argument("--write", action="store_true", help="perform the update (default: dry run)")
    ap.add_argument("--only", nargs="*", default=None,
                    help="restrict to these tables (the freeze is re-tagged in its own "
                         "step, so the CBT sync can run before it starts matching)")
    args = ap.parse_args()

    import asyncpg
    conn = await asyncpg.connect(_normalise(args.dsn))
    try:
        global TABLES
        if args.only:
            missing = set(args.only) - {t for t, _, _ in TABLES}
            if missing:
                sys.exit(f"unknown table(s): {sorted(missing)}")
            TABLES = [t for t in TABLES if t[0] in args.only]
            print(f"RESTRICTED to: {', '.join(t for t, _, _ in TABLES)}\n")
        total = await survey(conn, args.old, args.new)
        await freeze_effect(conn, args.old, args.new)
        await recovery_forecast(conn)
        await per_class(conn)
        if args.write:
            print("=== WRITING ===")
            await apply(conn, args.old, args.new)
        else:
            print(f"DRY RUN - nothing written. {total} row(s) would change.")
            print("Re-run with --write to apply.")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
