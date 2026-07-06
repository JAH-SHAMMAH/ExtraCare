"""Academic Records & Recognition models (Batch 3).

  • SubjectSelection — a student's elective/subject choice for a term.
  • Transcript (+ TranscriptEntry) — a formal, consolidated academic record
    snapshot (distinct from the live Grade gradebook).
  • ReportApproval — the report-card approval workflow (draft → published).
  • Recognition — ONE typed model for both conduct points and academic awards
    (``type`` = conduct_point | academic_award), shared backend, tabbed UI.

All tenant-scoped. Values stored as strings, validated in the schema layer.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, Date, Integer, Float, ForeignKey, Index, UniqueConstraint

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


class SubjectSelection(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A student's selection of a subject (elective) for an academic period."""
    __tablename__ = "subject_selections"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(String(36), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    academic_year = Column(String(20), nullable=True)
    term = Column(String(40), nullable=True)
    status = Column(String(20), default="requested", nullable=False)  # requested | approved | rejected
    selected_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", "academic_year", name="uq_subject_selection"),
        Index("ix_subject_selections_org_status", "org_id", "status"),
    )


class Transcript(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A consolidated academic record snapshot for a student + term."""
    __tablename__ = "transcripts"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    academic_year = Column(String(20), nullable=True)
    term = Column(String(40), nullable=True)
    average = Column(Float, nullable=True)
    remark = Column(Text, nullable=True)
    status = Column(String(20), default="draft", nullable=False)  # draft | issued
    issued_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_transcripts_student_org", "student_id", "org_id"),
    )


class TranscriptEntry(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """One subject line on a transcript."""
    __tablename__ = "transcript_entries"

    transcript_id = Column(String(36), ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_name = Column(String(150), nullable=False)
    score = Column(Float, nullable=True)
    grade = Column(String(10), nullable=True)
    remark = Column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_transcript_entries_transcript", "transcript_id", "org_id"),
    )


class ReportApproval(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A report-card moving through the approval workflow for a class + term."""
    __tablename__ = "report_approvals"

    class_id = Column(String(36), ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=True, index=True)
    academic_year = Column(String(20), nullable=True)
    term = Column(String(40), nullable=True)
    # draft | submitted | reviewed | approved | published
    stage = Column(String(20), default="draft", nullable=False)
    notes = Column(Text, nullable=True)
    submitted_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_report_approvals_org_stage", "org_id", "stage"),
    )


class Recognition(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Typed student recognition — ONE model, two faces:

      type=conduct_point  → ``points`` (+/-), ``house``, ``category``, ``reason``
      type=academic_award → ``title``, ``award_type``, ``description``

    A house-based conduct leaderboard aggregates ``points`` where
    type=conduct_point; academic awards are listed per student/term.
    """
    __tablename__ = "recognitions"

    type = Column(String(20), nullable=False, index=True)  # conduct_point | academic_award
    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=True)        # award title OR short conduct label
    reason = Column(Text, nullable=True)
    points = Column(Integer, nullable=True)           # conduct points (+/-)
    house = Column(String(80), nullable=True)         # conduct house bucket
    category = Column(String(80), nullable=True)      # conduct category
    award_type = Column(String(40), nullable=True)    # honor_roll | prize | certificate
    term = Column(String(40), nullable=True)
    awarded_on = Column(Date, nullable=True)
    recorded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_recognitions_org_type", "org_id", "type"),
        Index("ix_recognitions_student_org", "student_id", "org_id"),
        Index("ix_recognitions_house_org", "house", "org_id"),
    )
