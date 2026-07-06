"""Add payment_gateways (per-org gateway credentials, secrets encrypted at rest)

Revision ID: 029_add_payment_gateways
Revises: 028_add_pickups
Create Date: 2026-07-05 12:00:00.000000

Additive + reversible. secret_key / webhook_secret are Text at the DB level; the
application layer (EncryptedStr / app.services.crypto) stores AES-256-GCM ciphertext
in them. See ENCRYPTION_SERVICE_SPEC.md.
"""

from alembic import op
import sqlalchemy as sa


revision = "029_add_payment_gateways"
down_revision = "028_add_pickups"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
        sa.Column("secret_key", sa.Text(), nullable=True),        # AES-256-GCM ciphertext
        sa.Column("webhook_secret", sa.Text(), nullable=True),    # AES-256-GCM ciphertext
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id", name="pk_payment_gateways"),
    )
    op.create_index("ix_payment_gateways_id", "payment_gateways", ["id"])
    op.create_index("ix_payment_gateways_org_id", "payment_gateways", ["org_id"])
    op.create_index("ix_payment_gateways_org", "payment_gateways", ["org_id"])


def downgrade() -> None:
    op.drop_table("payment_gateways")
