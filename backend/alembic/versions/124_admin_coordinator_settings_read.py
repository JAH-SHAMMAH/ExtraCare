"""Grant settings:read to administrative_coordinator (Report Setup access)

Revision ID: 124_admin_coord_settings
Revises: 123_narrow_parent_payments
Create Date: 2026-08-26

Data migration. Report Setup is gated on `settings:read` (frontend access map +
the router's settings gate), and the Administrative Coordinator held every other
scope in the report section but not this one -- so the whole Secondary/Junior/
Nursery Report tree was reachable except its first item. Educare's equivalent role
reaches Report Setup, so the scope is granted.

Note this also opens the other `settings:read` pages (Attendance Setup, Feedback
Settings) -- accepted as appropriate for an admin-tier role.

Only `administrative_coordinator` is touched. manager / vice_principal /
deputy_head alias the same in-code preset but are deliberately NOT widened.

New orgs get this from SCHOOL_PERMISSION_PRESETS; this backfills EXISTING role
rows. Idempotent -- safe to re-run.
"""
import json

from alembic import op
import sqlalchemy as sa


revision = "124_admin_coord_settings"
down_revision = "123_narrow_parent_payments"
branch_labels = None
depends_on = None

_SLUG = "administrative_coordinator"
_GRANT = "settings:read"


def _load(perms):
    if perms is None:
        return []
    if isinstance(perms, (str, bytes)):
        try:
            return json.loads(perms)
        except Exception:
            return []
    return list(perms)


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, slug, permissions FROM roles")).fetchall()
    for rid, slug, perms in rows:
        if slug != _SLUG:
            continue
        plist = _load(perms)
        if "*" in plist or _GRANT in plist:
            continue
        conn.execute(
            sa.text("UPDATE roles SET permissions = :p WHERE id = :id"),
            {"p": json.dumps(plist + [_GRANT]), "id": rid},
        )


def downgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, slug, permissions FROM roles")).fetchall()
    for rid, slug, perms in rows:
        if slug != _SLUG:
            continue
        plist = _load(perms)
        keep = [x for x in plist if x != _GRANT]
        if keep != plist:
            conn.execute(
                sa.text("UPDATE roles SET permissions = :p WHERE id = :id"),
                {"p": json.dumps(keep), "id": rid},
            )
