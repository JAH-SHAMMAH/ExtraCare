"""Academic Records & Recognition models (Batch 3).

  • SubjectSelection — a student's elective/subject choice for a term.
  • Transcript (+ TranscriptEntry) — a formal, consolidated academic record
    snapshot (distinct from the live Grade gradebook).
  • ReportApproval — the report-card approval workflow (draft → published).
  • SubjectReportSubmission — one subject teacher's sign-off, at the (class,
    subject, term) grain that ReportApproval deliberately does not cover.
  • Recognition — ONE typed model for both conduct points and academic awards
    (``type`` = conduct_point | academic_award), shared backend, tabbed UI.

All tenant-scoped. Values stored as strings, validated in the schema layer.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, Date, DateTime, Integer, Float, ForeignKey, Index, UniqueConstraint

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
    # `published` is the stage that actually releases the card to parents, so it
    # carries its own stamp rather than sharing `approved_by`. Kept on a move back
    # to an earlier stage: it records the last release, not the current state.
    published_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_report_approvals_org_stage", "org_id", "stage"),
        # One workflow row per class + term. Both gates resolve a class's stage by
        # (class, term); duplicates would make "the stage" ambiguous and let a
        # stale second row keep releasing a card that was pulled back on the first.
        # `class_id` is a per-org FK, so this is org-scoped without naming org_id —
        # and NULL class_id (an org-wide row) stays unconstrained, as Postgres
        # treats NULLs as distinct.
        UniqueConstraint("class_id", "term", name="uq_report_approval_class_term"),
    )


class SubjectReportSubmission(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """One subject teacher's sign-off that their marks for a (class, subject,
    term, sub-term) are finished.

    WHY A SEPARATE TABLE. `report_approvals` is unique on (class_id, term), so a
    row there is a statement about the WHOLE class — which is why only the class's
    PC teacher may create one. A subject teacher needed a way to say "my part is
    done" without speaking for every other subject, and that is a different grain.
    ReportApproval is deliberately untouched: the approval ladder that gates
    publishing a class's cards keeps exactly the meaning it had.

    EXISTENCE IS THE STATE. A row means submitted; withdrawing deletes it. There
    is no `stage` column because there is only one state to be in, and no
    soft-delete flag because every query would then have to remember to filter it
    — a filter this codebase has already been bitten by forgetting. The history
    lives in the audit log, which records both the submission and the withdrawal.

    TERM IS A REAL FK, unlike ReportApproval.term, which is free text. That
    string is what let a production term rename drift away from the approvals
    referencing it and blank every parent's report card. A new table has no
    reason to inherit that.

    `sub_term_id` is nullable so a school that does not split its terms can sign
    off per term alone. Postgres treats NULLs as distinct in a unique index, so
    the constraint below does not prevent two NULL-sub-term rows for the same
    subject — the endpoint checks for an existing row before inserting, which is
    what actually enforces one sign-off per grain.
    """
    __tablename__ = "subject_report_submissions"

    class_id = Column(String(36), ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(String(36), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    term_id = Column(String(36), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False, index=True)
    sub_term_id = Column(String(36), ForeignKey("academic_sub_terms.id", ondelete="CASCADE"), nullable=True, index=True)
    submitted_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    # How many marks existed at sign-off. Not used as a gate — it is the record of
    # what the teacher was actually attesting to, so a later dispute about a
    # missing mark can be settled against what was there at the time.
    score_count = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("class_id", "subject_id", "term_id", "sub_term_id",
                         name="uq_subject_report_submission"),
        Index("ix_subject_report_submissions_class_term", "class_id", "term_id"),
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
