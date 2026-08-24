"""Narrow the parent role's finance scope: payments:read -> payments:own:read

Revision ID: 123_narrow_parent_payments
Revises: 122_add_org_missing_columns
Create Date: 2026-08-24 07:10:00.000000

SECURITY data migration. The `parent` role carried `payments:read` -- the STAFF
finance scope. It gates ~18 org-wide routes (invoices, requisitions, petty cash,
cash book, store items/sales, wallet + parent-wallet + cooperative summaries and
their GL reconciliations), every one of which returned 200 to a parent account.
The lists were empty only because the school had no finance data yet; the
aggregate endpoints already exposed control-account and subledger balances.

`payments:own:read` is a three-part scope, so User.has_permission resolves it via
its two-part parent: staff holding `payments:read` satisfy it automatically (no
regression), while a parent holding only this does NOT satisfy `payments:read`.
The parent-facing routes (fee_payments.py, remita.py) were re-gated to the narrow
scope, so paying a child's fees still works.

New orgs get this from SCHOOL_PERMISSION_PRESETS; this backfills EXISTING parent
role rows. Idempotent -- safe to re-run.
"""
import json

from alembic import op
import sqlalchemy as sa


revision = "123_narrow_parent_payments"
down_revision = "122_add_org_missing_columns"
branch_labels = None
depends_on = None

_REMOVE = "payments:read"
_ADD = "payments:own:read"


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
        if slug != "parent":
            continue
        plist = _load(perms)
        if "*" in plist:
            continue
        new = [p for p in plist if p != _REMOVE]
        if _ADD not in new:
            new.append(_ADD)
        if new != plist:
            conn.execute(
                sa.text("UPDATE roles SET permissions = :p WHERE id = :id"),
                {"p": json.dumps(new), "id": rid},
            )


def downgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, slug, permissions FROM roles")).fetchall()
    for rid, slug, perms in rows:
        if slug != "parent":
            continue
        plist = _load(perms)
        new = [p for p in plist if p != _ADD]
        if _REMOVE not in new:
            new.append(_REMOVE)
        if new != plist:
            conn.execute(
                sa.text("UPDATE roles SET permissions = :p WHERE id = :id"),
                {"p": json.dumps(new), "id": rid},
            )
