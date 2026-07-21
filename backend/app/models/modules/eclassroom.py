"""eClassroom (virtual classroom) module — Educare parity.

Its own top-level section with four children:
  • eClassroom Setup   → EClassroomSettings (per-org toggles)
  • Programs           → EClassroomProgram (CBT-linked learning programs)
  • Manage eClassrooms → EClassroomSchedule (scheduled sessions by year group)
  • Live Broadcast     → an EClassroomSchedule going live REUSES the existing
                          LiveSession/WebRTC infrastructure (no new streaming stack).

Scoped to our existing building blocks: SchoolSection (Educare's "Select School"),
AcademicSession (Session), YearGroup (Year Group).
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Index, UniqueConstraint

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


class EClassroomSettings(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """One row per org — eClassroom Setup (Automatic Publish Setup)."""
    __tablename__ = "eclassroom_settings"

    can_teacher_publish = Column(Boolean, nullable=False, default=True)
    automatic_approval = Column(Boolean, nullable=False, default=False)
    learning_program_enabled = Column(Boolean, nullable=False, default=False)

    __table_args__ = (UniqueConstraint("org_id", name="uq_eclassroom_settings_org"),)


class EClassroomProgram(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A learning program (Program Manager), scoped to a CBT type / section / session."""
    __tablename__ = "eclassroom_programs"

    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    cbt_type = Column(String(20), nullable=False, default="student")   # student | staff
    section_id = Column(String(36), ForeignKey("school_sections.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = Column(String(36), ForeignKey("academic_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("ix_eclassroom_programs_org_session", "org_id", "session_id"),)


class EClassroomSchedule(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A scheduled eClassroom session (Manage eClassrooms) and/or live broadcast.

    ``status`` moves new → live → ended. Going live links ``live_session_id`` to a
    real LiveSession (the existing WebRTC room), which the frontend then joins.
    """
    __tablename__ = "eclassroom_schedules"

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    section_id = Column(String(36), ForeignKey("school_sections.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = Column(String(36), ForeignKey("academic_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    year_group_id = Column(String(36), ForeignKey("year_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False, default="new")          # new | live | ended
    live_session_id = Column(String(36), ForeignKey("live_sessions.id", ondelete="SET NULL"), nullable=True, index=True)

    __table_args__ = (Index("ix_eclassroom_schedules_org_status", "org_id", "status"),)
