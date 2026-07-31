"""Secondary Report parity S-0: Terms & Sub-term + Term Periods + Deadlines

Revision ID: 108_report_terms_periods
Revises: 107_pastoral_rollcall_report
Create Date: 2026-07-29 15:30:00.000000

Foundational report-domain config: structured academic terms + sub-terms
(Half/Full), per-(session,term,sub-term) dates & attendance denominators, and
result-submission deadlines. Additive.
"""
from alembic import op
import sqlalchemy as sa


revision = "108_report_terms_periods"
down_revision = "107_pastoral_rollcall_report"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Sub-terms first (academic_terms FKs into it).
    op.create_table(
        "academic_sub_terms",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("alias", sa.String(length=60), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "name", name="uq_academic_sub_terms_org_name"),
    )
    op.create_index("ix_academic_sub_terms_org", "academic_sub_terms", ["org_id"])

    op.create_table(
        "academic_terms",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("alias", sa.String(length=60), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active_sub_term_id", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["active_sub_term_id"], ["academic_sub_terms.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "name", name="uq_academic_terms_org_name"),
    )
    op.create_index("ix_academic_terms_org", "academic_terms", ["org_id"])

    op.create_table(
        "term_periods",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("term_id", sa.String(length=36), nullable=False),
        sa.Column("sub_term_id", sa.String(length=36), nullable=False),
        sa.Column("begin_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("next_term_begins", sa.Date(), nullable=True),
        sa.Column("published_date", sa.Date(), nullable=True),
        sa.Column("excluded_days", sa.Integer(), nullable=True),
        sa.Column("total_days", sa.Integer(), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["academic_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["term_id"], ["academic_terms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sub_term_id"], ["academic_sub_terms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "session_id", "term_id", "sub_term_id", name="uq_term_period"),
    )
    op.create_index("ix_term_periods_session_id", "term_periods", ["session_id"])
    op.create_index("ix_term_periods_term_id", "term_periods", ["term_id"])
    op.create_index("ix_term_periods_sub_term_id", "term_periods", ["sub_term_id"])
    op.create_index("ix_term_periods_org_session", "term_periods", ["org_id", "session_id"])

    op.create_table(
        "report_deadlines",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("term_id", sa.String(length=36), nullable=False),
        sa.Column("sub_term_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("submission_deadline", sa.Date(), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["academic_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["term_id"], ["academic_terms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sub_term_id"], ["academic_sub_terms.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_deadlines_session_id", "report_deadlines", ["session_id"])
    op.create_index("ix_report_deadlines_org_session", "report_deadlines", ["org_id", "session_id"])


def downgrade() -> None:
    op.drop_table("report_deadlines")
    op.drop_table("term_periods")
    op.drop_table("academic_terms")
    op.drop_table("academic_sub_terms")
