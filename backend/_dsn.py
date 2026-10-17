"""The database address for the ad-hoc diagnostic scripts in this directory.

~~~ WHY THIS EXISTS ~~~
Thirty-nine scripts in `backend/` and `backend/scripts/` each carried a full
PostgreSQL connection string INLINE, complete with the password:

    conn = await asyncpg.connect("postgresql://<user>:<password>@host/db", ssl="require")

They were one-off diagnostics — `check_classes.py`, `audit_teacher_accounts.py`,
`dryrun_create_sections.py` — written against the live database and committed
with the credential still in them. The repository was public, so two live
database passwords were readable by anyone. This module is where the address
comes from now, and no tracked file holds one.

~~~ THE ENV VAR IS DELIBERATELY NOT `DATABASE_URL` ~~~
`DATABASE_URL` is what alembic, the app and `docker-compose` read. Setting it in
a shell so that a read-only diagnostic could run would arm every one of them:
one absent-minded `alembic upgrade head` in that shell afterwards would migrate
the live database. `ADHOC_DATABASE_URL` cannot be picked up by anything else.

NEVER FROM ARGV. A DSN passed as an argument lands in shell history and in the
process list, where other users on the machine can read it. If the variable is
unset the script prompts, hidden, and the value is never echoed, logged or
written to a file.

Usage, at the top of a diagnostic script:

    from _dsn import dsn, asyncpg_kwargs
    conn = await asyncpg.connect(dsn(), **asyncpg_kwargs(dsn()))

or, more usually, just:

    conn = await asyncpg.connect(dsn(), ssl="require")
"""
from __future__ import annotations

import getpass
import os
import sys
from urllib.parse import urlsplit, urlunsplit

ENV_VAR = "ADHOC_DATABASE_URL"

_cached: str | None = None


def dsn(*, for_sqlalchemy: bool = False) -> str:
    """The address, from the environment or a hidden prompt. Never printed.

    Cached for the life of the process so a script that connects twice does not
    prompt twice.

    `for_sqlalchemy=True` returns the `postgresql+asyncpg://` form that
    SQLAlchemy needs. The plain form is what libpq tools and asyncpg itself
    want — passing `+asyncpg` to `pg_dump` or `psql` is a hard error, and that
    confusion has cost time before.
    """
    global _cached
    if _cached is None:
        for a in sys.argv[1:]:
            if not a.startswith("--") and "://" in a:
                sys.exit(
                    f"Do not pass the database address as an argument: it would be "
                    f"recorded in shell history and visible in the process list. "
                    f"Set {ENV_VAR} instead, or run with no address and type it at "
                    f"the hidden prompt."
                )
        raw = (os.environ.get(ENV_VAR) or "").strip()
        if not raw:
            raw = getpass.getpass(
                f"{ENV_VAR} (hidden, not echoed, not stored): ").strip()
        if not raw:
            sys.exit(f"No database address given. Set {ENV_VAR} or type one at the prompt.")
        _cached = raw

    parts = urlsplit(_cached)
    scheme = parts.scheme
    if for_sqlalchemy:
        if scheme in ("postgres", "postgresql"):
            scheme = "postgresql+asyncpg"
        # asyncpg rejects sslmode as a query parameter; TLS is set via connect_args.
        query = "&".join(q for q in parts.query.split("&")
                         if q and not q.lower().startswith("sslmode="))
        return urlunsplit((scheme, parts.netloc, parts.path, query, parts.fragment))
    if scheme == "postgresql+asyncpg":
        scheme = "postgresql"
    return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))


def needs_tls() -> bool:
    """TLS everywhere except a loopback host.

    A hosted database requires it; a scratch server restored from a dump locally
    has no certificate, and a script that cannot be rehearsed locally is one
    whose first run is against production.
    """
    host = (urlsplit(dsn()).hostname or "").casefold()
    return host not in ("localhost", "127.0.0.1", "::1", "")


def asyncpg_kwargs() -> dict:
    """`ssl=` for asyncpg.connect, or nothing for a local server."""
    return {"ssl": "require"} if needs_tls() else {}


def sqlalchemy_connect_args() -> dict:
    """`connect_args=` for create_async_engine."""
    return {"ssl": "require"} if needs_tls() else {}
