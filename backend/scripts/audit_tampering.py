#!/usr/bin/env python3
"""Did anyone use the leaked credentials, and did anything change? READ-ONLY.

~~~ WHY ~~~
`backend/scripts/student_credentials_output.csv` was committed on 2026-08-23 --
450 rows of (student_id, email, temp_password) -- into a PUBLIC repository, and
sat there for seven weeks. Two live database passwords and three real account
passwords (two staff, one student) were exposed alongside it.

Removing the files does not answer the only question that matters: WAS ANY OF IT
USED. This script asks that, and nothing else. It changes nothing.

~~~ WHAT IT LOOKS AT ~~~
  1. logins AFTER the exposure date, by exposed and by privileged accounts --
     the sharpest signal available, because `users.last_login_at` is updated on
     every successful sign-in
  2. privileged accounts: anyone holding a role with a wildcard permission, the
     platform superadmin flag, or an admin-tier slug -- and when each was created
  3. accounts created or modified since the exposure date
  4. marks changed since then (`grades` and `student_assessment_scores` both, for
     the reason recorded in the enrolment work: marks live in TWO stores)
  5. money: invoices and payment transactions created or modified since
  6. the audit log over the window, by action and by actor, plus every distinct
     actor IP -- a sign-in from an unfamiliar address is the thing a human can
     recognise and a query cannot
  7. failed-login pressure, which is what a credential-stuffing attempt looks
     like from the inside

~~~ HOW READ-ONLY IS ENFORCED, NOT PROMISED ~~~
  * `assert_read_only()` greps THIS FILE's own SQL for write keywords before it
    connects, so the guarantee is checked rather than asserted in a docstring;
  * the connection is opened with `connect()`, never `begin()`, and is rolled
    back on the way out -- there is no code path that commits;
  * there is no --write flag, and nothing for one to do.

~~~ CREDENTIALS ~~~
The address comes from AUDIT_DATABASE_URL or a hidden prompt. NEVER from argv:
an address there is recorded in shell history and visible in the process list.
It is never printed, logged or written to a file, and driver errors are redacted
before they reach the terminal -- a password leaked to a console cannot be
un-leaked.

DELIBERATELY NOT `DATABASE_URL`: that name is what alembic, the app and
docker-compose read, so setting it in a shell to run an audit would arm all
three.

    $env:AUDIT_DATABASE_URL = "<address>"    # or leave unset and it prompts
    python -m scripts.audit_tampering
    python -m scripts.audit_tampering --since 2026-08-23 --limit 40
    Remove-Item Env:\AUDIT_DATABASE_URL
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

#: The day the credentials file was committed. Everything is measured from here.
EXPOSURE_DATE = "2026-08-23"

WRITE_WORDS = ("insert into", "update ", "delete from", "drop ", "truncate",
               "alter ", "create ", "grant ", "revoke ", "set ")


def assert_read_only() -> None:
    """Grep this file's own SQL for anything that could write. Before connecting."""
    src = Path(__file__).read_text(encoding="utf-8")
    sql = " ".join(re.findall(r'text\(\s*"""(.*?)"""', src, re.S)).casefold()
    for word in WRITE_WORDS:
        if word in sql:
            sys.exit(f"REFUSING TO RUN: this script's SQL contains {word!r}.")


def redact(message: str) -> str:
    """Strip user:password@ out of a driver error before it reaches a terminal."""
    return re.sub(r"(//)[^/\s:@]+:[^/\s@]+(@)", r"\1<redacted>:<redacted>\2", message)


def dsn() -> str:
    for a in sys.argv[1:]:
        if "://" in a:
            sys.exit("Do not pass the address as an argument -- it lands in shell "
                     "history and the process list. Set AUDIT_DATABASE_URL, or run "
                     "with no address and type it at the hidden prompt.")
    raw = (os.environ.get("AUDIT_DATABASE_URL") or "").strip()
    if not raw:
        raw = getpass.getpass("AUDIT_DATABASE_URL (hidden, not echoed, not stored): ").strip()
    if not raw:
        sys.exit("No address given. Set AUDIT_DATABASE_URL or type one at the prompt.")
    parts = urlsplit(raw)
    scheme = ("postgresql+asyncpg" if parts.scheme in ("postgres", "postgresql")
              else parts.scheme)
    query = "&".join(q for q in parts.query.split("&")
                     if q and not q.lower().startswith("sslmode="))
    return urlunsplit((scheme, parts.netloc, parts.path, query, parts.fragment))


def connect_args(url: str) -> dict:
    host = (urlsplit(url).hostname or "").casefold()
    return {} if host in ("localhost", "127.0.0.1", "::1", "") else {"ssl": "require"}


# ── the questions ────────────────────────────────────────────────────────────
# NOTE: `users.status` is a Postgres enum holding the Python enum NAME, so the
# stored value is 'ACTIVE', not 'active'. Every comparison folds case. A
# lowercase literal matches NOTHING and reports a clean bill of health, which
# is the worst possible failure mode for an audit. Caught by rehearsing this
# script against a restored production dump.
# Every one is a SELECT. `assert_read_only` checks that claim against this text.

Q_LOGINS_SINCE = text("""
    SELECT u.email, u.status::text AS status, u.last_login_at, u.last_login_ip,
           u.is_seed_account,
           COALESCE(string_agg(DISTINCT r.slug, ','), '') AS roles
      FROM users u
      LEFT JOIN user_roles ur ON ur.user_id = u.id
      LEFT JOIN roles r ON r.id = ur.role_id
     WHERE u.last_login_at IS NOT NULL
       AND u.last_login_at >= :since
     GROUP BY u.id, u.email, u.status, u.last_login_at, u.last_login_ip,
              u.is_seed_account
     ORDER BY u.last_login_at DESC
""")

Q_PRIVILEGED = text("""
    SELECT u.email, u.status::text AS status, u.is_superadmin, u.created_at,
           u.last_login_at, u.is_seed_account,
           string_agg(DISTINCT r.slug, ',') AS roles
      FROM users u
      JOIN user_roles ur ON ur.user_id = u.id
      JOIN roles r ON r.id = ur.role_id
     WHERE u.is_superadmin = true
        OR r.slug IN ('super_user', 'org_admin', 'head_of_admin', 'school_admin',
                      'principal', 'accountant')
        OR r.permissions::text LIKE '%"*"%'
     GROUP BY u.id, u.email, u.status, u.is_superadmin, u.created_at,
              u.last_login_at, u.is_seed_account
     ORDER BY u.created_at DESC
""")

Q_USERS_TOUCHED = text("""
    SELECT u.email, u.status::text AS status, u.created_at, u.updated_at,
           (u.created_at >= :since) AS is_new,
           u.force_password_change, u.is_seed_account
      FROM users u
     WHERE u.created_at >= :since OR u.updated_at >= :since
     ORDER BY GREATEST(u.created_at, u.updated_at) DESC
""")

Q_MARKS_TOUCHED = text("""
    SELECT 'student_assessment_scores' AS store,
           count(*) AS rows_touched,
           min(updated_at) AS earliest,
           max(updated_at) AS latest
      FROM student_assessment_scores
     WHERE updated_at >= :since
    UNION ALL
    SELECT 'grades', count(*), min(updated_at), max(updated_at)
      FROM grades
     WHERE updated_at >= :since
""")

Q_MONEY_TOUCHED = text("""
    SELECT 'invoices' AS store, count(*) AS rows_touched,
           min(updated_at) AS earliest, max(updated_at) AS latest
      FROM invoices
     WHERE updated_at >= :since
    UNION ALL
    SELECT 'payment_transactions', count(*), min(updated_at), max(updated_at)
      FROM payment_transactions
     WHERE updated_at >= :since
""")

Q_AUDIT_BY_ACTION = text("""
    SELECT action::text AS action, severity, count(*) AS n,
           min(created_at) AS earliest, max(created_at) AS latest
      FROM audit_logs
     WHERE created_at >= :since
     GROUP BY action, severity
     ORDER BY n DESC
""")

Q_AUDIT_BY_ACTOR = text("""
    SELECT COALESCE(actor_email, '<no actor>') AS actor, count(*) AS n,
           count(DISTINCT actor_ip) AS distinct_ips,
           max(created_at) AS latest
      FROM audit_logs
     WHERE created_at >= :since
     GROUP BY actor_email
     ORDER BY n DESC
""")

Q_AUDIT_IPS = text("""
    SELECT COALESCE(actor_ip, '<none>') AS ip, count(*) AS n,
           count(DISTINCT actor_email) AS distinct_actors,
           min(created_at) AS first_seen, max(created_at) AS last_seen
      FROM audit_logs
     WHERE created_at >= :since
     GROUP BY actor_ip
     ORDER BY n DESC
""")

Q_FAILED_LOGINS = text("""
    SELECT COALESCE(actor_email, '<unknown>') AS actor,
           COALESCE(actor_ip, '<none>') AS ip,
           count(*) AS attempts, max(created_at) AS latest
      FROM audit_logs
     WHERE created_at >= :since
       AND action::text ILIKE '%login_failed%'
     GROUP BY actor_email, actor_ip
     ORDER BY attempts DESC
""")

Q_LOCKED_OR_PRESSURED = text("""
    SELECT email, status::text AS status, failed_login_attempts, last_login_at
      FROM users
     WHERE lower(status::text) IN ('locked', 'suspended')
        OR (failed_login_attempts IS NOT NULL
            AND failed_login_attempts <> '0'
            AND failed_login_attempts <> '')
     ORDER BY email
""")

Q_STUDENT_LOGIN_SUMMARY = text("""
    SELECT count(*) AS student_users,
           count(*) FILTER (WHERE u.last_login_at IS NOT NULL) AS ever_logged_in,
           count(*) FILTER (WHERE u.last_login_at >= :since) AS logged_in_since,
           count(*) FILTER (WHERE lower(u.status::text) = 'active') AS active
      FROM users u
      JOIN user_roles ur ON ur.user_id = u.id
      JOIN roles r ON r.id = ur.role_id
     WHERE r.slug = 'student'
""")

#: The three accounts whose passwords were in the source, by name.
Q_NAMED_ACCOUNTS = text("""
    SELECT email, status::text AS status, last_login_at, last_login_ip,
           updated_at, force_password_change
      FROM users
     WHERE email IN ('ict@fairviewschoolng.com',
                     'mathematics@fairviewschoolng.com',
                     'abebi.abioye@fairviewschoolng.com')
     ORDER BY email
""")


def table(rows, headers, limit=None, indent="   "):
    rows = list(rows)
    shown = rows[:limit] if limit else rows
    if not shown:
        print(f"{indent}(none)")
        return
    cols = [str(h) for h in headers]
    data = [[("" if v is None else str(v)) for v in r] for r in shown]
    widths = [max(len(cols[i]), *(len(d[i]) for d in data)) for i in range(len(cols))]
    widths = [min(w, 44) for w in widths]
    line = indent + "  ".join(c[:widths[i]].ljust(widths[i]) for i, c in enumerate(cols))
    print(line)
    print(indent + "  ".join("-" * w for w in widths))
    for d in data:
        print(indent + "  ".join(d[i][:widths[i]].ljust(widths[i]) for i in range(len(cols))))
    if limit and len(rows) > limit:
        print(f"{indent}... and {len(rows) - limit} more (raise --limit to see them)")


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--since", default=EXPOSURE_DATE,
                    help=f"ISO date to measure from (default {EXPOSURE_DATE}, "
                         "the day the credentials file was committed)")
    ap.add_argument("--limit", type=int, default=25,
                    help="rows per section (default 25)")
    args, _ = ap.parse_known_args()

    assert_read_only()

    # asyncpg binds a timestamptz parameter STRICTLY: a string raises DataError
    # rather than being coerced, so the window is parsed to an aware datetime
    # here. Caught by rehearsing against a restored dump.
    try:
        since = datetime.fromisoformat(args.since)
    except ValueError:
        sys.exit(f"--since must be an ISO date, e.g. {EXPOSURE_DATE}; got {args.since!r}")
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    url = dsn()
    engine = create_async_engine(url, echo=False, connect_args=connect_args(url))
    p = {"since": since}

    try:
        async with engine.connect() as conn:       # connect(), not begin()
            print("=" * 74)
            print(f"READ-ONLY tampering audit. Nothing is written.")
            print(f"Window: everything at or after {args.since}")
            print("=" * 74)

            print("\n-- 1. THE QUESTION THAT MATTERS: sign-ins since the exposure --")
            r = (await conn.execute(Q_LOGINS_SINCE, p)).all()
            print(f"   {len(r)} account(s) signed in at or after {args.since}")
            table(r, ["email", "status", "last_login_at", "ip", "seed", "roles"],
                  args.limit)

            print("\n-- 2. the three accounts whose passwords were in the source --")
            table((await conn.execute(Q_NAMED_ACCOUNTS, p)).all(),
                  ["email", "status", "last_login_at", "ip", "updated_at", "force_pw"])

            print("\n-- 3. every student account, in summary --")
            table((await conn.execute(Q_STUDENT_LOGIN_SUMMARY, p)).all(),
                  ["student_users", "ever_logged_in", "logged_in_since", "active"])

            print("\n-- 4. privileged accounts (wildcard, superadmin or admin slug) --")
            r = (await conn.execute(Q_PRIVILEGED, p)).all()
            print(f"   {len(r)} privileged account(s). Check every one you do not recognise.")
            table(r, ["email", "status", "superadmin", "created_at", "last_login",
                      "seed", "roles"], args.limit)

            print("\n-- 5. accounts created or modified in the window --")
            r = (await conn.execute(Q_USERS_TOUCHED, p)).all()
            print(f"   {len(r)} account(s) touched; "
                  f"{sum(1 for x in r if x.is_new)} newly created")
            table(r, ["email", "status", "created_at", "updated_at", "is_new",
                      "force_pw", "seed"], args.limit)

            print("\n-- 6. marks changed in the window (BOTH stores) --")
            table((await conn.execute(Q_MARKS_TOUCHED, p)).all(),
                  ["store", "rows_touched", "earliest", "latest"])

            print("\n-- 7. money changed in the window --")
            table((await conn.execute(Q_MONEY_TOUCHED, p)).all(),
                  ["store", "rows_touched", "earliest", "latest"])

            print("\n-- 8. audit log by action --")
            table((await conn.execute(Q_AUDIT_BY_ACTION, p)).all(),
                  ["action", "severity", "n", "earliest", "latest"], args.limit)

            print("\n-- 9. audit log by actor --")
            table((await conn.execute(Q_AUDIT_BY_ACTOR, p)).all(),
                  ["actor", "events", "distinct_ips", "latest"], args.limit)

            print("\n-- 10. every distinct actor IP in the window --")
            print("   An address you do not recognise is the clearest signal here.")
            table((await conn.execute(Q_AUDIT_IPS, p)).all(),
                  ["ip", "events", "distinct_actors", "first_seen", "last_seen"],
                  args.limit)

            print("\n-- 11. failed logins (what credential stuffing looks like) --")
            table((await conn.execute(Q_FAILED_LOGINS, p)).all(),
                  ["actor", "ip", "attempts", "latest"], args.limit)

            print("\n-- 12. locked, suspended, or carrying failed attempts --")
            table((await conn.execute(Q_LOCKED_OR_PRESSURED, p)).all(),
                  ["email", "status", "failed_attempts", "last_login_at"], args.limit)

            print("\n" + "=" * 74)
            print("Read-only. Connection closed without a transaction.")
            print("Sections 1, 2 and 10 are the ones to read first: a sign-in by an")
            print("exposed account, or from an address you do not know, is the only")
            print("direct evidence that the leak was used.")
            print("=" * 74)
    except Exception as exc:                       # noqa: BLE001 - redaction matters more
        sys.exit(f"audit failed: {redact(str(exc))}")
    finally:
        await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
