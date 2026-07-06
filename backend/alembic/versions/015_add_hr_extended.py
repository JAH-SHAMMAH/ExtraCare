"""Add recruitment + disciplinary HR tables (Phase 4 Batch 1)

Revision ID: 015_add_hr_extended
Revises: 014_add_remita
Create Date: 2026-06-23 18:00:00.000000

Additive + reversible.
"""

from alembic import op
import sqlalchemy as sa


revision = "015_add_hr_extended"
down_revision = "014_add_remita"
branch_labels = None
depends_on = None


def _base():
    return (
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def upgrade() -> None:
    op.create_table(
        "job_openings", *_base(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("department", sa.String(120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("employment_type", sa.String(40), nullable=True),
        sa.Column("positions", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("posted_on", sa.Date(), nullable=True),
        sa.Column("closes_on", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_job_openings"),
    )
    op.create_index("ix_job_openings_id", "job_openings", ["id"])
    op.create_index("ix_job_openings_org_id", "job_openings", ["org_id"])
    op.create_index("ix_job_openings_org_status", "job_openings", ["org_id", "status"])

    op.create_table(
        "job_applicants", *_base(),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("stage", sa.String(20), nullable=False, server_default="applied"),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("resume_url", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("applied_on", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_job_applicants"),
        sa.ForeignKeyConstraint(["job_id"], ["job_openings.id"], ondelete="CASCADE", name="fk_job_applicants_job_id_job_openings"),
    )
    op.create_index("ix_job_applicants_id", "job_applicants", ["id"])
    op.create_index("ix_job_applicants_org_id", "job_applicants", ["org_id"])
    op.create_index("ix_job_applicants_job_id", "job_applicants", ["job_id"])
    op.create_index("ix_job_applicants_job_stage", "job_applicants", ["job_id", "stage"])

    op.create_table(
        "disciplinary_cases", *_base(),
        sa.Column("staff_user_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="minor"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("action_taken", sa.Text(), nullable=True),
        sa.Column("reported_by", sa.String(36), nullable=True),
        sa.Column("incident_on", sa.Date(), nullable=True),
        sa.Column("resolved_on", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_disciplinary_cases"),
        sa.ForeignKeyConstraint(["staff_user_id"], ["users.id"], ondelete="CASCADE", name="fk_disciplinary_staff_user_id_users"),
        sa.ForeignKeyConstraint(["reported_by"], ["users.id"], ondelete="SET NULL", name="fk_disciplinary_reported_by_users"),
    )
    op.create_index("ix_disciplinary_cases_id", "disciplinary_cases", ["id"])
    op.create_index("ix_disciplinary_cases_org_id", "disciplinary_cases", ["org_id"])
    op.create_index("ix_disciplinary_cases_staff_user_id", "disciplinary_cases", ["staff_user_id"])
    op.create_index("ix_disciplinary_org_status", "disciplinary_cases", ["org_id", "status"])


def downgrade() -> None:
    op.drop_table("disciplinary_cases")
    op.drop_table("job_applicants")
    op.drop_table("job_openings")
