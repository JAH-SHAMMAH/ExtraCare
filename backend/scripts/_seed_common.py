"""Shared safety guard + constants for the report-demo seed / teardown scripts.

The default is ALWAYS to refuse a production-looking database. Seeding production
is a DELIBERATE opt-in that requires BOTH SEED_DATABASE_URL (pointing at prod) and
SEED_ALLOW_PRODUCTION=yes-i-mean-it. The default safety never changes.
"""
from __future__ import annotations

import os

# A URL containing any of these is treated as production.
FORBIDDEN = ("onyz", "prod", "render.com", "amazonaws")

# Demo logins must be on the school's real login domain to pass the auth
# email-domain gate — so the domain is NO LONGER the "fake" marker. The
# authoritative marker is User.is_seed_account (set only by the seed script);
# the reserved "seed-" local-part prefix is a secondary, human-visible sanity
# check. Both scripts require is_seed_account=True AND a seed email.
SEED_EMAIL_DOMAIN = "fairviewschoolng.com"
SEED_PREFIX = "seed-"
LEGACY_SEED_DOMAIN = "fairview.seed"      # the earlier run's fake domain (still purge-able)
SEED_PASSWORD = "FairviewSeed#2026"
SEED_EMAILS = (
    f"{SEED_PREFIX}superuser@{SEED_EMAIL_DOMAIN}",
    f"{SEED_PREFIX}classteacher@{SEED_EMAIL_DOMAIN}",
    f"{SEED_PREFIX}subjectteacher@{SEED_EMAIL_DOMAIN}",
    f"{SEED_PREFIX}hr@{SEED_EMAIL_DOMAIN}",
)


def is_seed_email(email: str | None) -> bool:
    """Secondary sanity marker: a provably-seed address — the reserved 'seed-'
    prefix on the school domain, OR the legacy fake @fairview.seed domain. Never
    true for a real staff/student address."""
    e = (email or "").strip().lower()
    return (e.startswith(SEED_PREFIX) and e.endswith("@" + SEED_EMAIL_DOMAIN)) or e.endswith("@" + LEGACY_SEED_DOMAIN)

# Every non-account demo row is name-marked so teardown can find exactly its own
# data and nothing real.
SEED_MARKER = "[SEED]"
DEMO_CLASS_NAME = "[SEED] Report Demo Class"
DEMO_SUBJECT_NAME = "[SEED] Report Demo Subject"
DEMO_STUDENT_PREFIX = "SEED-"


def target_url_or_exit() -> str:
    """Resolve SEED_DATABASE_URL, applying the production opt-in guard.

    - No SEED_DATABASE_URL              -> refuse.
    - Prod-looking URL, no opt-in       -> refuse (the unchanged default).
    - Prod-looking URL + opt-in flag    -> allow, with a loud banner.
    - Non-prod URL                      -> allow.
    """
    url = os.environ.get("SEED_DATABASE_URL")
    if not url:
        raise SystemExit("Set SEED_DATABASE_URL to the target database (production is refused by default).")
    if any(bad in url.lower() for bad in FORBIDDEN):
        if os.environ.get("SEED_ALLOW_PRODUCTION") != "yes-i-mean-it":
            raise SystemExit(
                f"Refusing to run: '{url}' looks like PRODUCTION.\n"
                "This is the default safety guard and it stays in place.\n"
                "To act on production ON PURPOSE, set BOTH:\n"
                "    SEED_DATABASE_URL=<the prod url>\n"
                "    SEED_ALLOW_PRODUCTION=yes-i-mean-it")
        print("\n*** PRODUCTION MODE ENABLED (SEED_ALLOW_PRODUCTION=yes-i-mean-it) ***")
        print("*** Proceeding against a production-looking database on purpose. ***\n")
    return url
