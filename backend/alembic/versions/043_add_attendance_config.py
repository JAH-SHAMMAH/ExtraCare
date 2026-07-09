"""Attendance Setup: attendance_settings + absence_reasons + attendance_records.reason_id

Revision ID: 043_attendance_config
Revises: 042_rename_classes_british
Create Date: 2026-07-09 10:00:00.000000

Additive + reversible. Per-org late cutoff (attendance_settings) + configurable
absence reason codes (absence_reasons), plus a nullable reason_id FK on the
existing attendance_records (existing rows / present marks carry no reason).
"""
from alembic import op
import sqlalchemy as sa


revision = "043_attendance_config"
down_revision = "042_rename_classes_british"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attendance_settings",
        sa.Column("late_after_time", sa.Time(), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_attendance_settings_org_id_organizations")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attendance_settings")),
        sa.UniqueConstraint("org_id", name=op.f("uq_attendance_settings_org_id")),
    )
    with op.batch_alter_table("attendance_settings", schema=None) as b:
        b.create_index(b.f("ix_attendance_settings_id"), ["id"], unique=False)
        b.create_index(b.f("ix_attendance_settings_org_id"), ["org_id"], unique=True)

    op.create_table(
        "absence_reasons",
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("is_authorized", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_absence_reasons_org_id_organizations")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_absence_reasons")),
        sa.UniqueConstraint("org_id", "code", name="uq_absence_reasons_org_code"),
    )
    with op.batch_alter_table("absence_reasons", schema=None) as b:
        b.create_index(b.f("ix_absence_reasons_id"), ["id"], unique=False)
        b.create_index(b.f("ix_absence_reasons_org_id"), ["org_id"], unique=False)

    with op.batch_alter_table("attendance_records", schema=None) as b:
        b.add_column(sa.Column("reason_id", sa.String(length=36), nullable=True))
        b.create_foreign_key(
            op.f("fk_attendance_records_reason_id_absence_reasons"),
            "absence_reasons", ["reason_id"], ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("attendance_records", schema=None) as b:
        b.drop_constraint(op.f("fk_attendance_records_reason_id_absence_reasons"), type_="foreignkey")
        b.drop_column("reason_id")
    op.drop_table("absence_reasons")
    op.drop_table("attendance_settings")
