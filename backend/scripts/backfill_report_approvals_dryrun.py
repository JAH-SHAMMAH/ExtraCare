#!/usr/bin/env python
"""Preview migration 125's ReportApproval backfill against a live database.

  python scripts/backfill_report_approvals_dryrun.py                    # default DB
  python scripts/backfill_report_approvals_dryrun.py <db-url>           # explicit DB

READ-ONLY. It calls the exact planner the migration calls
(app.services.report_approval_backfill.plan_backfill) and prints the plan; it
never inserts, and the connection is rolled back on the way out. There is no
--write flag on purpose: the write path is the migration, so the two can't drift
into disagreeing about what "the backfill" means.

The verification it is built to support: the rows planned must correspond one for
one with the (class, term) pairs that currently have published grades — nothing
more, nothing less. The reconciliation at the bottom recomputes that set with an
INDEPENDENT query and asserts the two agree, so the check does not rest on the
planner grading its own homework.
"""
import asyncio
import pathlib
import re
import sys

# Runnable as `python scripts/backfill_report_approvals_dryrun.py` from the backend
# root, where sys.path[0] is scripts/ and `app` would otherwise be unimportable.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.services.report_approval_backfill import PUBLISHED_STATUS, plan_backfill

# Reuse the CBT backfill's connection string rather than restating the credential.
_CBT = pathlib.Path(__file__).with_name("backfill_cbt_assessments.py").read_text()
DB_URL = re.search(r'^DB_URL = "(.+)"', _CBT, re.M).group(1)


def _resolve_db_url() -> str:
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            return arg
    return DB_URL


async def main() -> int:
    url = _resolve_db_url().split("?")[0]
    engine = create_async_engine(url, connect_args={"ssl": "require"}, pool_pre_ping=True)
    exit_code = 0

    async with engine.connect() as conn:
        host = url.split("@")[-1]
        print("=" * 78)
        print("DRY-RUN — migration 125 ReportApproval backfill (nothing is written)")
        print(f"target: {host}")
        print("=" * 78)

        rev = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalars().all()
        print(f"\nalembic head on target : {rev}")

        # ── current state, before anything ────────────────────────────────────
        total_grades = (await conn.execute(text("SELECT COUNT(*) FROM grades"))).scalar()
        pub_grades = (await conn.execute(
            text("SELECT COUNT(*) FROM grades WHERE status = :s"), {"s": PUBLISHED_STATUS}
        )).scalar()
        existing = (await conn.execute(text("SELECT COUNT(*) FROM report_approvals"))).scalar()
        print(f"grades                 : {total_grades} ({pub_grades} published)")
        print(f"report_approvals rows  : {existing}")

        # ── the plan, from the migration's own planner ────────────────────────
        to_create, skipped = await conn.run_sync(lambda sync_conn: plan_backfill(sync_conn))

        print(f"\n-- WOULD CREATE {len(to_create)} report_approvals row(s), stage='published' --")
        print(f"   {'class':<18} {'term':<10} {'year':<12} {'grades':>7} {'students':>9}")
        for r in to_create:
            print(f"   {(r['class_name'] or '?'):<18} {(r['term'] or ''):<10} "
                  f"{(r['academic_year'] or '-'):<12} {r['grade_rows']:>7} {r['students']:>9}")

        print(f"\n-- WOULD SKIP {len(skipped)} pair(s) (a row already exists) --")
        for r in skipped:
            print(f"   {(r['class_name'] or '?'):<18} {(r['term'] or ''):<10} "
                  f"already at stage '{r['existing_stage']}'")
        if not skipped:
            print("   (none)")

        # ── independent reconciliation ────────────────────────────────────────
        # Recomputed WITHOUT the planner: if the two disagree, the plan is wrong.
        print("\n" + "-" * 78)
        print("RECONCILIATION — planned rows vs. classes that actually have published grades")
        print("-" * 78)

        truth = {
            (r[0], r[1], r[2]): (r[3], r[4])
            for r in (await conn.execute(text(
                """
                SELECT g.org_id, s.class_id, g.term, COUNT(*), COUNT(DISTINCT g.student_id)
                FROM grades g, students s
                WHERE s.id = g.student_id
                  AND g.status = :s
                  AND s.class_id IS NOT NULL
                  AND g.term IS NOT NULL
                GROUP BY g.org_id, s.class_id, g.term
                """
            ), {"s": PUBLISHED_STATUS})).fetchall()
        }
        planned = {(r["org_id"], r["class_id"], r["term"]) for r in to_create}
        skipped_keys = {(r["org_id"], r["class_id"], r["term"]) for r in skipped}
        covered = planned | skipped_keys

        missing = set(truth) - covered           # published grades with no row -> cards go blank
        extra = covered - set(truth)             # a row for something not published -> over-reach
        print(f"(class, term) pairs with published grades : {len(truth)}")
        print(f"pairs covered by the plan (create + skip)  : {len(covered)}")
        print(f"MISSING (would lose parent visibility)     : {len(missing)}")
        for k in sorted(missing):
            print(f"    !! {k}")
        print(f"EXTRA (row for a pair with no published grades): {len(extra)}")
        for k in sorted(extra):
            print(f"    !! {k}")

        counts_ok = all(truth[(r["org_id"], r["class_id"], r["term"])] == (r["grade_rows"], r["students"])
                        for r in to_create)
        grades_covered = sum(truth[k][0] for k in covered if k in truth)

        # A pair that is skipped but parked below `published` still hides its cards.
        blind = [r for r in skipped if r["existing_stage"] != "published"]
        print(f"\npublished grades under a covered pair      : {grades_covered} of {pub_grades}")
        print(f"per-pair grade/student counts match truth  : {counts_ok}")
        print(f"skipped pairs NOT at stage 'published'     : {len(blind)}")
        for r in blind:
            print(f"    !! {r['class_name']} / {r['term']} sits at '{r['existing_stage']}' "
                  f"— {r['grade_rows']} grades would stay hidden from parents")

        # Published grades the backfill can NEVER cover: no class, or no term.
        orphans = (await conn.execute(text(
            """
            SELECT COUNT(*) FROM grades g, students s
            WHERE s.id = g.student_id AND g.status = :s
              AND (s.class_id IS NULL OR g.term IS NULL)
            """
        ), {"s": PUBLISHED_STATUS})).scalar()
        print(f"published grades with no class or no term  : {orphans}"
              + ("  <- these would be hidden from parents" if orphans else ""))

        ok = (not missing and not extra and counts_ok and not blind
              and grades_covered == pub_grades and orphans == 0)
        print("\n" + "=" * 78)
        print("VERDICT: " + ("PASS — the plan covers exactly the published (class, term) pairs"
                             if ok else
                             "FAIL — read the !! lines above before applying"))
        print("=" * 78)
        exit_code = 0 if ok else 1

        await conn.rollback()

    await engine.dispose()
    return exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
