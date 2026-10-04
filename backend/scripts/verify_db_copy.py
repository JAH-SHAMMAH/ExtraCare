"""Verify a database copy before switching DATABASE_URL. READ-ONLY on both sides.

WRITES NOTHING. No INSERT/UPDATE/DELETE/DDL anywhere in this file.

CREDENTIALS NEVER TOUCH THE COMMAND LINE. Both DSNs come from the environment,
or from a hidden prompt if unset — never from argv, so nothing lands in shell
history or in a process list. The script refuses to run rather than guessing.

    set SOURCE_DATABASE_URL=...      (the OLD, live database)
    set TARGET_DATABASE_URL=...      (the NEW, restored database)
    python scripts/verify_db_copy.py

    python scripts/verify_db_copy.py --prompt
        Ask for whichever DSN is unset, with the input hidden. Opt-in, because
        an automatic prompt HANGS rather than refusing when there is no console.

    python scripts/verify_db_copy.py --preflight
        Only SOURCE is needed. Checks that pg_dump exists and is NOT OLDER than
        the server — an older client aborts the dump outright — and prints the
        exact dump/restore commands. Run this BEFORE taking the dump.

WHY A TABLE CHECKLIST IS NOT ENOUGH. Migrations 134-138 create NO tables; they
are column, constraint and index changes. A verification that compares table
inventories and row counts would pass while every one of them was missing, so
each is asserted by name in section [5].

SEQUENCES. A restore commonly leaves sequences behind their data. Nothing looks
wrong until the first INSERT, which then fails on a duplicate key. Section [7]
compares last_value per sequence.
"""
from __future__ import annotations

import asyncio
import getpass
import os
import re
import shutil
import subprocess
import sys

import asyncpg

PREFLIGHT = "--preflight" in sys.argv
PROMPT = "--prompt" in sys.argv

# ── What migrations 134-138 actually changed. Table checklists miss all of it ──
EXPECTED_COLUMNS = [
    # (table, column, must_be_not_null, which migration)
    ("assessments", "session_id", True, "134"),
    ("cumulatives", "session_id", True, "134"),
    ("student_reports", "term_id", True, "135"),
    ("student_reports", "session_id", True, "135"),
    ("subjects", "section_id", True, "137 + 138 (NOT NULL)"),
]
EXPECTED_CONSTRAINTS = [
    ("student_reports", "uq_student_report_student_session_term", "u", "135"),
    ("attendance_records", "uq_attendance_record_student_day", "u", "136"),
    ("subjects", "uq_subjects_org_section_name", "u", "137"),
]
# 135 REPLACED this one. If it is still present, an old schema was restored.
DROPPED_CONSTRAINTS = [("student_reports", "uq_student_report_student_term", "135")]
EXPECTED_HEAD = "138_subject_section_required"

# Where the dump goes. OUTSIDE OneDrive and OUTSIDE the repo, because it holds
# every user row and password hash. Same convention the manifest-writing scripts
# already use, so there is one backup location rather than two.
DUMP_DIR = os.environ.get("FAIRVIEW_BACKUPS", r"C:\Users\SHAMMAH\fairview-backups")
DUMP_PATH = os.path.join(DUMP_DIR, "fairview_138.dump")


def _dsn(var: str, prompt: str) -> str:
    """The DSN from the environment, or a hidden prompt ONLY with --prompt.

    Prompting is opt-in rather than automatic. `getpass` on Windows reads the
    console directly, so a redirected stdin does NOT make it fail fast — an
    automatic fallback therefore HANGS in any non-interactive context (CI, a
    pipe, a background shell) instead of refusing. Opt-in keeps the default
    behaviour deterministic: missing variable, immediate refusal.
    """
    val = os.environ.get(var, "").strip()
    if val:
        return val.replace("postgresql+asyncpg://", "postgresql://")
    if not PROMPT:
        raise SystemExit(
            f"{var} is not set.\n"
            f"  Set it in the environment (never on the command line — it would\n"
            f"  land in shell history and in the process list), or re-run with\n"
            f"  --prompt to be asked for it with the input hidden.")
    val = getpass.getpass(f"{prompt} (input hidden): ").strip()
    if not val:
        raise SystemExit(f"{var} is required.")
    return val.replace("postgresql+asyncpg://", "postgresql://")


def _redact(text: str) -> str:
    """Strip any user:password@ out of a string before it can be printed.

    A safety net, not the primary defence: nothing in this script prints a DSN.
    But a connection error raised by the driver can carry one, and a password
    leaked to a terminal cannot be un-leaked.
    """
    return re.sub(r"(?i)(postgres(?:ql)?://)[^:/@\s]+:[^@/\s]+@",
                  r"\1<redacted>@", text)


def _ver_tuple(text: str) -> tuple[int, ...]:
    m = re.search(r"(\d+)(?:\.(\d+))?", text or "")
    return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)


async def _preflight(src: str) -> None:
    print("=" * 78)
    print("[0] PREFLIGHT — can this machine take the dump at all?")
    print("=" * 78)
    exe = shutil.which("pg_dump")
    if not exe:
        print("    pg_dump: NOT FOUND on PATH.")
        print("    Install the PostgreSQL client tools, or run the dump from a")
        print("    container whose client major version matches the server.")
    else:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout
        print(f"    pg_dump: {exe}")
        print(f"             {out.strip()}")

    c = await asyncpg.connect(src, timeout=180, command_timeout=120, ssl="require")
    try:
        server = await c.fetchval("SHOW server_version")
        db = await c.fetchval("SELECT current_database()")
        head = await c.fetchval("SELECT version_num FROM alembic_version")
    finally:
        await c.close()
    print(f"    server:  PostgreSQL {server}   database: {db}")
    print(f"    alembic_version: {head}"
          f"{'' if head == EXPECTED_HEAD else '   <-- EXPECTED ' + EXPECTED_HEAD}")

    if exe:
        cv, sv = _ver_tuple(out), _ver_tuple(server)
        ok = cv >= sv
        print(f"\n    client {cv[0]}  vs  server {sv[0]}  ->  "
              f"{'OK — client is not older' if ok else 'TOO OLD — the dump WILL abort'}")
        if not ok:
            print("    A pg_dump older than the server refuses to run. Upgrade the")
            print("    client, or dump from a container matching the server major.")

    print(f"\n    DUMP LOCATION: {DUMP_PATH}")
    print("    Outside OneDrive and outside the repo, on purpose. A dump holds")
    print("    EVERY user row and password hash: inside OneDrive it would sync to")
    print("    the cloud, and inside the repo it would be one `git add -A` from")
    print("    being committed. `*.dump` is in .gitignore as a second line of")
    print("    defence, not as the only one.")
    if not os.path.isdir(DUMP_DIR):
        print(f"    NOTE: {DUMP_DIR} does not exist yet — create it first.")

    print("\n    THE COMMANDS, in order — PowerShell. The DSNs are passed BY")
    print("    VARIABLE REFERENCE, so no password is typed or stored in history:")
    print()
    print("      # 1. dump (custom format; no owner/ACL, as the new role differs)")
    print("      pg_dump -Fc --no-owner --no-privileges `")
    print("              $env:SOURCE_DATABASE_URL `")
    print(f'              -f "{DUMP_PATH}"')
    print()
    print("      # 2. verify the dump BY CONTENT, not by exit code")
    print(f'      pg_restore --list "{DUMP_PATH}" |')
    print('          Select-String "TABLE DATA" | Measure-Object | '
          "Select-Object -Expand Count")
    print()
    print("      # 3. restore into the NEW, EMPTY database")
    print("      pg_restore --no-owner --no-privileges `")
    print("                 -d $env:TARGET_DATABASE_URL `")
    print(f'                 "{DUMP_PATH}"')
    print()
    print("      # 4. alembic must find NOTHING to do (run from backend\\)")
    print("      alembic current        # expect " + EXPECTED_HEAD + " (head)")
    print("      alembic upgrade head   # expect no migration to run")
    print()
    print("    CAVEAT, stated rather than glossed: passing the DSN by variable")
    print("    keeps the password out of SHELL HISTORY, but the expanded value is")
    print("    briefly visible in the PROCESS LIST while pg_dump runs. On a shared")
    print("    machine, set $env:PGPASSWORD instead and pass -h/-U/-d separately.")
    print("\n    Then re-run this script without --preflight.")
    print("=" * 78)


async def _counts(c: asyncpg.Connection) -> dict[str, int]:
    """Row counts for every public table in ONE round trip.

    275 tables at ~940 ms each would be over four minutes; a single UNION ALL is
    one round trip. The table list is read from `pg_tables` at runtime, so the
    count is never hard-coded.

    (275 = the 274 tables the ORM defines, plus `alembic_version`, which alembic
    creates and no model declares. An earlier comment here said 154 — that was a
    partial ORM count taken after importing only 3 of the 40 model modules, and
    was never a figure about the database.)
    """
    tables = [r["tablename"] for r in await c.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
    if not tables:
        return {}
    sql = " UNION ALL ".join(
        f"SELECT {_lit(t)} AS t, count(*) AS n FROM public.{_ident(t)}" for t in tables)
    return {r["t"]: r["n"] for r in await c.fetch(sql)}


def _ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _lit(name: str) -> str:
    return "'" + name.replace("'", "''") + "'"


async def _sequences(c: asyncpg.Connection) -> dict[str, int | None]:
    return {r["sequencename"]: r["last_value"] for r in await c.fetch(
        "SELECT sequencename, last_value FROM pg_sequences WHERE schemaname='public'")}


async def _columns(c: asyncpg.Connection) -> dict[tuple[str, str], str]:
    return {(r["table_name"], r["column_name"]): r["is_nullable"]
            for r in await c.fetch(
                "SELECT table_name, column_name, is_nullable "
                "FROM information_schema.columns WHERE table_schema='public'")}


async def _constraints(c: asyncpg.Connection) -> set[tuple[str, str, str]]:
    return {(r["tbl"], r["conname"], r["contype"]) for r in await c.fetch("""
        SELECT rel.relname AS tbl, con.conname, con.contype::text
          FROM pg_constraint con
          JOIN pg_class rel ON rel.oid = con.conrelid
          JOIN pg_namespace n ON n.oid = rel.relnamespace
         WHERE n.nspname = 'public'""")}


async def _fk_orphans(c: asyncpg.Connection) -> tuple[list[tuple[str, int]], list[str]]:
    """Count orphan rows for every SINGLE-column FK. Composite FKs are reported
    as skipped rather than silently ignored."""
    fks = await c.fetch("""
        SELECT con.conname, rel.relname AS child, att.attname AS col,
               frel.relname AS parent, fatt.attname AS fcol,
               array_length(con.conkey, 1) AS ncols
          FROM pg_constraint con
          JOIN pg_class rel   ON rel.oid = con.conrelid
          JOIN pg_class frel  ON frel.oid = con.confrelid
          JOIN pg_namespace n ON n.oid = rel.relnamespace
          JOIN pg_attribute att  ON att.attrelid = con.conrelid
                                AND att.attnum = con.conkey[1]
          JOIN pg_attribute fatt ON fatt.attrelid = con.confrelid
                                AND fatt.attnum = con.confkey[1]
         WHERE con.contype = 'f' AND n.nspname = 'public'
         ORDER BY rel.relname, con.conname""")
    single = [f for f in fks if (f["ncols"] or 1) == 1]
    skipped = [f["conname"] for f in fks if (f["ncols"] or 1) != 1]
    if not single:
        return [], skipped
    sql = " UNION ALL ".join(
        f"SELECT {_lit(f['conname'])} AS c, count(*) AS n "
        f"FROM public.{_ident(f['child'])} ch "
        f"LEFT JOIN public.{_ident(f['parent'])} pa "
        f"  ON pa.{_ident(f['fcol'])} = ch.{_ident(f['col'])} "
        f"WHERE ch.{_ident(f['col'])} IS NOT NULL AND pa.{_ident(f['fcol'])} IS NULL"
        for f in single)
    rows = await c.fetch(sql)
    return [(r["c"], r["n"]) for r in rows if r["n"]], skipped


async def main() -> None:
    src_dsn = _dsn("SOURCE_DATABASE_URL", "SOURCE (old, live) DSN")
    if PREFLIGHT:
        await _preflight(src_dsn)
        return
    tgt_dsn = _dsn("TARGET_DATABASE_URL", "TARGET (new, restored) DSN")

    s = await asyncpg.connect(src_dsn, timeout=180, command_timeout=600, ssl="require")
    t = await asyncpg.connect(tgt_dsn, timeout=180, command_timeout=600, ssl="require")
    problems: list[str] = []
    try:
        print("=" * 78)
        print("VERIFY DATABASE COPY — READ-ONLY ON BOTH SIDES")
        print("=" * 78)

        print("\n[1] IDENTITY — these must be two DIFFERENT databases")
        sdb = await s.fetchval("SELECT current_database()")
        tdb = await t.fetchval("SELECT current_database()")
        shost = await s.fetchval("SELECT inet_server_addr()::text")
        thost = await t.fetchval("SELECT inet_server_addr()::text")
        print(f"    source: {sdb} @ {shost}")
        print(f"    target: {tdb} @ {thost}")
        if (sdb, shost) == (tdb, thost):
            problems.append("source and target are the SAME database")
            print("    *** SAME DATABASE — the comparison below is meaningless ***")

        print("\n[2] ALEMBIC VERSION")
        sv = await s.fetchval("SELECT version_num FROM alembic_version")
        tv = await t.fetchval("SELECT version_num FROM alembic_version")
        print(f"    source: {sv}")
        print(f"    target: {tv}")
        if sv != tv:
            problems.append(f"alembic_version differs ({sv} vs {tv})")
        if tv != EXPECTED_HEAD:
            problems.append(f"target is not at {EXPECTED_HEAD}")

        print("\n[3] TABLE INVENTORY")
        sc, tc = await _counts(s), await _counts(t)
        only_s = sorted(set(sc) - set(tc))
        only_t = sorted(set(tc) - set(sc))
        print(f"    source tables: {len(sc)}    target tables: {len(tc)}")
        print(f"    missing from target: {len(only_s)} {only_s or ''}")
        print(f"    extra in target:     {len(only_t)} {only_t or ''}")
        if only_s:
            problems.append(f"{len(only_s)} table(s) missing from target")

        print("\n[4] ROW COUNTS — every table with a difference")
        diffs = [(k, sc[k], tc.get(k)) for k in sorted(sc) if sc[k] != tc.get(k)]
        same = len(sc) - len(diffs)
        print(f"    identical: {same} of {len(sc)}")
        if diffs:
            print(f"      {'table':34} {'source':>9} {'target':>9}")
            for k, a, b in diffs:
                print(f"      {k[:33]:34} {a:>9} {str(b):>9}")
            problems.append(f"{len(diffs)} table(s) differ in row count")
        else:
            print("    every table matches")
        big = sorted(((k, v) for k, v in sc.items() if v), key=lambda kv: -kv[1])[:8]
        print("    largest tables (sanity): " +
              ", ".join(f"{k}={v}" for k, v in big))

        print("\n[5] THE 134-138 CHANGES — what a table checklist would miss")
        tcols = await _columns(t)
        for tbl, col, notnull, mig in EXPECTED_COLUMNS:
            got = tcols.get((tbl, col))
            if got is None:
                print(f"    MISSING  {tbl}.{col}  (migration {mig})")
                problems.append(f"{tbl}.{col} missing on target")
            elif notnull and got != "NO":
                print(f"    NULLABLE {tbl}.{col}  should be NOT NULL  ({mig})")
                problems.append(f"{tbl}.{col} is nullable on target")
            else:
                print(f"    OK       {tbl}.{col}  NOT NULL  ({mig})")
        tcon = await _constraints(t)
        names = {(a, b) for a, b, _ in tcon}
        for tbl, name, _ctype, mig in EXPECTED_CONSTRAINTS:
            ok = (tbl, name) in names
            print(f"    {'OK      ' if ok else 'MISSING '} {name}  ({mig})")
            if not ok:
                problems.append(f"constraint {name} missing on target")
        for tbl, name, mig in DROPPED_CONSTRAINTS:
            if (tbl, name) in names:
                print(f"    STALE    {name} still present — {mig} should have dropped it")
                problems.append(f"dropped constraint {name} still on target")
            else:
                print(f"    OK       {name} correctly absent  ({mig})")

        print("\n[6] FOREIGN KEY INTEGRITY ON THE TARGET")
        orphans, skipped = await _fk_orphans(t)
        print(f"    single-column FKs with orphan rows: {len(orphans)}")
        for name, n in orphans:
            print(f"      {name}: {n} orphan row(s)")
            problems.append(f"FK {name} has {n} orphans")
        if skipped:
            print(f"    composite FKs NOT checked ({len(skipped)}): {skipped}")

        print("\n[7] SEQUENCES — the restore gotcha that only shows on first INSERT")
        ss, ts = await _sequences(s), await _sequences(t)
        missing = sorted(set(ss) - set(ts))
        behind = [(k, ss[k], ts.get(k)) for k in sorted(ss)
                  if k in ts and (ss[k] or 0) > (ts[k] or 0)]
        print(f"    sequences: source {len(ss)}  target {len(ts)}")
        print(f"    missing from target: {len(missing)} {missing or ''}")
        if missing:
            problems.append(f"{len(missing)} sequence(s) missing from target")
        if behind:
            print(f"      {'sequence':34} {'source':>10} {'target':>10}")
            for k, a, b in behind:
                print(f"      {k[:33]:34} {str(a):>10} {str(b):>10}")
            problems.append(f"{len(behind)} sequence(s) BEHIND on target — "
                            f"first insert will fail on duplicate key")
        else:
            print("    no sequence is behind its source")
        if not ss:
            print("    (none — this schema is UUID-keyed, so nothing to reset)")

        print("\n" + "=" * 78)
        if problems:
            print(f"VERDICT: NOT SAFE TO SWITCH — {len(problems)} problem(s)")
            for p in problems:
                print(f"    - {p}")
        else:
            print("VERDICT: target matches source on every check above.")
            print("Switch DATABASE_URL only after re-confirming nothing has been")
            print("written to the source since the dump was taken.")
        print("=" * 78)
    finally:
        await s.close()
        await t.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except SystemExit:
        raise
    except BaseException as exc:                              # noqa: BLE001
        # Never let a driver error print a DSN to the terminal. `from None`
        # suppresses the chained traceback, which could carry one too.
        raise SystemExit(f"{type(exc).__name__}: {_redact(str(exc))}") from None
