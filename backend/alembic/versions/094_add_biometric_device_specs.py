"""Biometric: device hardware specs (Device Information tab)

Revision ID: 094_biometric_device_specs
Revises: 093_bank_ledger_account
Create Date: 2026-07-24 08:00:00.000000

Additive + reversible. Adds the device spec columns surfaced on the Manage
Biometric → Device Information tab (model name, vendor, firmware/fingerprint/
face versions, volume, language, MAC, storage, attendance-log capacity).
"""
from alembic import op
import sqlalchemy as sa


revision = "094_biometric_device_specs"
down_revision = "093_bank_ledger_account"
branch_labels = None
depends_on = None

_COLS = [
    ("model_name", sa.String(length=100)),
    ("vendor", sa.String(length=100)),
    ("device_type", sa.String(length=100)),
    ("volume", sa.Integer()),
    ("language", sa.String(length=40)),
    ("firmware_version", sa.String(length=40)),
    ("fingerprint_version", sa.String(length=20)),
    ("face_version", sa.String(length=20)),
    ("mac_address", sa.String(length=40)),
    ("storage_used_percent", sa.Integer()),
    ("attendance_log_capacity", sa.Integer()),
    ("current_attendance_log", sa.Integer()),
]


def upgrade() -> None:
    for name, type_ in _COLS:
        op.add_column("biometric_devices", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(_COLS):
        op.drop_column("biometric_devices", name)
