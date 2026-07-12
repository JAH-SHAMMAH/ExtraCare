"""Admissions (Educare parity): post-entrance registration form

Revision ID: 056_post_entrance_forms
Revises: 055_enquiry_appointment
Create Date: 2026-07-12 12:00:00.000000

Additive + reversible. One table backing "Post Entrance Form" — the full
candidate registration completed after passing the entrance exam. 1:1 with
admission_applications (unique application_id). Flat parent/guardian columns.
"""
from alembic import op
import sqlalchemy as sa


revision = "056_post_entrance_forms"
down_revision = "055_enquiry_appointment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "post_entrance_forms",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        # Candidate
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("nationality", sa.String(length=80), nullable=True),
        sa.Column("state_origin", sa.String(length=80), nullable=True),
        sa.Column("lga", sa.String(length=80), nullable=True),
        sa.Column("religion", sa.String(length=80), nullable=True),
        sa.Column("home_address", sa.Text(), nullable=True),
        sa.Column("passport_photo_url", sa.String(length=500), nullable=True),
        sa.Column("previous_school", sa.String(length=200), nullable=True),
        sa.Column("applying_for_class_id", sa.String(length=36), nullable=True),
        sa.Column("applying_for_level", sa.String(length=80), nullable=True),
        # Health
        sa.Column("blood_group", sa.String(length=10), nullable=True),
        sa.Column("genotype", sa.String(length=10), nullable=True),
        sa.Column("allergies", sa.Text(), nullable=True),
        sa.Column("special_needs", sa.Text(), nullable=True),
        # Father
        sa.Column("father_name", sa.String(length=200), nullable=True),
        sa.Column("father_occupation", sa.String(length=120), nullable=True),
        sa.Column("father_phone", sa.String(length=50), nullable=True),
        sa.Column("father_email", sa.String(length=320), nullable=True),
        # Mother
        sa.Column("mother_name", sa.String(length=200), nullable=True),
        sa.Column("mother_occupation", sa.String(length=120), nullable=True),
        sa.Column("mother_phone", sa.String(length=50), nullable=True),
        sa.Column("mother_email", sa.String(length=320), nullable=True),
        # Guardian
        sa.Column("guardian_name", sa.String(length=200), nullable=True),
        sa.Column("guardian_relationship", sa.String(length=80), nullable=True),
        sa.Column("guardian_phone", sa.String(length=50), nullable=True),
        sa.Column("guardian_address", sa.Text(), nullable=True),
        # Emergency
        sa.Column("emergency_name", sa.String(length=200), nullable=True),
        sa.Column("emergency_relationship", sa.String(length=80), nullable=True),
        sa.Column("emergency_phone", sa.String(length=50), nullable=True),
        # Meta
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["admission_applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["applying_for_class_id"], ["school_classes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_post_entrance_application"),
    )
    op.create_index("ix_post_entrance_forms_org", "post_entrance_forms", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_post_entrance_forms_org", table_name="post_entrance_forms")
    op.drop_table("post_entrance_forms")
