"""Admissions (Educare parity): acceptance / offer form

Revision ID: 057_acceptance_forms
Revises: 056_post_entrance_forms
Create Date: 2026-07-12 13:00:00.000000

Additive + reversible. One table backing "Acceptance Form" — the offer/acceptance
artifact a parent confirms once a place is offered. 1:1 with admission_applications
(unique application_id). Light fee handling (flat fields, no ledger wiring).
"""
from alembic import op
import sqlalchemy as sa


revision = "057_acceptance_forms"
down_revision = "056_post_entrance_forms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "acceptance_forms",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        # Offer
        sa.Column("offered_class_id", sa.String(length=36), nullable=True),
        sa.Column("offered_level", sa.String(length=80), nullable=True),
        sa.Column("offer_date", sa.Date(), nullable=True),
        sa.Column("acceptance_deadline", sa.Date(), nullable=True),
        sa.Column("resumption_date", sa.Date(), nullable=True),
        # Fee (light)
        sa.Column("acceptance_fee_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("fee_status", sa.String(length=20), nullable=False, server_default="unpaid"),
        sa.Column("payment_reference", sa.String(length=120), nullable=True),
        sa.Column("terms_text", sa.Text(), nullable=True),
        # Acceptance
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("accepted_by", sa.String(length=200), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decline_reason", sa.Text(), nullable=True),
        # Meta
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["admission_applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["offered_class_id"], ["school_classes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_acceptance_application"),
    )
    op.create_index("ix_acceptance_forms_org", "acceptance_forms", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_acceptance_forms_org", table_name="acceptance_forms")
    op.drop_table("acceptance_forms")
