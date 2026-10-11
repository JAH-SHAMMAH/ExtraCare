#!/usr/bin/env python3
"""Deactivate the student accounts whose passwords were published. DRY RUN BY DEFAULT.

~~~ WHY ~~~
`backend/scripts/student_credentials_output.csv` was committed on 2026-08-23 with
450 rows of (student_id, email, temp_password), into a PUBLIC repository. Anyone
who read it can sign in as those pupils until the passwords stop working.

Deactivating the accounts stops that without deleting anything and without
needing 450 new passwords chosen now.

~~~ WHAT IT CHANGES, AND WHAT IT DOES NOT ~~~
Sets, for each matched account:
    status                -> 'inactive'
    force_password_change -> true

NOTHING ELSE. It does not delete a user, does not touch `hashed_password`, does
not touch the `students` roster, and does not touch marks, fees or enrolments. A
pupil's record and history are untouched; only the ability to sign in stops.

REVERSIBLE, and that is the point of the manifest. Every row's PREVIOUS status
and force_password_change are recorded before the change, so the manifest is
also the undo instructions. Reactivating is a matter of reading it back.

~~~ HOW IT REFUSES TO SURPRISE YOU ~~~
  * DRY RUN IS THE DEFAULT. Without --remove it writes the manifest, prints the
    summary, and changes nothing. The dry run executes the same selection the
    write would, so what it reports is what would happen -- not a prediction.
  * --remove is the apply flag, matching the convention every other destructive
    script in this repo follows.
  * --manifest <path> re-uses an APPROVED manifest instead of re-selecting. With
    it, the script touches exactly the accounts listed and refuses if the
    database no longer matches what the manifest recorded. That is what makes
    "approve the manifest, then apply" meaningful rather than ceremonial.
  * It will not touch a privileged account. A student role plus an admin role on
    one user is a configuration error, and deactivating it could lock an
    administrator out of the portal; those are reported and skipped.

~~~ WHERE THE MANIFEST GOES ~~~
C:\\Users\\SHAMMAH\\fairview-backups by default -- OUTSIDE OneDrive, which would
sync it to the cloud, and outside the repository, which is one `git add -A` from
committing a list of 450 pupils' emails. Override with --out.

THE MANIFEST HOLDS NO PASSWORD. Emails and ids only. The exposed passwords are
not read, not written and not needed: deactivation does not require knowing them.

~~~ CREDENTIALS ~~~
From DEACTIVATE_DATABASE_URL or a hidden prompt, never argv, never printed.
Deliberately not `DATABASE_URL`, which alembic and the app read.

    $env:DEACTIVATE_DATABASE_URL = "<address>"   # or leave unset and it prompts
    python -m scripts.deactivate_exposed_students                     # dry run
    python -m scripts.deactivate_exposed_students --manifest <file> --remove
    Remove-Item Env:\\DEACTIVATE_DATABASE_URL
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DEFAULT_OUT = Path(r"C:\Users\SHAMMAH\fairview-backups")
EXPOSURE_DATE = "2026-08-23"

#: Holding any of these alongside `student` means the account is not just a
#: pupil, and deactivating it could lock a person out of their real job.
PRIVILEGED_SLUGS = ("super_user", "org_admin", "head_of_admin", "school_admin",
                    "principal", "accountant", "teacher", "head_teacher")


def redact(message: str) -> str:
    return re.sub(r"(//)[^/\s:@]+:[^/\s@]+(@)", r"\1<redacted>:<redacted>\2", message)


def dsn() -> str:
    for a in sys.argv[1:]:
        if "://" in a:
            sys.exit("Do not pass the address as an argument -- it lands in shell "
                     "history and the process list. Set DEACTIVATE_DATABASE_URL, or "
                     "run with no address and type it at the hidden prompt.")
    raw = (os.environ.get("DEACTIVATE_DATABASE_URL") or "").strip()
    if not raw:
        raw = getpass.getpass(
            "DEACTIVATE_DATABASE_URL (hidden, not echoed, not stored): ").strip()
    if not raw:
        sys.exit("No address given. Set DEACTIVATE_DATABASE_URL or type one at the prompt.")
    parts = urlsplit(raw)
    scheme = ("postgresql+asyncpg" if parts.scheme in ("postgres", "postgresql")
              else parts.scheme)
    query = "&".join(q for q in parts.query.split("&")
                     if q and not q.lower().startswith("sslmode="))
    return urlunsplit((scheme, parts.netloc, parts.path, query, parts.fragment))


def connect_args(url: str) -> dict:
    host = (urlsplit(url).hostname or "").casefold()
    return {} if host in ("localhost", "127.0.0.1", "::1", "") else {"ssl": "require"}


# ── selection ───────────────────────────────────────────────────────────────

SELECT_STUDENTS = text("""
    SELECT u.id, u.email, u.status::text AS status, u.force_password_change,
           u.last_login_at, u.is_seed_account,
           string_agg(DISTINCT r.slug, ',') AS roles
      FROM users u
      JOIN user_roles ur ON ur.user_id = u.id
      JOIN roles r ON r.id = ur.role_id
     WHERE EXISTS (
            SELECT 1 FROM user_roles ur2
              JOIN roles r2 ON r2.id = ur2.role_id
             WHERE ur2.user_id = u.id AND r2.slug = 'student')
       AND u.is_deleted = false
     GROUP BY u.id, u.email, u.status, u.force_password_change,
              u.last_login_at, u.is_seed_account
     ORDER BY u.email
""")

VERIFY_ROW = text("""
    SELECT status::text AS status, force_password_change
      FROM users WHERE id = :id
""")

APPLY = text("""
    UPDATE users
       SET status = 'INACTIVE', force_password_change = true
     WHERE id = :id
""")


def manifest_path(out: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return out / f"deactivate_students_manifest_{stamp}.json"


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--remove", action="store_true",
                    help="apply the change. Without this nothing is written.")
    ap.add_argument("--manifest", type=Path, default=None,
                    help="apply exactly the accounts in this approved manifest")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help=f"where to write the manifest (default {DEFAULT_OUT})")
    args, _ = ap.parse_known_args()

    if args.remove and not args.manifest:
        sys.exit("--remove requires --manifest <file>: the manifest is what you "
                 "approve, and applying without one would act on a selection "
                 "nobody has read. Run the dry run first.")

    url = dsn()
    engine = create_async_engine(url, echo=False, connect_args=connect_args(url))

    try:
        # ── apply an approved manifest ──────────────────────────────────────
        if args.manifest:
            data = json.loads(args.manifest.read_text(encoding="utf-8"))
            rows = data["accounts"]
            print(f"manifest {args.manifest.name}: {len(rows)} account(s), "
                  f"written {data.get('generated_at')}")

            async with engine.begin() as conn:
                drifted, applied = [], 0
                for row in rows:
                    cur = (await conn.execute(VERIFY_ROW, {"id": row["id"]})).first()
                    if cur is None:
                        drifted.append((row["email"], "account no longer exists"))
                        continue
                    # The manifest recorded the state it expected to change FROM.
                    # If the database has moved since, stop: something else has
                    # touched these accounts and the manifest is no longer a
                    # description of reality.
                    if (cur.status != row["was_status"]
                            or bool(cur.force_password_change) != bool(row["was_force_password_change"])):
                        drifted.append((row["email"],
                                        f"now {cur.status}/{cur.force_password_change}, "
                                        f"manifest expected {row['was_status']}/"
                                        f"{row['was_force_password_change']}"))
                        continue
                    if not args.remove:
                        continue
                    await conn.execute(APPLY, {"id": row["id"]})
                    applied += 1

                if drifted:
                    print(f"\n{len(drifted)} account(s) DRIFTED from the manifest:")
                    for email, why in drifted[:20]:
                        print(f"   {email}: {why}")
                    if not args.remove:
                        print("\nDry run against the manifest -- nothing written.")
                        return 1
                    # Inside engine.begin(): raising rolls the whole thing back.
                    raise RuntimeError(
                        f"{len(drifted)} account(s) no longer match the manifest. "
                        "Nothing has been written. Re-run the dry run to produce a "
                        "fresh manifest and read it before applying.")

                if not args.remove:
                    print("\nDry run against the manifest: every account still "
                          "matches. Re-run with --remove to apply.")
                    return 0
                print(f"\nAPPLIED to {applied} account(s): status -> inactive, "
                      f"force_password_change -> true")
            return 0

        # ── dry run: select, write the manifest, change nothing ─────────────
        async with engine.connect() as conn:       # connect(), not begin()
            rows = (await conn.execute(SELECT_STUDENTS)).all()

        eligible, skipped = [], []
        for r in rows:
            slugs = set((r.roles or "").split(","))
            extra = sorted(slugs & set(PRIVILEGED_SLUGS))
            if extra:
                skipped.append((r.email, f"also holds {','.join(extra)}"))
                continue
            # `status` holds the enum NAME ("ACTIVE"), so fold case --
            # a lowercase comparison here would re-deactivate every
            # already-deactivated account on every run.
            if (r.status or "").lower() == "inactive" and r.force_password_change:
                skipped.append((r.email, "already deactivated"))
                continue
            eligible.append(r)

        print("=" * 74)
        print("DRY RUN -- nothing has been written.")
        print("=" * 74)
        print(f"   student accounts found      : {len(rows)}")
        print(f"   would be deactivated        : {len(eligible)}")
        print(f"   skipped                     : {len(skipped)}")
        ever = sum(1 for r in eligible if r.last_login_at is not None)
        print(f"   of those, have ever signed in: {ever}")
        print(f"   seed accounts among them     : "
              f"{sum(1 for r in eligible if r.is_seed_account)}")

        if skipped:
            print("\n   SKIPPED, with the reason:")
            for email, why in skipped[:25]:
                print(f"      {email}: {why}")
            if len(skipped) > 25:
                print(f"      ... and {len(skipped) - 25} more")

        print("\n   first 10 accounts that would change:")
        for r in eligible[:10]:
            print(f"      {r.email:44} {r.status:9} -> inactive"
                  f"   (force_pw {r.force_password_change} -> True)")
        if len(eligible) > 10:
            print(f"      ... and {len(eligible) - 10} more")

        args.out.mkdir(parents=True, exist_ok=True)
        path = manifest_path(args.out)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "reason": ("student_credentials_output.csv exposed 450 temp passwords "
                       f"in a public repository from {EXPOSURE_DATE}"),
            "change": {"status": "inactive", "force_password_change": True},
            "note": ("Contains NO password. `was_*` fields are the state to "
                     "restore if this is reverted."),
            "accounts": [
                {"id": r.id, "email": r.email,
                 "was_status": r.status,
                 "was_force_password_change": bool(r.force_password_change),
                 "roles": r.roles,
                 "ever_signed_in": r.last_login_at is not None}
                for r in eligible
            ],
            "skipped": [{"email": e, "reason": w} for e, w in skipped],
        }
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"\n   manifest written: {path}")
        print(f"   it holds NO password -- emails and ids only")
        print("\n   Read it, then apply with:")
        print(f"      python -m scripts.deactivate_exposed_students "
              f'--manifest "{path}" --remove')
        print("=" * 74)
    except Exception as exc:                       # noqa: BLE001
        sys.exit(f"failed: {redact(str(exc))}")
    finally:
        await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
