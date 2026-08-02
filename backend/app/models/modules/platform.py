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

    device_id = Column(String(128), nullable=False)   # hardware serial / id (NOT the model name)
    name = Column(String(150), nullable=False)
    location = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    clock_skew_seconds = Column(Integer, nullable=True)   # device_time − server_receipt; surfaced, not trusted
    notes = Column(Text, nullable=True)

    # Device Information (hardware specs surfaced on the Device Information tab).
    model_name = Column(String(100), nullable=True)          # e.g. "MB360 Plus"
    vendor = Column(String(100), nullable=True)              # e.g. "ZKTeco CO., LTD."
    device_type = Column(String(100), nullable=True)         # e.g. "Fingerprint & Face"
    volume = Column(Integer, nullable=True)                  # 0–100
    language = Column(String(40), nullable=True)             # e.g. "English"
    firmware_version = Column(String(40), nullable=True)     # e.g. "v1.0.8"
    fingerprint_version = Column(String(20), nullable=True)  # e.g. "v10"
    face_version = Column(String(20), nullable=True)         # e.g. "v7"
    mac_address = Column(String(40), nullable=True)          # e.g. "00:17:61:12:f9:74"
    storage_used_percent = Column(Integer, nullable=True)    # 0–100
    attendance_log_capacity = Column(Integer, nullable=True)
    current_attendance_log = Column(Integer, nullable=True)

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
    """Maps a device-side biometric/user id to a student OR a staff user."""
    __tablename__ = "biometric_enrollments"

    biometric_user_id = Column(String(128), nullable=False)   # the id stored on the device
    # A registration targets exactly one of these (enforced in the API).
    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)  # staff
    label = Column(String(150), nullable=True)
    # Device-reported enrolment state (Registered Users tab columns).
    fingerprint_count = Column(Integer, default=0, nullable=False)
    has_face = Column(Boolean, default=False, nullable=False)
    has_card = Column(Boolean, default=False, nullable=False)
    profile_pic_url = Column(String(500), nullable=True)
    status = Column(String(30), default="registered", nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "biometric_user_id", name="uq_biometric_enrollments_org_uid"),
        Index("ix_biometric_enrollments_student_org", "student_id", "org_id"),
    )


class BiometricCommand(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A command queued to a biometric device (Home tab command log). The device
    fetches PENDING commands via the ingest channel and reports back the result."""
    __tablename__ = "biometric_commands"

    device_pk = Column(String(36), ForeignKey("biometric_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    command = Column(String(100), nullable=False)     # e.g. "Backup User Data from device", "Sync Users to device"
    status = Column(String(20), default="pending", nullable=False)  # pending | success | failed
    result = Column(Text, nullable=True)              # device-reported detail
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


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


# ── Secondary Report parity S-0: Terms & Sub-term + dated config ─────────────

class AcademicTerm(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A managed academic term (Report Setup → Terms & Sub-term), e.g. Autumn /
    Spring / Summer. Exactly one is the active (current) term; ``active_sub_term_id``
    is which sub-term is current within it. Distinct from the free-text
    ``AcademicSession.term`` — this is the structured report-domain list."""
    __tablename__ = "academic_terms"

    name = Column(String(60), nullable=False)
    alias = Column(String(60), nullable=True)
    position = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    active_sub_term_id = Column(String(36), ForeignKey("academic_sub_terms.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_academic_terms_org_name"),
        Index("ix_academic_terms_org", "org_id"),
    )


class AcademicSubTerm(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A sub-term applied across every term (Report Setup → Terms & Sub-term):
    Half-Term (mid) / Full-Term. The report title + assessment scoping key off it.
    Seeded with Half-Term + Full-Term (Mock deliberately excluded)."""
    __tablename__ = "academic_sub_terms"

    name = Column(String(60), nullable=False)
    alias = Column(String(60), nullable=True)
    position = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_academic_sub_terms_org_name"),
        Index("ix_academic_sub_terms_org", "org_id"),
    )


class TermPeriod(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Dates + attendance denominators for one (session, term, sub-term) — backs
    BOTH Report Setup → 'Term Begins/Ends Date' and 'Attendance Setup' (two views
    of the same row). ``total_days`` is the attendance % denominator."""
    __tablename__ = "term_periods"

    session_id = Column(String(36), ForeignKey("academic_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    term_id = Column(String(36), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False, index=True)
    sub_term_id = Column(String(36), ForeignKey("academic_sub_terms.id", ondelete="CASCADE"), nullable=False, index=True)
    begin_date = Column(Date, nullable=True)          # attendance begin
    end_date = Column(Date, nullable=True)            # attendance end + term/sub-term ends
    next_term_begins = Column(Date, nullable=True)
    published_date = Column(Date, nullable=True)
    excluded_days = Column(Integer, nullable=True)    # non-school days in the window
    total_days = Column(Integer, nullable=True)       # attendance denominator (school days)

    __table_args__ = (
        UniqueConstraint("org_id", "session_id", "term_id", "sub_term_id", name="uq_term_period"),
        Index("ix_term_periods_org_session", "org_id", "session_id"),
    )


class ReportDeadline(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Result-submission deadline for a (session, term, sub-term) — Report Setup →
    Deadline."""
    __tablename__ = "report_deadlines"

    session_id = Column(String(36), ForeignKey("academic_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    term_id = Column(String(36), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False, index=True)
    sub_term_id = Column(String(36), ForeignKey("academic_sub_terms.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(20), default="open", nullable=False)   # open | closed
    submission_deadline = Column(Date, nullable=True)

    __table_args__ = (
        Index("ix_report_deadlines_org_session", "org_id", "session_id"),
    )


class ReportCommentType(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Report Setup → Comment: a named comment slot on the report card (e.g.
    'Classroom Behaviour' short, "Teacher's Comment" long). ``comment_type`` sets
    the length class; ``max_length`` caps long comments (e.g. 5000)."""
    __tablename__ = "report_comment_types"

    name = Column(String(120), nullable=False)
    comment_type = Column(String(20), default="short", nullable=False)   # short | long
    max_length = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_report_comment_types_org_name"),
        Index("ix_report_comment_types_org", "org_id"),
    )


class ResultDefaultComment(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Report Setup → Result Default Comment: an auto-fill comment for a score band,
    keyed by teacher type + grading scale (+ optional year group). When a student's
    score falls in [min_score, max_score] it pre-fills that teacher's comment."""
    __tablename__ = "result_default_comments"

    teacher_type = Column(String(20), default="class", nullable=False)   # subject | class | head
    grading_scale_id = Column(String(36), ForeignKey("grading_scales.id", ondelete="SET NULL"), nullable=True, index=True)
    year_group = Column(String(60), nullable=True)   # e.g. "YEAR 7"; null = all
    min_score = Column(Numeric(6, 2), nullable=True)
    max_score = Column(Numeric(6, 2), nullable=True)
    comment = Column(Text, nullable=False)

    __table_args__ = (
        Index("ix_result_default_comments_org", "org_id", "teacher_type"),
    )


class ReportBranding(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Report Setup → School Motto, Seal & Sponsor: the branding + heading block
    printed on the report card (one row per org). Passmarks feed the card's
    pass/fail; the images are the seal, head signature, logo background and
    sponsor strip."""
    __tablename__ = "report_branding"

    school_motto = Column(String(200), nullable=True)
    school_name_alias = Column(String(150), nullable=True)      # e.g. "FAIRVIEW SECONDARY SCHOOL"
    school_address = Column(Text, nullable=True)
    school_website = Column(String(200), nullable=True)
    school_email = Column(String(200), nullable=True)
    school_phone = Column(String(60), nullable=True)
    class_teacher_title = Column(String(80), nullable=True, default="Class Teacher")
    school_head_title = Column(String(80), nullable=True, default="Principal")
    school_head_name = Column(String(150), nullable=True)
    full_term_passmark = Column(Numeric(6, 2), nullable=True)
    mid_term_passmark = Column(Numeric(6, 2), nullable=True)
    min_average_honours = Column(Numeric(6, 2), nullable=True)
    promotion_comment = Column(String(120), nullable=True, default="Promoted")
    demotion_comment = Column(String(120), nullable=True, default="Not Promoted")
    logo_url = Column(String(500), nullable=True)
    head_signature_url = Column(String(500), nullable=True)
    logo_background_url = Column(String(500), nullable=True)
    sponsor_url = Column(String(500), nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", name="uq_report_branding_org"),
    )


class ReportLevelSetting(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Report Setup → Result Type + Result Photo Setup: per year-group report
    options — Junior/Senior classification, whether class position prints, and
    whether the pupil photo shows on the card. One row per (org, year_group)."""
    __tablename__ = "report_level_settings"

    year_group = Column(String(60), nullable=False)      # e.g. "YEAR 7"
    result_type = Column(String(20), default="junior", nullable=False)   # junior | senior
    show_position = Column(Boolean, default=True, nullable=False)
    show_photo = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "year_group", name="uq_report_level_setting"),
        Index("ix_report_level_settings_org", "org_id"),
    )


class ReportSubjectExclusion(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Report Setup → Subjects For Score Exclusion: a subject that still shows on
    the report for a year-group but does NOT count toward totals / position."""
    __tablename__ = "report_subject_exclusions"

    year_group = Column(String(60), nullable=False)
    subject_id = Column(String(36), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("org_id", "year_group", "subject_id", name="uq_report_subject_exclusion"),
        Index("ix_report_subject_exclusions_org", "org_id", "year_group"),
    )


class AssessmentGroup(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Report Setup → Assessment Group: a named grouping for assessments (e.g. a
    'Continuous Assessment' bucket). Optional label on assessments."""
    __tablename__ = "assessment_groups"

    name = Column(String(120), nullable=False)
    position = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_assessment_groups_org_name"),
        Index("ix_assessment_groups_org", "org_id"),
    )


class Assessment(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Report Setup → Assessment: a leaf mark component (CBT / Theory / PRJ / PBT /
    EXAM) scored out of ``max_score``, scoped to a (term, sub-term) and a level
    (year_group NULL = all levels). Cumulatives (S-3) compose these into the
    report columns. ``decimal_places`` controls display rounding."""
    __tablename__ = "assessments"

    name = Column(String(80), nullable=False)
    code = Column(String(40), nullable=True)
    max_score = Column(Numeric(6, 2), nullable=False, default=100)
    term_id = Column(String(36), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False, index=True)
    sub_term_id = Column(String(36), ForeignKey("academic_sub_terms.id", ondelete="CASCADE"), nullable=False, index=True)
    year_group = Column(String(60), nullable=True)          # NULL = All Levels
    decimal_places = Column(Integer, default=0, nullable=False)
    group_id = Column(String(36), ForeignKey("assessment_groups.id", ondelete="SET NULL"), nullable=True)
    position = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("ix_assessments_org_term", "org_id", "term_id"),
    )


class Cumulative(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Report Setup → Result View → Assessment Cumulative Setup: a named report
    column composed from assessments and/or other cumulatives (a small DAG).
      • cumul_type: score (sum) | percentage (sum/max*100) | custom_percentage
        (sum rescaled to ``max_percent``).
    Scoped to (term, sub-term, level). The evaluator (S-4) resolves components
    per student."""
    __tablename__ = "cumulatives"

    name = Column(String(120), nullable=False)
    code = Column(String(40), nullable=True)
    term_id = Column(String(36), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False, index=True)
    sub_term_id = Column(String(36), ForeignKey("academic_sub_terms.id", ondelete="CASCADE"), nullable=False, index=True)
    year_group = Column(String(60), nullable=True)                 # NULL = All Levels
    cumul_type = Column(String(20), default="score", nullable=False)   # score | percentage | custom_percentage
    max_percent = Column(Numeric(6, 2), nullable=True)             # for custom_percentage
    decimal_places = Column(Integer, default=0, nullable=False)
    position = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("ix_cumulatives_org_term", "org_id", "term_id"),
    )


class CumulativeComponent(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A member of a Cumulative — a reference to either an assessment or another
    cumulative (``ref_type``). Ordered by ``position``."""
    __tablename__ = "cumulative_components"

    cumulative_id = Column(String(36), ForeignKey("cumulatives.id", ondelete="CASCADE"), nullable=False, index=True)
    ref_type = Column(String(20), nullable=False)   # assessment | cumulative
    ref_id = Column(String(36), nullable=False)
    position = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("ix_cumulative_components_cumulative", "cumulative_id"),
    )


class StudentAssessmentScore(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Report Entry: a pupil's raw score for one assessment component in one
    subject (e.g. CBT=18 in Mathematics). The (term, sub-term, max) come from the
    Assessment. Cumulatives (S-3) are computed from these — not stored. One row
    per (student, subject, assessment)."""
    __tablename__ = "student_assessment_scores"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(String(36), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    assessment_id = Column(String(36), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Numeric(6, 2), nullable=True)
    recorded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "student_id", "subject_id", "assessment_id", name="uq_student_assessment_score"),
        Index("ix_student_assessment_scores_subj", "subject_id", "assessment_id"),
    )


class SchoolHouse(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A school house (for the merit/conduct leaderboard + Pastoral House Setup)."""
    __tablename__ = "school_houses"

    name = Column(String(80), nullable=False)
    color = Column(String(20), nullable=True)
    motto = Column(String(200), nullable=True)
    # Pastoral House Setup: optional school-section scoping + active flag.
    section_id = Column(String(36), ForeignKey("school_sections.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

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
    # Report Setup → Grading System: whether this scale's legend prints in the
    # report table, and what it is used for (main grade / keys legend / cumulative
    # / mock). Several scales can coexist; the report picks by purpose.
    show_in_table = Column(Boolean, default=True, nullable=False)
    purpose = Column(String(20), default="grade", nullable=False)  # grade | keys | cumulative | mock

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
