"""School Attendance Setup: departure cutoff + notify toggles

Revision ID: 068_attendance_setup
Revises: 067_library_setup_reviews
Create Date: 2026-07-16 09:00:00.000000

Additive + reversible. Three columns on attendance_settings backing the School
Attendance Setup screen (Educare parity): a max-departure cutoff (late-departure
threshold for the live monitor) and email/SMS notify toggles.
"""
from alembic import op
import sqlalchemy as sa


revision = "068_attendance_setup"
down_revision = "067_library_setup_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("attendance_settings") as batch:
        batch.add_column(sa.Column("max_departure_time", sa.Time(), nullable=True))
        batch.add_column(sa.Column("notify_email", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("notify_sms", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("attendance_settings") as batch:
        batch.drop_column("notify_sms")
        batch.drop_column("notify_email")
        batch.drop_column("max_departure_time")
