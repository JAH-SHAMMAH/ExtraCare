"""Backfill missing auditaction enum values (Postgres native-enum drift).

Revision ID: 096_auditaction_enum_backfill
Revises: 095_biometric_staff_commands
Create Date: 2026-07-27 00:00:00.000000

`audit_logs.action` is a NATIVE Postgres ENUM (`auditaction`) created by the
baseline migration with a fixed value set. Several `AuditAction` members added to
the Python enum since then were never added to the DB type, so writing an audit
row for any of them fails on Postgres with `invalid input value for enum` — which
500s the request that logged it. Most visibly: ROLE_SWITCHED, written by the
"My Roles" switch (POST /auth/switch-role), so role switching fails in prod even
though every test passes (SQLite/test enums are rebuilt from the current model).

The DB enum stores the member NAMES (e.g. 'ROLE_SWITCHED'), matching how the
baseline created it. This backfills every currently-missing name. Idempotent
(IF NOT EXISTS) and Postgres-only; on SQLite the enum is a CHECK recreated from
the model, so nothing to do.
"""
from alembic import op


revision = "096_auditaction_enum_backfill"
down_revision = "095_biometric_staff_commands"
branch_labels = None
depends_on = None

# Names present in the Python AuditAction enum but absent from the baseline
# Postgres type. Add-only + IF NOT EXISTS, so re-running is safe.
_MISSING = [
    "ROLE_SWITCHED",
    "ORG_INDUSTRY_CHANGED",
    "ORG_FEATURES_CHANGED",
    "ORG_ONBOARDING_ADVANCED",
    "PAYMENT_INITIATED",
    "PAYMENT_VERIFIED",
    "PAYMENT_FAILED",
    "SUBSCRIPTION_UPGRADED",
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # ALTER TYPE ... ADD VALUE prefers to run outside a transaction; autocommit_block
    # steps out of Alembic's migration transaction for exactly this.
    with op.get_context().autocommit_block():
        for name in _MISSING:
            op.execute(f"ALTER TYPE auditaction ADD VALUE IF NOT EXISTS '{name}'")


def downgrade() -> None:
    # Postgres has no DROP VALUE for an enum; the extra labels are harmless.
    pass
