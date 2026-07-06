"""Grant payment_gateways:read/write to existing org_admin roles

Revision ID: 030_grant_payment_gateways
Revises: 029_add_payment_gateways
Create Date: 2026-07-05 12:10:00.000000

Data migration. Managing gateway API secrets is org_admin-only, on the SEPARATE
`payment_gateways` namespace (not a `payments:*` sub-scope, which accountants/
managers would inherit). New orgs get these via SCHOOL_PERMISSION_PRESETS; this
backfills EXISTING org_admin role rows. Idempotent. Skips roles that already hold
`*` (they cover it) — but org_admin holds `payments:*`, NOT `*`, so it needs these.
"""
import json

from alembic import op
import sqlalchemy as sa


revision = "030_grant_payment_gateways"
down_revision = "029_add_payment_gateways"
branch_labels = None
depends_on = None

_GRANTS = ("payment_gateways:read", "payment_gateways:write")


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
        if slug != "org_admin":
            continue
        plist = _load(perms)
        if "*" in plist:
            continue
        add = [g for g in _GRANTS if g not in plist]
        if add:
            conn.execute(
                sa.text("UPDATE roles SET permissions = :p WHERE id = :id"),
                {"p": json.dumps(plist + add), "id": rid},
            )


def downgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, slug, permissions FROM roles")).fetchall()
    for rid, slug, perms in rows:
        if slug != "org_admin":
            continue
        plist = _load(perms)
        keep = [x for x in plist if x not in _GRANTS]
        if keep != plist:
            conn.execute(
                sa.text("UPDATE roles SET permissions = :p WHERE id = :id"),
                {"p": json.dumps(keep), "id": rid},
            )
