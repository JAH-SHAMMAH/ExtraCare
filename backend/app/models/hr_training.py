"""Training (HR) — training programs and their scheduled sessions.

Deliberately light per scope: a Training is a program/course; a TrainingSession is
a scheduled instance of it (date / facilitator / location). No enrolment or scoring
yet — that's a later extension. Confidential HR admin: gated ``hr:write``.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, Date, Time, ForeignKey, Index

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


class Training(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A training program / course."""
    __tablename__ = "trainings"

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(80), nullable=True)                   # free-text / from training_category list
    status = Column(String(20), default="planned", nullable=False) # planned | ongoing | completed

    __table_args__ = (Index("ix_trainings_org_status", "org_id", "status"),)


class TrainingSession(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A scheduled session of a Training."""
    __tablename__ = "training_sessions"

    training_id = Column(String(36), ForeignKey("trainings.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=True)                     # optional session label
    session_date = Column(Date, nullable=True, index=True)
    start_time = Column(Time, nullable=True)
    location = Column(String(200), nullable=True)
    facilitator = Column(String(150), nullable=True)

    __table_args__ = (Index("ix_training_sessions_org_date", "org_id", "session_date"),)
