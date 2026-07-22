"""Voting System module

Revision ID: 081_voting
Revises: 080_eclassroom
Create Date: 2026-07-21 13:00:00.000000

Additive + reversible. Staff-awards voting: periods, categories, sessions (+ their
categories/candidates) and cast ballots. Matches TenantMixin — org_id indexed, no FK.
"""
from alembic import op
import sqlalchemy as sa


revision = "081_voting"
down_revision = "080_eclassroom"
branch_labels = None
depends_on = None

_TS = lambda: sa.Column("created_at", sa.DateTime(timezone=True), nullable=True)  # noqa: E731


def _common(*extra, soft_delete=True):
    cols = [
        sa.Column("id", sa.String(length=36), nullable=False),
        *extra,
        sa.Column("org_id", sa.String(length=36), nullable=False),
    ]
    if soft_delete:
        cols += [
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        ]
    cols += [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    ]
    return cols


def upgrade() -> None:
    op.create_table(
        "voting_periods",
        *_common(
            sa.Column("name", sa.String(length=60), nullable=False),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("section_id", sa.String(length=36), nullable=True),
        ),
        sa.ForeignKeyConstraint(["section_id"], ["school_sections.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_voting_periods_org_id", "voting_periods", ["org_id"])
    op.create_index("ix_voting_periods_section_id", "voting_periods", ["section_id"])
    op.create_index("ix_voting_periods_org_status", "voting_periods", ["org_id", "status"])

    op.create_table(
        "vote_categories",
        *_common(
            sa.Column("description", sa.String(length=300), nullable=False),
            sa.Column("section_id", sa.String(length=36), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        ),
        sa.ForeignKeyConstraint(["section_id"], ["school_sections.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vote_categories_org_id", "vote_categories", ["org_id"])
    op.create_index("ix_vote_categories_section_id", "vote_categories", ["section_id"])
    op.create_index("ix_vote_categories_org", "vote_categories", ["org_id"])

    op.create_table(
        "vote_sessions",
        *_common(
            sa.Column("title", sa.String(length=250), nullable=False),
            sa.Column("instructions", sa.Text(), nullable=True),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("session_id", sa.String(length=36), nullable=True),
            sa.Column("section_id", sa.String(length=36), nullable=True),
            sa.Column("positions", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("candidate_role", sa.String(length=60), nullable=True),
            sa.Column("voter_role", sa.String(length=60), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("result_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        ),
        sa.ForeignKeyConstraint(["session_id"], ["academic_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["section_id"], ["school_sections.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vote_sessions_org_id", "vote_sessions", ["org_id"])
    op.create_index("ix_vote_sessions_session_id", "vote_sessions", ["session_id"])
    op.create_index("ix_vote_sessions_section_id", "vote_sessions", ["section_id"])
    op.create_index("ix_vote_sessions_org_status", "vote_sessions", ["org_id", "status"])

    op.create_table(
        "vote_session_categories",
        *_common(
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("category_id", sa.String(length=36), nullable=False),
            soft_delete=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["vote_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["vote_categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "category_id", name="uq_vote_session_category"),
    )
    op.create_index("ix_vote_session_categories_org_id", "vote_session_categories", ["org_id"])
    op.create_index("ix_vote_session_categories_session_id", "vote_session_categories", ["session_id"])
    op.create_index("ix_vote_session_categories_category_id", "vote_session_categories", ["category_id"])

    op.create_table(
        "vote_candidates",
        *_common(
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("category_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            soft_delete=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["vote_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["vote_categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "category_id", "user_id", name="uq_vote_candidate"),
    )
    op.create_index("ix_vote_candidates_org_id", "vote_candidates", ["org_id"])
    op.create_index("ix_vote_candidates_session_id", "vote_candidates", ["session_id"])
    op.create_index("ix_vote_candidates_category_id", "vote_candidates", ["category_id"])
    op.create_index("ix_vote_candidates_user_id", "vote_candidates", ["user_id"])
    op.create_index("ix_vote_candidates_session", "vote_candidates", ["session_id", "category_id"])

    op.create_table(
        "vote_ballots",
        *_common(
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("category_id", sa.String(length=36), nullable=False),
            sa.Column("candidate_id", sa.String(length=36), nullable=False),
            sa.Column("voter_user_id", sa.String(length=36), nullable=False),
            soft_delete=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["vote_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["vote_categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["vote_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["voter_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "category_id", "voter_user_id", name="uq_vote_ballot_once"),
    )
    op.create_index("ix_vote_ballots_org_id", "vote_ballots", ["org_id"])
    op.create_index("ix_vote_ballots_session_id", "vote_ballots", ["session_id"])
    op.create_index("ix_vote_ballots_category_id", "vote_ballots", ["category_id"])
    op.create_index("ix_vote_ballots_candidate_id", "vote_ballots", ["candidate_id"])
    op.create_index("ix_vote_ballots_voter_user_id", "vote_ballots", ["voter_user_id"])
    op.create_index("ix_vote_ballots_tally", "vote_ballots", ["session_id", "category_id", "candidate_id"])


def downgrade() -> None:
    for t in ("vote_ballots", "vote_candidates", "vote_session_categories", "vote_sessions", "vote_categories", "voting_periods"):
        op.drop_table(t)
