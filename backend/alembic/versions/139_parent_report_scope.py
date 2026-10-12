"""Split the staff report scope from the own-child one, on existing roles

Revision ID: 139_parent_report_scope
Revises: 138_subject_section_required
Create Date: 2026-10-12 06:00:00.000000

`school:reports:read` was doing two unrelated jobs: "may read reports across the
school", which every staff report screen is gated on, and "may read my own
child's card", which a parent needs. The parent and pupil presets carried it, so
three staff report groups appeared in their sidebar and -- far worse --
`/report-cards-bulk` answered them with a whole class's report cards, having no
per-pupil ownership check of its own.

The code change splits the scope. This migration moves the roles ALREADY IN THE
DATABASE across, because permissions are stored per role row: without it the
preset change affects only roles created after the deploy, and every existing
parent and pupil account keeps the staff scope.

~~~ WHY THIS IS ELEMENT-LEVEL, NOT A WHOLESALE OVERWRITE ~~~
Migration 121 did the same kind of job by replacing the role's entire
permissions list with a constant. That is simpler and it is lossy: anything an
administrator had added to a role by hand is silently discarded. This one
removes exactly one string and adds exactly one, leaving every other scope on
the row alone.

~~~ WHICH ROLES IT TOUCHES ~~~
Not "slug starts with parent". A staff role called "Parent Liaison" would match
that and legitimately needs the staff scope, and stripping it would break a
real workflow. The test is on the DATA instead: a role is treated as
parent/pupil-derived when everything it holds, apart from the scope being
replaced, is drawn from the self-service presets. A cloned parent role passes;
any role carrying a staff scope (school:students:read, school_admin:*, ...)
does not.

Anything holding `school:reports:read` that does NOT pass that test is left
untouched and LOGGED, so it shows up in the deploy output for review rather
than being changed on a guess.

Idempotent: a role already carrying the own-read scope and not the staff one is
left alone, so re-running changes nothing.
"""
import json
import logging

import sqlalchemy as sa
from alembic import op

# 23 characters. `alembic_version.version_num` is varchar(32), and the first
# draft of this file used "139_split_parent_pupil_report_scope" -- 36 -- so
# `alembic upgrade head` ran every migration and then died on the final version
# bump with StringDataRightTruncationError, rolling the whole chain back. It
# would have failed the same way on the deploy.
revision = "139_parent_report_scope"
down_revision = "138_subject_section_required"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")

STAFF_SCOPE = "school:reports:read"
OWN_SCOPE = "school:reports:own:read"

#: The self-service scopes a parent or pupil may hold. Copied here rather than
#: imported from app.models.role on purpose: a migration has to keep describing
#: the world as it was when it ran, and importing today's preset would make the
#: behaviour of this file change under later edits.
SELF_SERVICE_SCOPES = {
    # parent
    "payments:own:read",
    "school:attendance:read",
    "school:feedback:read",
    "school:journals:read",
    # pupil
    "school:cbt:sit",
    "school:classroom:read",
    "school:clubs:read",
    "school:lessons:read",
    "school:library:read",
    "school:timetable:read",
    "school:voting:submit",
    # the two being swapped
    STAFF_SCOPE,
    OWN_SCOPE,
}


def _rows(conn):
    """Every role with a permissions list, as (id, name, slug, perms)."""
    res = conn.execute(sa.text(
        "SELECT id, name, slug, permissions FROM roles WHERE permissions IS NOT NULL"))
    out = []
    for rid, name, slug, perms in res:
        if isinstance(perms, str):          # SQLite hands back JSON text
            try:
                perms = json.loads(perms)
            except (TypeError, ValueError):
                continue
        if isinstance(perms, list):
            out.append((rid, name, slug, perms))
    return out


def _is_self_service(perms: list[str]) -> bool:
    """True when nothing on this role reaches beyond the self-service presets."""
    return bool(perms) and set(perms) <= SELF_SERVICE_SCOPES


def _write(conn, rid: str, perms: list[str]) -> None:
    # JSON as a bound parameter, so the column's own type handles the dialect
    # difference instead of this file hand-rolling quoting per backend.
    conn.execute(
        sa.text("UPDATE roles SET permissions = :p WHERE id = :i").bindparams(
            sa.bindparam("p", type_=sa.JSON()), sa.bindparam("i")),
        {"p": perms, "i": rid},
    )


def _swap(conn, remove: str, add: str) -> None:
    changed = skipped = 0
    for rid, name, slug, perms in _rows(conn):
        if remove not in perms:
            continue
        if not _is_self_service(perms):
            # A staff role. Report it; do not touch it.
            beyond = sorted(set(perms) - SELF_SERVICE_SCOPES)
            logger.warning(
                "139: role %r (slug=%s) holds %s but is NOT parent/pupil-derived "
                "-- left unchanged. Scopes beyond the self-service presets: %s",
                name, slug, remove, ", ".join(beyond[:8]) or "(none)",
            )
            skipped += 1
            continue
        new = [p for p in perms if p != remove]
        if add not in new:
            new.append(add)
        _write(conn, rid, new)
        logger.info("139: role %r (slug=%s): %s -> %s", name, slug, remove, add)
        changed += 1
    logger.warning("139: %d role(s) moved from %s to %s; %d staff role(s) "
                   "holding %s left for review", changed, remove, add, skipped, remove)


def upgrade() -> None:
    _swap(op.get_bind(), remove=STAFF_SCOPE, add=OWN_SCOPE)


def downgrade() -> None:
    # Symmetric, and equally element-level: a role that was moved goes back,
    # and nothing else is disturbed. The same self-service test applies, so a
    # staff role that happens to hold the own-read scope is not given the staff
    # one by this downgrade.
    _swap(op.get_bind(), remove=OWN_SCOPE, add=STAFF_SCOPE)
