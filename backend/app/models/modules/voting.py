"""Voting System module — staff-awards voting + rating (Educare parity).

Its own top-level section with five children:
  • Rating Setup   → VotingPeriod (monthly voting windows)
  • Voting Setup   → VoteCategory (award categories)
  • Manage Votes   → VoteSession (+ its categories, candidates) → ballots → results
  • My Votes       → an eligible voter casts VoteBallot(s)
  • Manage Rating  → a scoped monitoring view over the above (no new model)

Scoped to SchoolSection (Educare's "Select School") + AcademicSession. Candidate
and voter eligibility are by Role slug (candidate_role / voter_role).
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, Index, UniqueConstraint

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


class VotingPeriod(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A voting/rating period (Rating Setup → "Voting Periods")."""
    __tablename__ = "voting_periods"

    name = Column(String(60), nullable=False)                # e.g. "January"
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False, default="active")   # active | ended
    section_id = Column(String(36), ForeignKey("school_sections.id", ondelete="SET NULL"), nullable=True, index=True)

    __table_args__ = (Index("ix_voting_periods_org_status", "org_id", "status"),)


class VoteCategory(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """An award category (Voting Setup → "Manage Category")."""
    __tablename__ = "vote_categories"

    description = Column(String(300), nullable=False)
    section_id = Column(String(36), ForeignKey("school_sections.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("ix_vote_categories_org", "org_id"),)


class VoteSession(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A vote session (Manage Votes → "New Vote Session")."""
    __tablename__ = "vote_sessions"

    title = Column(String(250), nullable=False)
    instructions = Column(Text, nullable=True)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    session_id = Column(String(36), ForeignKey("academic_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    section_id = Column(String(36), ForeignKey("school_sections.id", ondelete="SET NULL"), nullable=True, index=True)
    positions = Column(Integer, nullable=False, default=1)          # winners per category
    candidate_role = Column(String(60), nullable=True)             # role slug candidates hold
    voter_role = Column(String(60), nullable=True)                 # role slug voters hold
    status = Column(String(20), nullable=False, default="draft")   # draft | conducted
    result_published = Column(Boolean, nullable=False, default=False)

    __table_args__ = (Index("ix_vote_sessions_org_status", "org_id", "status"),)


class VoteSessionCategory(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Which categories a session covers (Vote Categories on the New Vote form)."""
    __tablename__ = "vote_session_categories"

    session_id = Column(String(36), ForeignKey("vote_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(String(36), ForeignKey("vote_categories.id", ondelete="CASCADE"), nullable=False, index=True)

    __table_args__ = (UniqueConstraint("session_id", "category_id", name="uq_vote_session_category"),)


class VoteCandidate(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A candidate standing in a (session, category)."""
    __tablename__ = "vote_candidates"

    session_id = Column(String(36), ForeignKey("vote_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(String(36), ForeignKey("vote_categories.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("session_id", "category_id", "user_id", name="uq_vote_candidate"),
        Index("ix_vote_candidates_session", "session_id", "category_id"),
    )


class VoteBallot(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """One cast vote — a voter picks a candidate in a (session, category). One
    ballot per voter per category (enforced)."""
    __tablename__ = "vote_ballots"

    session_id = Column(String(36), ForeignKey("vote_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(String(36), ForeignKey("vote_categories.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("vote_candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    voter_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("session_id", "category_id", "voter_user_id", name="uq_vote_ballot_once"),
        Index("ix_vote_ballots_tally", "session_id", "category_id", "candidate_id"),
    )
