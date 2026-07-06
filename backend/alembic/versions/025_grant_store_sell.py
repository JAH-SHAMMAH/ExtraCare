"""Grant store:sell to existing finance roles (Cashier RBAC for POS sales)

Revision ID: 025_grant_store_sell
Revises: 024_add_store_sales
Create Date: 2026-07-04 15:00:00.000000

Data migration. Store POS sale/void moved from `payments:post` to a narrow
`store:sell` gate. Grant it to the roles that could already sell so they keep the
ability: org_admin (→ store:*), accountant (→ store:sell). New orgs also get a
`cashier` preset (store:sell + payments:read) via SCHOOL_PERMISSION_PRESETS; this
migration only backfills EXISTING role rows. Idempotent.
"""
import json

from alembic import op
import sqlalchemy as sa


revision = "025_grant_store_sell"
down_revision = "024_add_store_sales"
branch_labels = None
depends_on = None


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
        plist = _load(perms)
        add = None
        if slug == "org_admin" and "store:*" not in plist and "*" not in plist:
            add = "store:*"
        elif slug == "accountant" and "store:sell" not in plist and "store:*" not in plist:
            add = "store:sell"
        if add:
            conn.execute(
                sa.text("UPDATE roles SET permissions = :p WHERE id = :id"),
                {"p": json.dumps(plist + [add]), "id": rid},
            )


def downgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, slug, permissions FROM roles")).fetchall()
    for rid, slug, perms in rows:
        plist = _load(perms)
        drop = {"org_admin": "store:*", "accountant": "store:sell"}.get(slug)
        if drop and drop in plist:
            conn.execute(
                sa.text("UPDATE roles SET permissions = :p WHERE id = :id"),
                {"p": json.dumps([x for x in plist if x != drop]), "id": rid},
            )
