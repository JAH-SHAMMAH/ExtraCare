"""Administration & Platform models (Batch 7) — all `settings:*` (admin) config.

  • Biometric (ZKTeco): BiometricDevice, BiometricEnrollment, UnmappedPunch —
    devices + a biometric-id→student map; punches feed the EXISTING attendance
    event layer (dedup on the device record id); unrecognised punches quarantine.
  • School Setup: AcademicSession, SchoolHouse, GradingBand.
  • Custom Fields: CustomFieldDefinition + CustomFieldValue (EAV).
  • Voting: Poll + PollOption + PollVote (one vote per voter; results derived).
  • Mailbox: MailboxMessage + MailboxRecipient (announcements, not chat).
  • Mobile: MobileDevice (push tokens) + MobileAppConfig (toggles).
"""
from __future__ import annotations

from sqlalchemy import (
    Column, String, Text, Date, DateTime, Integer, Numeric, Boolean, JSON, ForeignKey,
    Index, UniqueConstraint,
)

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


# ── Biometric ───────────────────────────────────────────────────────────────────

class BiometricDevice(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A registered biometric terminal (e.g. ZKTeco)."""
    __tablename__ = "biometric_devices"

    device_id = Column(String(128), nullable=False)   # hardware serial / id
    name = Column(String(150), nullable=False)
    location = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    clock_skew_seconds = Column(Integer, nullable=True)   # device_time − server_receipt; surfaced, not trusted
    notes = Column(Text, nullable=True)

    # Per-device ingest credential. Only the SHA-256 hash is stored (never the
    # plaintext); the token is shown once at issue/rotate time. `token_prefix`
    # is the first few chars, surfaced so an admin can identify the active token.
    # Revoking nulls all three → the device can no longer POST /biometric/ingest.
    token_hash = Column(String(64), nullable=True, unique=True)
    token_prefix = Column(String(16), nullable=True)
    token_issued_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "device_id", name="uq_biometric_devices_org_device"),
        Index("ix_biometric_devices_org", "org_id"),
    )


class BiometricEnrollment(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Maps a device-side biometric/user id to a student."""
    __tablename__ = "biometric_enrollments"

    biometric_user_id = Column(String(128), nullable=False)   # the id stored on the device
    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String(150), nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "biometric_user_id", name="uq_biometric_enrollments_org_uid"),
        Index("ix_biometric_enrollments_student_org", "student_id", "org_id"),
    )


class UnmappedPunch(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Quarantine for a punch we couldn't map (unknown device / biometric id).
    NEVER silently dropped, NEVER auto-creates a student — resolvable to a real
    attendance event or explicitly discarded."""
    __tablename__ = "unmapped_punches"

    device_id = Column(String(128), nullable=True)
    biometric_user_id = Column(String(128), nullable=True)
    event_time = Column(DateTime(timezone=True), nullable=True)
    direction = Column(String(20), nullable=True)     # check_in | check_out
    external_ref = Column(String(128), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    reason = Column(String(40), nullable=False)       # unknown_device | unknown_biometric_id
    status = Column(String(20), default="pending", nullable=False)  # pending | resolved | discarded
    resolved_event_id = Column(String(36), ForeignKey("attendance_events.id", ondelete="SET NULL"), nullable=True)
    resolved_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_unmapped_punches_org_status", "org_id", "status"),
    )


# ── School Setup ────────────────────────────────────────────────────────────────

class AcademicSession(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """An academic session/term."""
    __tablename__ = "academic_sessions"

    name = Column(String(80), nullable=False)         # e.g. "2025/2026"
    term = Column(String(40), nullable=True)          # e.g. "Term 1"
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    is_current = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_academic_sessions_org", "org_id"),
    )


class AcademicWeek(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A single academic week within a term — the calendar backbone admins define.

    Standalone registry (nothing FKs into it yet): weekly remarks/reflections still
    store a raw ``week_start`` date. A locked week is frozen against edits/deletes
    so the calendar can't shift under features that reference it later.
    """
    __tablename__ = "academic_weeks"

    academic_year = Column(String(20), nullable=False)   # e.g. "2025/2026"
    term = Column(String(40), nullable=False)            # canonical "Term 1/2/3"
    week_number = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    label = Column(String(120), nullable=True)           # e.g. "Mid-term break"
    is_holiday = Column(Boolean, default=False, nullable=False)
    is_locked = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "academic_year", "term", "week_number",
                         name="uq_academic_weeks_slot"),
        Index("ix_academic_weeks_org_term", "org_id", "academic_year", "term"),
    )


class SchoolHouse(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A school house (for the merit/conduct leaderboard etc.)."""
    __tablename__ = "school_houses"

    name = Column(String(80), nullable=False)
    color = Column(String(20), nullable=True)
    motto = Column(String(200), nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_school_houses_org_name"),
    )


class SchoolSection(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A managed school section (e.g. Nursery / Junior / Secondary). The level a
    class belongs to and that a ReportTemplate is keyed on — replaces the free-text
    ``SchoolClass.level`` for report/grading purposes. ``curriculum`` selects the
    assessment paradigm feel (EYFS Nursery vs Nigerian/hybrid Junior-Secondary)."""
    __tablename__ = "school_sections"

    name = Column(String(60), nullable=False)
    curriculum = Column(String(20), default="nigerian", nullable=False)  # eyfs | nigerian | hybrid
    position = Column(Integer, default=0, nullable=False)
    # Class `level` values that map to this section (e.g. ["YEAR 1", …, "YEAR 6"]).
    # Auto-map links a class when its normalized level matches the section name OR
    # one of these aliases; anything else is left unassigned, never guessed.
    level_aliases = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_school_sections_org_name"),
        Index("ix_school_sections_org", "org_id"),
    )


class GradingScale(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A named grading scale. ``numeric`` scales map a percentage to a grade via
    GradingBand min/max ranges; ``descriptor`` scales are ordered labels (EYFS
    emerging/expected/exceeding, Cambridge attainment) with no score ranges.
    ``is_provisional`` marks a seeded placeholder until the school locks real
    numbers — never a code constant."""
    __tablename__ = "grading_scales"

    name = Column(String(80), nullable=False)
    scale_type = Column(String(20), default="numeric", nullable=False)  # numeric | descriptor
    is_provisional = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_grading_scales_org_name"),
        Index("ix_grading_scales_org", "org_id"),
    )


class GradingBand(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A grade band. Numeric scale: ``grade`` for [min_score, max_score]. Descriptor
    scale: ``grade`` is the label (min/max null), ordered by ``position``."""
    __tablename__ = "grading_bands"

    scale_id = Column(String(36), ForeignKey("grading_scales.id", ondelete="CASCADE"), nullable=True, index=True)
    grade = Column(String(20), nullable=False)        # A1 / B2 / … or a descriptor label
    min_score = Column(Numeric(6, 2), nullable=True)  # nullable: descriptor bands have no range
    max_score = Column(Numeric(6, 2), nullable=True)
    remark = Column(String(120), nullable=True)
    position = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("ix_grading_bands_org", "org_id"),
    )


class ReportTemplate(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Per-section report format (School Reports R2). Chooses the assessment
    paradigm (``descriptive`` for EYFS Nursery, ``hybrid`` for Junior/Secondary),
    the CA/exam weighting, the numeric grading scale, and which sections/domains
    print. All numeric values are editable data, never code constants; unset
    weights fall back to the engine default."""
    __tablename__ = "report_templates"

    section_id = Column(String(36), ForeignKey("school_sections.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    assessment_mode = Column(String(20), default="hybrid", nullable=False)  # descriptive | numeric | hybrid
    ca_weight = Column(Numeric(5, 2), nullable=True)     # provisional/editable (e.g. 40); None → engine default
    exam_weight = Column(Numeric(5, 2), nullable=True)   # provisional/editable (e.g. 60)
    grading_scale_id = Column(String(36), ForeignKey("grading_scales.id", ondelete="SET NULL"), nullable=True)
    show_cognitive_table = Column(Boolean, default=True, nullable=False)
    show_position = Column(Boolean, default=True, nullable=False)
    show_attendance = Column(Boolean, default=True, nullable=False)
    show_affective = Column(Boolean, default=False, nullable=False)
    show_psychomotor = Column(Boolean, default=False, nullable=False)
    is_provisional = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "section_id", name="uq_report_templates_org_section"),
        Index("ix_report_templates_org", "org_id"),
    )


class ReportSubjectAssessment(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Per-(section, subject) flag for the hybrid report (School Reports R2b): does
    this subject carry a Cambridge assessment overlay in this section's report? The
    Nigerian numeric marks are always shown; when ``carries_cambridge`` is set, a
    Cambridge attainment (a descriptor, fed by the R3 strand domains) is layered on
    top. One row per (section, subject)."""
    __tablename__ = "report_subject_assessments"

    section_id = Column(String(36), ForeignKey("school_sections.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(String(36), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    carries_cambridge = Column(Boolean, default=False, nullable=False)
    cambridge_scale_id = Column(String(36), ForeignKey("grading_scales.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "section_id", "subject_id", name="uq_report_subject_assessment"),
        Index("ix_report_subject_assess_section", "section_id"),
    )


class AssessmentDomain(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A non-cognitive / criterion-referenced assessment domain (School Reports R3).
    One model carries them all, distinguished by ``domain_type``:
      • eyfs_area / eyfs_goal — EYFS Areas of Learning + their Early Learning Goals
        (area→goal nesting via parent_domain_id); Nursery's whole report.
      • cambridge_strand — a Cambridge attainment strand under a subject
        (parent_subject_id); the overlay on hybrid Junior/Secondary reports.
      • psychomotor / affective — the Nigerian report's skill + behaviour domains.
    Rated against ``rating_scale_id`` (a descriptor GradingScale)."""
    __tablename__ = "assessment_domains"

    section_id = Column(String(36), ForeignKey("school_sections.id", ondelete="CASCADE"), nullable=False, index=True)
    domain_type = Column(String(20), nullable=False)  # eyfs_area | eyfs_goal | cambridge_strand | psychomotor | affective
    name = Column(String(150), nullable=False)
    parent_domain_id = Column(String(36), ForeignKey("assessment_domains.id", ondelete="CASCADE"), nullable=True, index=True)
    parent_subject_id = Column(String(36), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True, index=True)
    rating_scale_id = Column(String(36), ForeignKey("grading_scales.id", ondelete="SET NULL"), nullable=True)
    position = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("ix_assessment_domains_org_section", "org_id", "section_id"),
    )


class StudentDomainRating(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A student's assessment against one domain for a term (School Reports R3)."""
    __tablename__ = "student_domain_ratings"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    term = Column(String(50), nullable=False)
    domain_id = Column(String(36), ForeignKey("assessment_domains.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = Column(String(60), nullable=True)   # descriptor label (e.g. "Secure")
    comment = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("student_id", "term", "domain_id", name="uq_student_domain_rating"),
        Index("ix_student_domain_ratings_term", "org_id", "term"),
    )


# ── Custom Fields (EAV) ─────────────────────────────────────────────────────────

class CustomFieldDefinition(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A user-defined field for an entity type (student/staff…)."""
    __tablename__ = "custom_field_definitions"

    entity_type = Column(String(40), nullable=False)  # student | staff | …
    field_key = Column(String(60), nullable=False)
    label = Column(String(120), nullable=False)
    field_type = Column(String(20), default="text", nullable=False)  # text | number | date | boolean | select
    options = Column(JSON, nullable=True)             # for select
    required = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "entity_type", "field_key", name="uq_custom_field_def_key"),
        Index("ix_custom_field_def_org_entity", "org_id", "entity_type"),
    )


class CustomFieldValue(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A value for a custom field on a specific entity row."""
    __tablename__ = "custom_field_values"

    field_id = Column(String(36), ForeignKey("custom_field_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(40), nullable=False)
    entity_id = Column(String(36), nullable=False)
    value = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "field_id", "entity_id", name="uq_custom_field_value"),
        Index("ix_custom_field_values_entity", "entity_type", "entity_id", "org_id"),
    )


# ── Voting ──────────────────────────────────────────────────────────────────────

class Poll(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A poll/election. Results are DERIVED from votes (no mutable tally)."""
    __tablename__ = "polls"

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="open", nullable=False)  # open | closed
    closes_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_polls_org_status", "org_id", "status"),
    )


class PollOption(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "poll_options"

    poll_id = Column(String(36), ForeignKey("polls.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String(200), nullable=False)

    __table_args__ = (
        Index("ix_poll_options_poll_org", "poll_id", "org_id"),
    )


class PollVote(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """One vote. Integrity: exactly one vote per (poll, voter) — DB-enforced."""
    __tablename__ = "poll_votes"

    poll_id = Column(String(36), ForeignKey("polls.id", ondelete="CASCADE"), nullable=False, index=True)
    option_id = Column(String(36), ForeignKey("poll_options.id", ondelete="CASCADE"), nullable=False)
    voter_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint("poll_id", "voter_id", name="uq_poll_votes_one_per_voter"),
        Index("ix_poll_votes_poll_org", "poll_id", "org_id"),
    )


# ── Mailbox (announcements, not chat) ────────────────────────────────────────────

class MailboxMessage(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """An internal announcement/memo from an admin to recipients."""
    __tablename__ = "mailbox_messages"

    subject = Column(String(200), nullable=False)
    body = Column(Text, nullable=True)
    sender_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    audience = Column(String(40), default="custom", nullable=True)  # all_staff | custom

    __table_args__ = (
        Index("ix_mailbox_messages_org", "org_id"),
    )


class MailboxRecipient(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "mailbox_recipients"

    message_id = Column(String(36), ForeignKey("mailbox_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("message_id", "recipient_id", name="uq_mailbox_recipient"),
        Index("ix_mailbox_recipients_recipient_org", "recipient_id", "org_id"),
    )


# ── Mobile Manager ───────────────────────────────────────────────────────────────

class MobileDevice(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A registered mobile device / push token."""
    __tablename__ = "mobile_devices"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    push_token = Column(String(255), nullable=False)
    platform = Column(String(20), nullable=True)   # ios | android
    label = Column(String(120), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "push_token", name="uq_mobile_devices_org_token"),
        Index("ix_mobile_devices_org", "org_id"),
    )


class MobileAppConfig(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A key/value app-config toggle (force-update version, feature flags)."""
    __tablename__ = "mobile_app_config"

    key = Column(String(80), nullable=False)
    value = Column(String(255), nullable=True)
    description = Column(String(200), nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "key", name="uq_mobile_app_config_key"),
    )
