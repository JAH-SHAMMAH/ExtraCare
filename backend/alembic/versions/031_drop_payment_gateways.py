"""Drop payment_gateways table (converged onto TenantPaymentSettings)

Revision ID: 031_drop_payment_gateways
Revises: 030_grant_payment_gateways
Create Date: 2026-07-05 14:00:00.000000

The Payment Gateways feature was initially built on a NEW `payment_gateways`
table (029), but the billing subsystem already had `tenant_payment_settings`
(with encrypted_* columns) that the resolver consumes. We converged the gateway
CRUD onto `TenantPaymentSettings` and dropped the duplicate. The RBAC namespace
grant (030) is retained. down_revision recreates the dropped table.
"""

from alembic import op
import sqlalchemy as sa


revision = "031_drop_payment_gateways"
down_revision = "030_grant_payment_gateways"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("payment_gateways")


def downgrade() -> None:
    op.create_table(
        "payment_gateways",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("label", sa.String(120), nullable=True),
        sa.Column("mode", sa.String(10), nullable=False, server_default="test"),
        sa.Column("public_key", sa.String(255), nullable=True),
        sa.Column("secret_key", sa.Text(), nullable=True),
        sa.Column("webhook_secret", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id", name="pk_payment_gateways"),
    )
    op.create_index("ix_payment_gateways_id", "payment_gateways", ["id"])
    op.create_index("ix_payment_gateways_org_id", "payment_gateways", ["org_id"])
    op.create_index("ix_payment_gateways_org", "payment_gateways", ["org_id"])
