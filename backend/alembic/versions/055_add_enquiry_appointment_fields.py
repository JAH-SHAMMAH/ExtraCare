"""Students (Educare parity): enquiry appointment fields

Revision ID: 055_enquiry_appointment
Revises: 054_student_pickups
Create Date: 2026-07-12 10:30:00.000000

Additive + reversible. Three columns on admission_applications backing the
"Enquiry Appointment" view — a single scheduled meeting per enquiry (no child
table). appointment_status defaults to "none" via server_default so existing
rows backfill cleanly under NOT NULL.
"""
from alembic import op
import sqlalchemy as sa


revision = "055_enquiry_appointment"
down_revision = "054_student_pickups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("admission_applications") as batch:
        batch.add_column(sa.Column("appointment_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("appointment_status", sa.String(length=20), nullable=False, server_default="none"))
        batch.add_column(sa.Column("appointment_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("admission_applications") as batch:
        batch.drop_column("appointment_notes")
        batch.drop_column("appointment_status")
        batch.drop_column("appointment_at")
