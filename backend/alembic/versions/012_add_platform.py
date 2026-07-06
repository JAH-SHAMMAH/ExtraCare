"""Add administration & platform tables (Batch 7 — final)

Revision ID: 012_add_platform
Revises: 011_add_operations
Create Date: 2026-06-21 08:00:00.000000

Additive + reversible. Biometric (devices/enrollments/quarantine), school setup,
custom fields, voting, mailbox, mobile manager.
"""

from alembic import op
import sqlalchemy as sa


revision = "012_add_platform"
down_revision = "011_add_operations"
branch_labels = None
depends_on = None


def _base():
    return (
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
    )


def _soft():
    return (
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def upgrade() -> None:
    # ── Biometric ──
    op.create_table(
        "biometric_devices", *_base(),
        sa.Column("device_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clock_skew_seconds", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_biometric_devices"),
        sa.UniqueConstraint("org_id", "device_id", name="uq_biometric_devices_org_device"),
    )
    op.create_index("ix_biometric_devices_id", "biometric_devices", ["id"])
    op.create_index("ix_biometric_devices_org_id", "biometric_devices", ["org_id"])
    op.create_index("ix_biometric_devices_org", "biometric_devices", ["org_id"])

    op.create_table(
        "biometric_enrollments", *_base(),
        sa.Column("biometric_user_id", sa.String(128), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("label", sa.String(150), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_biometric_enrollments"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE", name="fk_biometric_enrollments_student_id_students"),
        sa.UniqueConstraint("org_id", "biometric_user_id", name="uq_biometric_enrollments_org_uid"),
    )
    op.create_index("ix_biometric_enrollments_id", "biometric_enrollments", ["id"])
    op.create_index("ix_biometric_enrollments_org_id", "biometric_enrollments", ["org_id"])
    op.create_index("ix_biometric_enrollments_student_id", "biometric_enrollments", ["student_id"])
    op.create_index("ix_biometric_enrollments_student_org", "biometric_enrollments", ["student_id", "org_id"])

    op.create_table(
        "unmapped_punches", *_base(),
        sa.Column("device_id", sa.String(128), nullable=True),
        sa.Column("biometric_user_id", sa.String(128), nullable=True),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("direction", sa.String(20), nullable=True),
        sa.Column("external_ref", sa.String(128), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("resolved_event_id", sa.String(36), nullable=True),
        sa.Column("resolved_by", sa.String(36), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_unmapped_punches"),
        sa.ForeignKeyConstraint(["resolved_event_id"], ["attendance_events.id"], ondelete="SET NULL", name="fk_unmapped_punches_resolved_event_id_attendance_events"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL", name="fk_unmapped_punches_resolved_by_users"),
    )
    op.create_index("ix_unmapped_punches_id", "unmapped_punches", ["id"])
    op.create_index("ix_unmapped_punches_org_id", "unmapped_punches", ["org_id"])
    op.create_index("ix_unmapped_punches_org_status", "unmapped_punches", ["org_id", "status"])

    # ── School setup ──
    op.create_table(
        "academic_sessions", *_base(),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("term", sa.String(40), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("id", name="pk_academic_sessions"),
    )
    op.create_index("ix_academic_sessions_id", "academic_sessions", ["id"])
    op.create_index("ix_academic_sessions_org_id", "academic_sessions", ["org_id"])
    op.create_index("ix_academic_sessions_org", "academic_sessions", ["org_id"])

    op.create_table(
        "school_houses", *_base(),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("motto", sa.String(200), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_school_houses"),
        sa.UniqueConstraint("org_id", "name", name="uq_school_houses_org_name"),
    )
    op.create_index("ix_school_houses_id", "school_houses", ["id"])
    op.create_index("ix_school_houses_org_id", "school_houses", ["org_id"])

    op.create_table(
        "grading_bands", *_base(),
        sa.Column("grade", sa.String(10), nullable=False),
        sa.Column("min_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("max_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("remark", sa.String(120), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_grading_bands"),
    )
    op.create_index("ix_grading_bands_id", "grading_bands", ["id"])
    op.create_index("ix_grading_bands_org_id", "grading_bands", ["org_id"])
    op.create_index("ix_grading_bands_org", "grading_bands", ["org_id"])

    # ── Custom fields ──
    op.create_table(
        "custom_field_definitions", *_base(), *_soft(),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("field_key", sa.String(60), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("field_type", sa.String(20), nullable=False, server_default="text"),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("id", name="pk_custom_field_definitions"),
        sa.UniqueConstraint("org_id", "entity_type", "field_key", name="uq_custom_field_def_key"),
    )
    op.create_index("ix_custom_field_definitions_id", "custom_field_definitions", ["id"])
    op.create_index("ix_custom_field_definitions_org_id", "custom_field_definitions", ["org_id"])
    op.create_index("ix_custom_field_def_org_entity", "custom_field_definitions", ["org_id", "entity_type"])

    op.create_table(
        "custom_field_values", *_base(),
        sa.Column("field_id", sa.String(36), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_custom_field_values"),
        sa.ForeignKeyConstraint(["field_id"], ["custom_field_definitions.id"], ondelete="CASCADE", name="fk_custom_field_values_field_id_custom_field_definitions"),
        sa.UniqueConstraint("org_id", "field_id", "entity_id", name="uq_custom_field_value"),
    )
    op.create_index("ix_custom_field_values_id", "custom_field_values", ["id"])
    op.create_index("ix_custom_field_values_org_id", "custom_field_values", ["org_id"])
    op.create_index("ix_custom_field_values_field_id", "custom_field_values", ["field_id"])
    op.create_index("ix_custom_field_values_entity", "custom_field_values", ["entity_type", "entity_id", "org_id"])

    # ── Voting ──
    op.create_table(
        "polls", *_base(), *_soft(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_polls"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL", name="fk_polls_created_by_users"),
    )
    op.create_index("ix_polls_id", "polls", ["id"])
    op.create_index("ix_polls_org_id", "polls", ["org_id"])
    op.create_index("ix_polls_org_status", "polls", ["org_id", "status"])

    op.create_table(
        "poll_options", *_base(),
        sa.Column("poll_id", sa.String(36), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_poll_options"),
        sa.ForeignKeyConstraint(["poll_id"], ["polls.id"], ondelete="CASCADE", name="fk_poll_options_poll_id_polls"),
    )
    op.create_index("ix_poll_options_id", "poll_options", ["id"])
    op.create_index("ix_poll_options_org_id", "poll_options", ["org_id"])
    op.create_index("ix_poll_options_poll_id", "poll_options", ["poll_id"])
    op.create_index("ix_poll_options_poll_org", "poll_options", ["poll_id", "org_id"])

    op.create_table(
        "poll_votes", *_base(),
        sa.Column("poll_id", sa.String(36), nullable=False),
        sa.Column("option_id", sa.String(36), nullable=False),
        sa.Column("voter_id", sa.String(36), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_poll_votes"),
        sa.ForeignKeyConstraint(["poll_id"], ["polls.id"], ondelete="CASCADE", name="fk_poll_votes_poll_id_polls"),
        sa.ForeignKeyConstraint(["option_id"], ["poll_options.id"], ondelete="CASCADE", name="fk_poll_votes_option_id_poll_options"),
        sa.ForeignKeyConstraint(["voter_id"], ["users.id"], ondelete="CASCADE", name="fk_poll_votes_voter_id_users"),
        sa.UniqueConstraint("poll_id", "voter_id", name="uq_poll_votes_one_per_voter"),
    )
    op.create_index("ix_poll_votes_id", "poll_votes", ["id"])
    op.create_index("ix_poll_votes_org_id", "poll_votes", ["org_id"])
    op.create_index("ix_poll_votes_poll_id", "poll_votes", ["poll_id"])
    op.create_index("ix_poll_votes_poll_org", "poll_votes", ["poll_id", "org_id"])

    # ── Mailbox ──
    op.create_table(
        "mailbox_messages", *_base(), *_soft(),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("sender_id", sa.String(36), nullable=True),
        sa.Column("audience", sa.String(40), nullable=True, server_default="custom"),
        sa.PrimaryKeyConstraint("id", name="pk_mailbox_messages"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="SET NULL", name="fk_mailbox_messages_sender_id_users"),
    )
    op.create_index("ix_mailbox_messages_id", "mailbox_messages", ["id"])
    op.create_index("ix_mailbox_messages_org_id", "mailbox_messages", ["org_id"])
    op.create_index("ix_mailbox_messages_org", "mailbox_messages", ["org_id"])

    op.create_table(
        "mailbox_recipients", *_base(),
        sa.Column("message_id", sa.String(36), nullable=False),
        sa.Column("recipient_id", sa.String(36), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_mailbox_recipients"),
        sa.ForeignKeyConstraint(["message_id"], ["mailbox_messages.id"], ondelete="CASCADE", name="fk_mailbox_recipients_message_id_mailbox_messages"),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE", name="fk_mailbox_recipients_recipient_id_users"),
        sa.UniqueConstraint("message_id", "recipient_id", name="uq_mailbox_recipient"),
    )
    op.create_index("ix_mailbox_recipients_id", "mailbox_recipients", ["id"])
    op.create_index("ix_mailbox_recipients_org_id", "mailbox_recipients", ["org_id"])
    op.create_index("ix_mailbox_recipients_message_id", "mailbox_recipients", ["message_id"])
    op.create_index("ix_mailbox_recipients_recipient_id", "mailbox_recipients", ["recipient_id"])
    op.create_index("ix_mailbox_recipients_recipient_org", "mailbox_recipients", ["recipient_id", "org_id"])

    # ── Mobile ──
    op.create_table(
        "mobile_devices", *_base(),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("push_token", sa.String(255), nullable=False),
        sa.Column("platform", sa.String(20), nullable=True),
        sa.Column("label", sa.String(120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_mobile_devices"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_mobile_devices_user_id_users"),
        sa.UniqueConstraint("org_id", "push_token", name="uq_mobile_devices_org_token"),
    )
    op.create_index("ix_mobile_devices_id", "mobile_devices", ["id"])
    op.create_index("ix_mobile_devices_org_id", "mobile_devices", ["org_id"])
    op.create_index("ix_mobile_devices_user_id", "mobile_devices", ["user_id"])
    op.create_index("ix_mobile_devices_org", "mobile_devices", ["org_id"])

    op.create_table(
        "mobile_app_config", *_base(),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("value", sa.String(255), nullable=True),
        sa.Column("description", sa.String(200), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_mobile_app_config"),
        sa.UniqueConstraint("org_id", "key", name="uq_mobile_app_config_key"),
    )
    op.create_index("ix_mobile_app_config_id", "mobile_app_config", ["id"])
    op.create_index("ix_mobile_app_config_org_id", "mobile_app_config", ["org_id"])


def downgrade() -> None:
    for tbl in ["mobile_app_config", "mobile_devices", "mailbox_recipients", "mailbox_messages",
                "poll_votes", "poll_options", "polls", "custom_field_values", "custom_field_definitions",
                "grading_bands", "school_houses", "academic_sessions", "unmapped_punches",
                "biometric_enrollments", "biometric_devices"]:
        op.drop_table(tbl)
