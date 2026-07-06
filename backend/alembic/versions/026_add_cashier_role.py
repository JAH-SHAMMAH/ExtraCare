"""Create the Cashier role for existing school orgs (POS till operator)

Revision ID: 026_add_cashier_role
Revises: 025_grant_store_sell
Create Date: 2026-07-04 15:30:00.000000

Data migration. New orgs get the `cashier` preset via SCHOOL_PERMISSION_PRESETS at
seed time; this backfills a Cashier role (`payments:read` + `store:sell`) for
EXISTING set-up school orgs (those that already have an org_admin role) so real
till staff can be assigned it instead of `payments:post`. Idempotent.
"""
import json
import uuid

from alembic import op
import sqlalchemy as sa


revision = "026_add_cashier_role"
down_revision = "025_grant_store_sell"
branch_labels = None
depends_on = None

CASHIER_PERMS = json.dumps(["payments:read", "store:sell"])


def upgrade() -> None:
    conn = op.get_bind()
    org_ids = [r[0] for r in conn.execute(sa.text("SELECT DISTINCT org_id FROM roles WHERE slug = 'org_admin'")).fetchall()]
    for org_id in org_ids:
        exists = conn.execute(
            sa.text("SELECT 1 FROM roles WHERE org_id = :o AND slug = 'cashier' LIMIT 1"), {"o": org_id}
        ).fetchone()
        if exists:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO roles (id, name, slug, description, permissions, is_system, color, org_id, created_at, updated_at) "
                "VALUES (:id, 'Cashier', 'cashier', :desc, :perms, 1, NULL, :org, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"id": str(uuid.uuid4()), "desc": "School-store till operator (POS sales only).",
             "perms": CASHIER_PERMS, "org": org_id},
        )


def downgrade() -> None:
    conn = op.get_bind()
    # Remove only unused system cashier roles (never delete a role that has members).
    conn.execute(sa.text(
        "DELETE FROM roles WHERE slug = 'cashier' AND is_system = 1 "
        "AND id NOT IN (SELECT role_id FROM user_roles)"
    ))
