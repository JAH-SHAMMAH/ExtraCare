"""Feedback module extras: settings + daily reports + student daily reports + CRM

Revision ID: 051_feedback_module_extras
Revises: 050_staff_assessment_criteria
Create Date: 2026-07-10 17:30:00.000000

Additive + reversible. Backs the reference's Feedback section children that
weren't present: Feedback Settings, Daily Report, Student Daily Report, CRM.
StudentFeedback (Feedback Form / My Feedback / Feedback Manager) is unchanged.
"""
from alembic import op
import sqlalchemy as sa


revision = "051_feedback_module_extras"
down_revision = "050_staff_assessment_criteria"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("allow_anonymous", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notify_on_submit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("acknowledgement_message", sa.Text(), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_feedback_settings_org"),
    )
    op.create_index("ix_feedback_settings_org_id", "feedback_settings", ["org_id"])

    op.create_table(
        "daily_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("author_id", sa.String(length=36), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("class_id", sa.String(length=36), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("highlights", sa.Text(), nullable=True),
        sa.Column("challenges", sa.Text(), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["class_id"], ["school_classes.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_daily_reports_author_id", "daily_reports", ["author_id"])
    op.create_index("ix_daily_reports_report_date", "daily_reports", ["report_date"])
    op.create_index("ix_daily_reports_org_date", "daily_reports", ["org_id", "report_date"])

    op.create_table(
        "student_daily_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("author_id", sa.String(length=36), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("mood", sa.String(length=20), nullable=True),
        sa.Column("academic", sa.Text(), nullable=True),
        sa.Column("behaviour", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_student_daily_reports_student_id", "student_daily_reports", ["student_id"])
    op.create_index("ix_student_daily_reports_report_date", "student_daily_reports", ["report_date"])
    op.create_index("ix_student_daily_reports_student_date", "student_daily_reports", ["student_id", "report_date"])

    op.create_table(
        "crm_contacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("contact_type", sa.String(length=40), nullable=False, server_default="prospective_parent"),
        sa.Column("stage", sa.String(length=20), nullable=False, server_default="new"),
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column("assigned_to", sa.String(length=36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crm_contacts_email", "crm_contacts", ["email"])
    op.create_index("ix_crm_contacts_org_stage", "crm_contacts", ["org_id", "stage"])


def downgrade() -> None:
    op.drop_index("ix_crm_contacts_org_stage", table_name="crm_contacts")
    op.drop_index("ix_crm_contacts_email", table_name="crm_contacts")
    op.drop_table("crm_contacts")
    op.drop_index("ix_student_daily_reports_student_date", table_name="student_daily_reports")
    op.drop_index("ix_student_daily_reports_report_date", table_name="student_daily_reports")
    op.drop_index("ix_student_daily_reports_student_id", table_name="student_daily_reports")
    op.drop_table("student_daily_reports")
    op.drop_index("ix_daily_reports_org_date", table_name="daily_reports")
    op.drop_index("ix_daily_reports_report_date", table_name="daily_reports")
    op.drop_index("ix_daily_reports_author_id", table_name="daily_reports")
    op.drop_table("daily_reports")
    op.drop_index("ix_feedback_settings_org_id", table_name="feedback_settings")
    op.drop_table("feedback_settings")
