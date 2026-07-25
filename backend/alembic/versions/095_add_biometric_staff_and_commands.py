"""Biometric: staff enrollment + Registered-Users columns + command queue

Revision ID: 095_biometric_staff_commands
Revises: 094_biometric_device_specs
Create Date: 2026-07-24 09:00:00.000000

Additive + reversible. Lets an enrolment target a staff user (student_id becomes
nullable + a user_id is added), adds the device-reported enrolment columns
(fingerprint/face/card/profile/status), and creates the biometric_commands queue.
"""
from alembic import op
import sqlalchemy as sa


revision = "095_biometric_staff_commands"
down_revision = "094_biometric_device_specs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enrolment can now map to a staff user; student_id becomes optional.
    op.alter_column("biometric_enrollments", "student_id", existing_type=sa.String(length=36), nullable=True)
    op.add_column("biometric_enrollments", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.create_foreign_key("fk_biometric_enrollments_user", "biometric_enrollments", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_biometric_enrollments_user_id", "biometric_enrollments", ["user_id"])
    op.add_column("biometric_enrollments", sa.Column("fingerprint_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("biometric_enrollments", sa.Column("has_face", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("biometric_enrollments", sa.Column("has_card", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("biometric_enrollments", sa.Column("profile_pic_url", sa.String(length=500), nullable=True))
    op.add_column("biometric_enrollments", sa.Column("status", sa.String(length=30), nullable=False, server_default="registered"))

    op.create_table(
        "biometric_commands",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("device_pk", sa.String(length=36), nullable=False),
        sa.Column("command", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["device_pk"], ["biometric_devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_biometric_commands_device_pk", "biometric_commands", ["device_pk"])
    op.create_index("ix_biometric_commands_org_id", "biometric_commands", ["org_id"])


def downgrade() -> None:
    op.drop_table("biometric_commands")
    op.drop_index("ix_biometric_enrollments_user_id", table_name="biometric_enrollments")
    op.drop_constraint("fk_biometric_enrollments_user", "biometric_enrollments", type_="foreignkey")
    for col in ("status", "profile_pic_url", "has_card", "has_face", "fingerprint_count", "user_id"):
        op.drop_column("biometric_enrollments", col)
    op.alter_column("biometric_enrollments", "student_id", existing_type=sa.String(length=36), nullable=False)
