"""What a year-group filter would change. STRICTLY READ-ONLY.

Phase 1 of the report-template arc teaches `load_term_setup` and
`_pick_display_cumulative` to filter report columns by the pupil's year group.
Today they filter by (session, term) ONLY, so every configured column is visible
at every level — which is why Primary's four mark components and Secondary's
three cannot currently coexist.

This script answers the one question that decides whether that filter is safe:
HOW MANY CONFIGURED ROWS ALREADY CARRY A year_group, and what would stop being
visible on a card that renders today.

~~~ WHY THE ANSWER MATTERS SO MUCH ~~~
With the filter written as `year_group IS NULL OR year_group = <level>`, an
unscoped row stays visible everywhere and nothing is lost. Written as a strict
`year_group = <level>`, every column on every card disappears the moment the
filter ships. The difference is one clause, and this measurement is what tells
us which side of it production is on.

It also reports the CASE of `school_classes.level` against the case of
`assessments.year_group`. Production holds 'Year 7' on the class and the
documented/seeded form is 'YEAR 7'; a case-sensitive comparison in PostgreSQL
matches neither way round, which would blank every card while looking like a
filtering bug rather than a collation one.

~~~ HOW IT IS KEPT READ-ONLY ~~~
  * every statement is a SELECT, and `assert_read_only()` greps THIS FILE for
    write keywords before connecting — the same self-check the earlier
    verification scripts carry, so "read-only" is enforced rather than asserted
    in a docstring;
  * the connection is opened inside a transaction that is always rolled back;
  * no --write flag exists, and there is nothing for one to do.

~~~ THE DSN ~~~
Taken from MEASURE_DATABASE_URL, or a hidden prompt if that is unset. NEVER from
argv, so it cannot reach shell history or a process list, and never printed,
logged or written to a file. Refuses to run if it cannot get one.

DELIBERATELY NOT `DATABASE_URL`. That name is what alembic, the app and every
other script in this directory read. Setting it at User scope to point at
production — so that this read-only script can be run — would arm every one of
them: one `alembic upgrade head` in this shell afterwards would migrate the live
database by accident. A dedicated name cannot be picked up by anything else.

    $env:MEASURE_DATABASE_URL = "<dsn>"   # or leave unset and type it at the prompt
    python -m scripts.measure_year_group_scope
    Remove-Item Env:\MEASURE_DATABASE_URL # clear it again afterwards

Accepts either scheme: a `postgresql://` DSN is rewritten to
`postgresql+asyncpg://` for SQLAlchemy, and `sslmode=` is dropped because asyncpg
does not accept it as a query parameter.
"""
from __future__ import annotations

import asyncio
import getpass
import os
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

WRITE_WORDS = (
    "insert into", "update ", "delete from", "drop ", "truncate", "alter ",
    "create ", "grant ", "revoke ", "commit(", ".commit()",
)


def assert_read_only() -> None:
    """Grep this file for anything that could write. Runs before connecting."""
    src = Path(__file__).read_text(encoding="utf-8").casefold()
    # Only the statements we actually send matter, so look inside the SQL blocks
    # rather than the prose — WRITE_WORDS itself names every keyword above.
    sql = " ".join(re.findall(r'text\(\s*"""(.*?)"""', src, re.S) +
                   re.findall(r'text\(\s*"(.*?)"', src, re.S))
    for word in WRITE_WORDS:
        if word in sql:
            sys.exit(f"REFUSING TO RUN: the SQL in this script contains {word!r}.")


def dsn() -> str:
    """From MEASURE_DATABASE_URL, else a hidden prompt. Never argv, never printed."""
    for a in sys.argv[1:]:
        if not a.startswith("--"):
            sys.exit("Do not pass the DSN as an argument — it would land in shell "
                     "history and the process list. Set MEASURE_DATABASE_URL instead, or "
                     "run with no arguments and type it at the hidden prompt.")
    raw = (os.environ.get("MEASURE_DATABASE_URL") or "").strip()
    if not raw:
        raw = getpass.getpass("DSN (hidden, not echoed, not stored): ").strip()
    if not raw:
        sys.exit("No DSN given. Set MEASURE_DATABASE_URL or type one at the prompt.")

    parts = urlsplit(raw)
    scheme = "postgresql+asyncpg" if parts.scheme in ("postgres", "postgresql") else parts.scheme
    # asyncpg rejects sslmode as a query parameter; TLS is negotiated by connect_args.
    query = "&".join(q for q in parts.query.split("&")
                     if q and not q.lower().startswith("sslmode="))
    return urlunsplit((scheme, parts.netloc, parts.path, query, parts.fragment))


CONFIG = text("""
    SELECT 'assessments' AS tbl, year_group, count(*) AS n
      FROM assessments GROUP BY year_group
    UNION ALL
    SELECT 'cumulatives', year_group, count(*)
      FROM cumulatives GROUP BY year_group
     ORDER BY tbl, n DESC
""")

CLASS_LEVELS = text("""
    SELECT level, count(*) AS n
      FROM school_classes
     GROUP BY level
     ORDER BY level
""")

# The rows a strict (case-sensitive) comparison would match, versus a
# case-insensitive one — the gap between them IS the collation risk.
MATCHABLE = text("""
    SELECT a.tbl, a.year_group, c.level,
           (a.year_group = c.level)                 AS exact_match,
           (lower(a.year_group) = lower(c.level))   AS folded_match
      FROM (SELECT 'assessments' AS tbl, year_group FROM assessments
            WHERE year_group IS NOT NULL
            UNION ALL
            SELECT 'cumulatives', year_group FROM cumulatives
            WHERE year_group IS NOT NULL) a
      JOIN (SELECT DISTINCT level FROM school_classes WHERE level IS NOT NULL) c
        ON lower(a.year_group) = lower(c.level)
""")

CONFIGURED_PAIRS = text("""
    SELECT t.name AS term, s.name AS sub_term,
           count(DISTINCT cu.id) AS cumulatives,
           count(DISTINCT asm.id) AS assessments
      FROM academic_terms t
      CROSS JOIN academic_sub_terms s
      LEFT JOIN cumulatives cu ON cu.term_id = t.id AND cu.sub_term_id = s.id
      LEFT JOIN assessments asm ON asm.term_id = t.id AND asm.sub_term_id = s.id
     GROUP BY t.name, s.name, t.position, s.position
     ORDER BY t.position, s.position
""")

ACTIVE_TERM = text("""
    SELECT t.name AS term, s.name AS active_sub_term
      FROM academic_terms t
      LEFT JOIN academic_sub_terms s ON s.id = t.active_sub_term_id
     WHERE t.is_active
""")


def _connect_args(url: str) -> dict:
    """TLS required everywhere except a loopback host.

    The rest of the repo passes `ssl="require"` unconditionally, which is right
    for Render but makes the script unrunnable against a local scratch server
    restored from a dump — and a script that cannot be rehearsed is a script
    whose first run is against production.
    """
    host = (urlsplit(url).hostname or "").casefold()
    if host in ("localhost", "127.0.0.1", "::1"):
        return {}
    return {"ssl": "require"}


async def main() -> int:
    assert_read_only()
    url = dsn()
    engine = create_async_engine(url, echo=False, connect_args=_connect_args(url))

    async with engine.connect() as conn:            # connect(), not begin(): no implicit commit
        print("READ-ONLY measurement. Nothing is written.\n")

        print("-- configured report columns, by year_group --")
        rows = (await conn.execute(CONFIG)).all()
        totals: Counter = Counter()
        scoped: Counter = Counter()
        for tbl, yg, n in rows:
            totals[tbl] += n
            if yg is not None:
                scoped[tbl] += n
            print(f"   {tbl:12} year_group={yg!r:16} x{n}")
        print()
        for tbl in ("assessments", "cumulatives"):
            print(f"   {tbl}: {totals[tbl]} rows, {scoped[tbl]} scoped to a year group")

        print("\n-- WHAT A YEAR-GROUP FILTER WOULD REMOVE --")
        if sum(scoped.values()) == 0:
            print("   NOTHING, provided the filter reads")
            print("     year_group IS NULL OR lower(year_group) = lower(<level>)")
            print("   Every configured row is unscoped, so it stays visible at every")
            print("   level. A STRICT `year_group = <level>` would instead remove")
            print(f"   all {sum(totals.values())} rows from every card in the school.")
        else:
            print(f"   {sum(scoped.values())} scoped rows exist -- each is visible at")
            print("   EVERY level today and would become visible only at its own.")
            print("   Check the per-row listing above against the class levels below")
            print("   before shipping the filter.")

        print("\n-- class levels (what the filter compares against) --")
        for level, n in (await conn.execute(CLASS_LEVELS)).all():
            print(f"   level={level!r:16} x{n} classes")

        print("\n-- case agreement between year_group and level --")
        pairs = (await conn.execute(MATCHABLE)).all()
        if not pairs:
            print("   no scoped rows to compare (consistent with the count above)")
        else:
            bad = [p for p in pairs if not p.exact_match]
            for p in pairs:
                flag = "OK" if p.exact_match else "CASE MISMATCH"
                print(f"   {p.tbl:12} {p.year_group!r} vs level {p.level!r}: {flag}")
            if bad:
                print(f"\n   {len(bad)} pair(s) match only when case-folded. A")
                print("   case-sensitive comparison would silently match NOTHING.")

        print("\n-- configured (term, sub-term) pairs --")
        for r in (await conn.execute(CONFIGURED_PAIRS)).all():
            mark = "" if r.cumulatives else "   <- no columns: a card here has nothing to show"
            print(f"   {r.term:10} {r.sub_term:12} cumulatives={r.cumulatives} "
                  f"assessments={r.assessments}{mark}")

        print("\n-- the ACTIVE term, and whether its sub-term is configured --")
        for r in (await conn.execute(ACTIVE_TERM)).all():
            print(f"   active term {r.term!r}, active sub-term {r.active_sub_term!r}")
            print("   If that pair shows cumulatives=0 above, the card currently")
            print("   BORROWS another sub-term's column -- the fallback that the")
            print("   'not set up' change removes.")

    await engine.dispose()
    print("\nDone. Connection closed, nothing committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
