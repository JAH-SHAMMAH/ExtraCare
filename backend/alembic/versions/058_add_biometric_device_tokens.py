"""Biometric: per-device ingest tokens (RELEASE BLOCKER close)

Revision ID: 058_biometric_tokens
Revises: 057_acceptance_forms
Create Date: 2026-07-12 14:00:00.000000

Additive + reversible. Adds a per-device ingest credential to biometric_devices
so POST /biometric/ingest is authenticated by a scoped, rotatable/revocable
device token instead of a broad settings:write admin session. Only the SHA-256
hash is stored; the plaintext is shown once at issue time.
"""
from alembic import op
import sqlalchemy as sa


revision = "058_biometric_tokens"
down_revision = "057_acceptance_forms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("biometric_devices") as batch:
        batch.add_column(sa.Column("token_hash", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("token_prefix", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("token_issued_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_unique_constraint("uq_biometric_devices_token_hash", ["token_hash"])


def downgrade() -> None:
    with op.batch_alter_table("biometric_devices") as batch:
        batch.drop_constraint("uq_biometric_devices_token_hash", type_="unique")
        batch.drop_column("token_issued_at")
        batch.drop_column("token_prefix")
        batch.drop_column("token_hash")
