from sqlalchemy import Column, String, Integer, Float, Date, DateTime, Time, Text, Boolean, Enum, ForeignKey, JSON, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin, utc_now
import enum


class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class GradeStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ExamSittingStatus(str, enum.Enum):
    """Status of a manual Exam sitting. Named distinctly from the CBT `ExamStatus`
    (draft/published/active/closed) defined below — different lifecycle."""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Student(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "students"

    student_id = Column(String(50), nullable=False, index=True)  # org-assigned ID
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(320), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True)
    photo_url = Column(String(500), nullable=True)
    address = Column(Text, nullable=True)

    # Linked login — nullable because legacy rows created before the multi-role
    # flow may not have a user record yet. When present this is the canonical
    # source of truth for "is this user a student"; email-match fallback in
    # /me/school-context stays as a resilience path only.
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Academic
    class_id = Column(String(36), ForeignKey("school_classes.id"), nullable=True)
    admission_date = Column(Date, nullable=True)
    graduation_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)

    # Parent/Guardian — free-text fields kept for CSV imports + paper records.
    # The authoritative link for login/visibility is ParentGuardian below.
    guardian_name = Column(String(255), nullable=True)
    guardian_phone = Column(String(50), nullable=True)
    guardian_email = Column(String(320), nullable=True)
    guardian_relationship = Column(String(50), nullable=True)

    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    school_class = relationship("SchoolClass", back_populates="students")
    attendance_records = relationship("AttendanceRecord", back_populates="student")
    grades = relationship("Grade", back_populates="student")
    guardians = relationship("ParentGuardian", back_populates="student", cascade="all, delete-orphan")

    __table_args__ = (
        # /me/school-context: resolve linked student by email within an org.
        Index("ix_students_email_org", "email", "org_id"),
    )


class ParentGuardian(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Link table joining a parent-role User to the Student(s) they guard.

    One parent can have multiple children; one child can have multiple
    guardians (parent + guardian, split households, etc). `is_primary`
    drives who receives report-card emails and SMS by default.
    """

    __tablename__ = "parent_guardians"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(String(50), default="parent")  # parent | guardian | other
    is_primary = Column(Boolean, default=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    student = relationship("Student", back_populates="guardians")
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("user_id", "student_id", name="uq_parent_student"),
        # "Who are this child's guardians?" — hot path for report cards + SMS.
        Index("ix_parent_guardians_student_org", "student_id", "org_id"),
    )


class SchoolClass(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "school_classes"

    name = Column(String(100), nullable=False)  # e.g. "Grade 10A"
    level = Column(String(50), nullable=True)   # e.g. "Secondary", "Primary" (UI: grade_level) — legacy free-text
    # Managed section (School Reports R2). Nullable: unassigned classes fall back to
    # the legacy `level`-tagged report. Backfilled explicitly (normalized match),
    # never guessed — see the auto-map action.
    section_id = Column(String(36), ForeignKey("school_sections.id", ondelete="SET NULL"), nullable=True, index=True)
    section = Column(String(50), nullable=True)  # e.g. "A" (UI: section)
    academic_year = Column(String(20), nullable=True)  # e.g. "2024/2025"
    teacher_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    room = Column(String(50), nullable=True)
    max_capacity = Column(Integer, default=40)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    students = relationship("Student", back_populates="school_class")
    teacher = relationship("User", foreign_keys=[teacher_id])
    timetables = relationship("Timetable", back_populates="school_class")

    __table_args__ = (
        # Hot path: /me/school-context lookup of "classes I teach in this org".
        Index("ix_school_classes_teacher_org", "teacher_id", "org_id"),
    )


class YearGroup(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A managed year group / level (Classes/YearGroups → Manage YearGroups). The
    ordered taxonomy above classes — e.g. YEAR 7 … YEAR 12, plus non-teaching
    groups (Alumni, Entrance Examination) distinguished by ``category``. Feeds the
    class form's Grade-Level picklist; ``SchoolClass.level`` stays free-text."""
    __tablename__ = "year_groups"

    name = Column(String(80), nullable=False)
    short_code = Column(String(20), nullable=True)      # e.g. "Y7", "PN"
    category = Column(String(20), default="active", nullable=False)  # active | alumni | prospective
    position = Column(Integer, default=0, nullable=False)
    is_mock = Column(Boolean, default=False, nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_year_group_org_name"),
        Index("ix_year_groups_org", "org_id"),
    )


class Subject(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "subjects"

    name = Column(String(100), nullable=False)
    code = Column(String(20), nullable=True)
    description = Column(Text, nullable=True)
    department = Column(String(100), nullable=True)
    credit_hours = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    teacher_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    # Free-text teacher label — the Subjects UI captures a name, not a linked user.
    teacher_name = Column(String(120), nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        Index("ix_subjects_teacher_org", "teacher_id", "org_id"),
    )


class AttendanceRecord(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "attendance_records"

    student_id = Column(String(36), ForeignKey("students.id"), nullable=False, index=True)
    class_id = Column(String(36), ForeignKey("school_classes.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    status = Column(Enum(AttendanceStatus), nullable=False, default=AttendanceStatus.PRESENT)
    marked_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    # Structured reason for a non-present mark (Attendance Setup). Nullable +
    # additive: existing rows and present marks carry no reason.
    reason_id = Column(String(36), ForeignKey("absence_reasons.id"), nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    student = relationship("Student", back_populates="attendance_records")


class AttendanceSettings(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Per-org attendance configuration (Attendance Setup). One row per org.

    ``late_after_time`` replaces the global ``SCHOOL_LATE_AFTER`` env constant as
    the per-org source of truth: a check-in at/after this local time derives a
    LATE daily record. The env value remains the fallback when a school hasn't
    configured one, so ingestion keeps working out of the box.
    """
    __tablename__ = "attendance_settings"

    late_after_time = Column(Time, nullable=False)
    # School Attendance Setup (Educare parity): the departure cutoff + notify toggles.
    # A check-out at/after this local time is a LATE departure (monitor + logs).
    max_departure_time = Column(Time, nullable=True)
    notify_email = Column(Boolean, default=False, nullable=False)
    notify_sms = Column(Boolean, default=False, nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, unique=True, index=True)


class AbsenceReason(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A configurable reason code for a non-present attendance mark.

    ``is_authorized`` distinguishes authorised/excused absences from
    unauthorised ones for reporting. Reasons are deactivated, never hard-deleted,
    once referenced by an attendance record — historical marks keep their reason.
    """
    __tablename__ = "absence_reasons"

    code = Column(String(40), nullable=False)
    label = Column(String(120), nullable=False)
    is_authorized = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("org_id", "code", name="uq_absence_reasons_org_code"),
    )


class AttendanceEventType(str, enum.Enum):
    CHECK_IN = "check_in"
    CHECK_OUT = "check_out"


class AttendanceEventSource(str, enum.Enum):
    MANUAL = "manual"   # entered by staff in the portal
    ZKTECO = "zkteco"   # pushed by a ZKTeco biometric device adapter (future)
    IMPORT = "import"   # bulk CSV / sync import
    API = "api"         # generic external integration


class AttendanceEvent(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Timestamped check-in / check-out event — the event-sourced backbone of
    attendance.

    Deliberately separate from the daily roll-call ``AttendanceRecord``:
    biometric devices (e.g. ZKTeco) emit *punches* with a precise timestamp and
    a direction, whereas ``AttendanceRecord`` is a once-per-day present/absent
    status. Ingesting an event here *derives* / updates the daily record, so the
    existing roll-call API and reports keep working unchanged.

    Extension point: a future ZKTeco adapter only has to translate device
    payloads into these rows (via ``AttendanceIngestionService.ingest``) —
    nothing downstream changes. ``external_ref`` makes ingestion idempotent.
    """

    __tablename__ = "attendance_events"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(Enum(AttendanceEventType), nullable=False)
    event_time = Column(DateTime(timezone=True), nullable=False, index=True)

    # Provenance — how the event reached us. Drives dedup + audit.
    source = Column(Enum(AttendanceEventSource), nullable=False, default=AttendanceEventSource.MANUAL)
    # Device-side unique id for the punch (e.g. ZKTeco transaction id). Used to
    # guarantee idempotent ingestion — re-pushing the same punch is a no-op.
    external_ref = Column(String(128), nullable=True, index=True)
    device_id = Column(String(128), nullable=True)
    raw_payload = Column(JSON, nullable=True)  # original device record, for audit/debug

    # Who recorded it (manual entries). Null for device/automated sources.
    recorded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)

    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    student = relationship("Student")

    __table_args__ = (
        # Idempotent device ingestion: the same punch (source + external_ref)
        # can only land once per tenant. NULL external_ref (manual entries) are
        # distinct under SQL NULL semantics, so manual rows never collide.
        UniqueConstraint("org_id", "source", "external_ref", name="uq_attendance_event_source_ref"),
        # Hot paths: a student's punches over a window; a day's punches.
        Index("ix_attendance_events_student_time", "student_id", "event_time"),
        Index("ix_attendance_events_org_time", "org_id", "event_time"),
    )


class Grade(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "grades"

    student_id = Column(String(36), ForeignKey("students.id"), nullable=False, index=True)
    subject_id = Column(String(36), ForeignKey("subjects.id"), nullable=False, index=True)
    # Set when the grade was entered against an Exam sitting (else a standalone grade).
    exam_id = Column(String(36), ForeignKey("exams.id"), nullable=True, index=True)
    # Set when the grade was fed from a CBT exam (else NULL). Distinct FK from
    # exam_id, which points at the manual `exams` table.
    cbt_exam_id = Column(String(36), ForeignKey("cbt_exams.id"), nullable=True, index=True)
    term = Column(String(50), nullable=True)  # e.g. "Term 1", "Semester 2"
    score = Column(Float, nullable=True)
    max_score = Column(Float, default=100.0)
    grade_letter = Column(String(5), nullable=True)  # A, B, C+...
    remarks = Column(Text, nullable=True)
    status = Column(Enum(GradeStatus), default=GradeStatus.DRAFT)
    graded_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    student = relationship("Student", back_populates="grades")


class StudentReport(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Per-student, per-term report metadata that ISN'T derivable from grades.

    The cognitive marks table, subject totals, average and class position are all
    computed live from ``Grade`` rows at read time; only the human-authored fields
    live here — the class-teacher / head-teacher comments, the attendance summary,
    and the next-term-begins date. One row per (student, term)."""
    __tablename__ = "student_reports"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    term = Column(String(50), nullable=False)
    academic_year = Column(String(20), nullable=True)   # session name snapshot at authoring time
    class_teacher_comment = Column(Text, nullable=True)
    head_teacher_comment = Column(Text, nullable=True)
    attendance_present = Column(Integer, nullable=True)  # days present
    attendance_total = Column(Integer, nullable=True)    # school days in the term (absent = total - present)
    next_term_begins = Column(Date, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("student_id", "term", "org_id", name="uq_student_report_student_term"),
        Index("ix_student_reports_org_term", "org_id", "term"),
    )


class Exam(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A manual exam sitting for a class + subject — teachers enter marks against
    it, which land as Grade rows tagged with exam_id (so results flow into the
    existing report-card). Distinct from CBTExam, which is online/auto-scored."""
    __tablename__ = "exams"

    name = Column(String(150), nullable=False)
    exam_type = Column(String(30), default="midterm", nullable=False)  # midterm/final/quiz/assignment/practical
    subject_id = Column(String(36), ForeignKey("subjects.id"), nullable=True, index=True)
    class_id = Column(String(36), ForeignKey("school_classes.id"), nullable=True, index=True)
    term = Column(String(50), nullable=True)
    session_year = Column(String(20), nullable=True)
    exam_date = Column(Date, nullable=True)
    start_time = Column(String(10), nullable=True)
    end_time = Column(String(10), nullable=True)
    total_marks = Column(Float, default=100.0, nullable=False)
    pass_marks = Column(Float, default=40.0, nullable=False)
    status = Column(Enum(ExamSittingStatus), default=ExamSittingStatus.SCHEDULED, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class Timetable(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "timetables"

    class_id = Column(String(36), ForeignKey("school_classes.id"), nullable=False, index=True)
    subject_id = Column(String(36), ForeignKey("subjects.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Mon, 6=Sun
    start_time = Column(String(10), nullable=False)  # "08:00"
    end_time = Column(String(10), nullable=False)    # "09:00"
    room = Column(String(50), nullable=True)
    teacher_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    school_class = relationship("SchoolClass", back_populates="timetables")


# ── School Experience Layer ───────────────────────────────────────────────────
#
# Everything below powers the student/teacher-facing experience (eClassroom,
# CBT, pastoral care, feedback, clubs, journals, tuckshop). All tables are
# tenant-scoped via TenantMixin and accessed through RBAC'd routers that
# always pin org_id server-side.


class AssignmentStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"


class SubmissionStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    GRADED = "graded"
    RETURNED = "returned"


class Assignment(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "assignments"

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    instructions = Column(Text, nullable=True)
    class_id = Column(String(36), ForeignKey("school_classes.id"), nullable=False, index=True)
    subject_id = Column(String(36), ForeignKey("subjects.id"), nullable=True)
    teacher_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    max_points = Column(Float, default=100.0)
    attachment_url = Column(String(500), nullable=True)
    status = Column(Enum(AssignmentStatus), default=AssignmentStatus.PUBLISHED, nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class AssignmentSubmission(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "assignment_submissions"

    assignment_id = Column(String(36), ForeignKey("assignments.id"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("students.id"), nullable=False, index=True)
    content = Column(Text, nullable=True)
    file_url = Column(String(500), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    score = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)
    graded_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    graded_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(Enum(SubmissionStatus), default=SubmissionStatus.SUBMITTED, nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class LessonPlanStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class LessonPlan(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Teacher's written plan for a single lesson. Intentionally decoupled
    from `Timetable` — teachers often plan ad-hoc revision or catch-up
    lessons outside the scheduled grid. A plan pins to `class_id + subject_id
    + lesson_date`; an optional `period` lets a teacher run two lessons with
    the same class/subject on the same day without conflicting."""

    __tablename__ = "lesson_plans"

    title = Column(String(255), nullable=False)
    class_id = Column(String(36), ForeignKey("school_classes.id"), nullable=False, index=True)
    subject_id = Column(String(36), ForeignKey("subjects.id"), nullable=False, index=True)
    teacher_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    lesson_date = Column(Date, nullable=False, index=True)
    period = Column(Integer, nullable=True)  # optional 1..N within the day
    duration_minutes = Column(Integer, default=45)

    # Content — all free-text. We keep the shape flat so the CRUD UI is
    # a simple form and search can grep across a single text column later.
    objectives = Column(Text, nullable=True)  # what students will learn
    activities = Column(Text, nullable=True)  # what teacher/students do
    materials = Column(Text, nullable=True)   # chalk, slides, pages 24–31
    homework = Column(Text, nullable=True)    # assigned tasks
    notes = Column(Text, nullable=True)       # private teacher notes

    # Optional Lesson-Planner-Setup taxonomy label (Theory / Practical / …).
    category_id = Column(String(36), ForeignKey("lesson_plan_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(Enum(LessonPlanStatus), default=LessonPlanStatus.DRAFT, nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        # Hot path: "plans for my class this week" — teacher opens the planner.
        Index("ix_lesson_plans_teacher_date", "teacher_id", "lesson_date"),
        # "What lessons does this class have planned on day X?" — student view.
        Index("ix_lesson_plans_class_date", "class_id", "lesson_date"),
    )


class LessonPlanCategory(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A label for organising lesson plans (Theory / Practical / Revision …) —
    Lesson Planner Setup taxonomy. Optional on a plan (LessonPlan.category_id)."""
    __tablename__ = "lesson_plan_categories"

    name = Column(String(100), nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_lesson_plan_category_org_name"),
    )


class LessonPlannerSettings(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Per-org lesson-planner configuration (Lesson Planner Setup → Settings).
    One row per org. ``require_approval`` marks the workflow where a plan needs a
    supervisor's approval (publish) rather than teacher self-publish."""
    __tablename__ = "lesson_planner_settings"

    require_approval = Column(Boolean, default=False, nullable=False)
    default_duration_minutes = Column(Integer, default=45, nullable=False)
    allow_backdated = Column(Boolean, default=True, nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, unique=True, index=True)


class LessonPlanSupervisor(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Assigns a user as a lesson-plan supervisor, optionally scoped to a section
    (level) — the reviewers who own the Approve queue. One row per (supervisor,
    section); a null section means org-wide."""
    __tablename__ = "lesson_plan_supervisors"

    supervisor_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id = Column(String(36), ForeignKey("school_sections.id", ondelete="CASCADE"), nullable=True, index=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("org_id", "supervisor_id", "section_id", name="uq_lesson_plan_supervisor"),
    )


class LessonPlanSchedule(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A recurring lesson-plan reminder (Lesson Planner Setup → Schedules). On its
    due day/time it delivers ``subject``/``body`` to the audience as an in-app
    Mailbox message (and an email when SMTP is configured). ``last_run_on`` makes
    firing idempotent per day so a poller can call run-due safely on any cadence."""
    __tablename__ = "lesson_plan_schedules"

    subject = Column(String(200), nullable=False)       # the "email content"
    body = Column(Text, nullable=True)
    audience = Column(String(20), default="teachers", nullable=False)   # teachers | all_staff
    frequency = Column(String(20), default="weekly", nullable=False)    # daily | weekly
    days = Column(JSON, nullable=True)                  # [0..6] weekdays (Mon=0) for weekly
    run_time = Column(Time, nullable=False)             # local time of day to fire
    is_active = Column(Boolean, default=True, nullable=False)
    last_run_on = Column(Date, nullable=True)           # date last dispatched (idempotency)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class WeeklyReflection(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Students log a short weekly reflection; teachers can comment."""
    __tablename__ = "weekly_reflections"

    student_id = Column(String(36), ForeignKey("students.id"), nullable=False, index=True)
    week_start = Column(Date, nullable=False, index=True)
    content = Column(Text, nullable=False)
    mood = Column(String(30), nullable=True)  # happy, sad, stressed, etc.
    teacher_comment = Column(Text, nullable=True)
    commented_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    commented_at = Column(DateTime(timezone=True), nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


# ── CBT (Computer-Based Testing) ─────────────────────────────────────────────


class ExamStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ACTIVE = "active"
    CLOSED = "closed"


class QuestionType(str, enum.Enum):
    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    LONG_ANSWER = "long_answer"


class AttemptStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    GRADED = "graded"


class CBTExam(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "cbt_exams"

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    class_id = Column(String(36), ForeignKey("school_classes.id"), nullable=True, index=True)
    subject_id = Column(String(36), ForeignKey("subjects.id"), nullable=True)
    # Term this sitting belongs to (e.g. "Term 1") — tags fed Grade rows so the
    # gradebook can scope/publish them. Required before results can feed the gradebook.
    term = Column(String(50), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration_minutes = Column(Integer, default=60)
    total_points = Column(Float, default=0.0)
    shuffle_questions = Column(Boolean, default=False)
    # Max completed attempts per student. 1 = single sitting (default); 0 = unlimited.
    max_attempts = Column(Integer, default=1, nullable=False)
    # Pass mark for this exam (%). NULL → fall back to the org CBT default.
    pass_percentage = Column(Integer, nullable=True)
    # Results distribution (Phase 1). hold_results gates a student's view of their
    # score until results are published; publishing snapshots the resolved pass
    # mark so the released view is frozen even if the live pass mark later changes.
    hold_results = Column(Boolean, default=False, nullable=False)
    results_published_at = Column(DateTime(timezone=True), nullable=True)
    results_published_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    published_pass_percentage = Column(Integer, nullable=True)
    status = Column(Enum(ExamStatus), default=ExamStatus.DRAFT, nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class CBTQuestion(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "cbt_questions"

    exam_id = Column(String(36), ForeignKey("cbt_exams.id"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(Enum(QuestionType), default=QuestionType.MCQ, nullable=False)
    options = Column(JSON, nullable=True)  # [{"key": "a", "text": "..."}, ...]
    correct_answer = Column(Text, nullable=True)  # "a" or free text
    points = Column(Float, default=1.0)
    position = Column(Integer, default=0)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class CBTAttempt(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "cbt_attempts"

    exam_id = Column(String(36), ForeignKey("cbt_exams.id"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("students.id"), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    score = Column(Float, nullable=True)
    max_score = Column(Float, nullable=True)
    status = Column(Enum(AttemptStatus), default=AttemptStatus.IN_PROGRESS, nullable=False)
    # True when submitted after the deadline (within the accepted late window).
    submitted_late = Column(Boolean, default=False, nullable=False)
    # Reset-for-retake soft-delete: a superseded attempt is kept for the record but
    # doesn't count toward the attempt limit and is excluded from Result Manager
    # stats. NULL = active.
    superseded_at = Column(DateTime(timezone=True), nullable=True)
    superseded_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    # Staff textual remark on the result ("Test Remark") — distinct from the
    # per-answer manual grading flow (which awards points).
    remark_note = Column(Text, nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class CBTAnswer(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "cbt_answers"

    attempt_id = Column(String(36), ForeignKey("cbt_attempts.id"), nullable=False, index=True)
    question_id = Column(String(36), ForeignKey("cbt_questions.id"), nullable=False)
    answer_text = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    points_awarded = Column(Float, nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class QuestionBankItem(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A reusable CBT question, independent of any single exam — the Question Bank.
    Categorised by subject + topic + difficulty. Tests are composed by copying
    selected items into an exam's CBTQuestion set, so the existing exam→attempt→
    score flow is untouched; the bank is just the reusable pool feeding it."""
    __tablename__ = "cbt_question_bank"

    subject_id = Column(String(36), ForeignKey("subjects.id"), nullable=True, index=True)
    topic = Column(String(150), nullable=True, index=True)
    difficulty = Column(String(20), default="medium", nullable=False)  # easy / medium / hard
    question_text = Column(Text, nullable=False)
    question_type = Column(Enum(QuestionType), default=QuestionType.MCQ, nullable=False)
    options = Column(JSON, nullable=True)          # [{"key": "a", "text": "..."}, ...]
    correct_answer = Column(Text, nullable=True)
    points = Column(Float, default=1.0, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        Index("ix_cbt_question_bank_subject_org", "subject_id", "org_id"),
    )


class InterventionStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class CBTIntervention(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A post-result flag — a student who underperformed on a CBT exam plus the
    follow-up the school tracks to resolution (Phase C)."""
    __tablename__ = "cbt_interventions"

    student_id = Column(String(36), ForeignKey("students.id"), nullable=False, index=True)
    exam_id = Column(String(36), ForeignKey("cbt_exams.id"), nullable=True, index=True)
    attempt_id = Column(String(36), ForeignKey("cbt_attempts.id"), nullable=True)
    reason = Column(Text, nullable=False)
    note = Column(Text, nullable=True)          # the follow-up plan / actions taken
    status = Column(Enum(InterventionStatus), default=InterventionStatus.OPEN, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    resolved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class CBTSettings(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Org-level CBT defaults used to prefill new exams (one row per org)."""
    __tablename__ = "cbt_settings"

    default_duration_minutes = Column(Integer, default=60, nullable=False)
    default_pass_percentage = Column(Integer, default=50, nullable=False)
    shuffle_default = Column(Boolean, default=False, nullable=False)
    instructions = Column(Text, nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, unique=True, index=True)


# ── Pastoral / Behaviour ─────────────────────────────────────────────────────


class BehaviourType(str, enum.Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class BehaviourRecord(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "behaviour_records"

    student_id = Column(String(36), ForeignKey("students.id"), nullable=False, index=True)
    recorded_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    type = Column(Enum(BehaviourType), default=BehaviourType.POSITIVE, nullable=False)
    category = Column(String(100), nullable=True)  # e.g. "Punctuality", "Teamwork" (free-text, back-compat)
    # Optional links into the managed taxonomy (BehaviourCategory / BehaviourSubCategory).
    # The free-text `category` above is kept so existing records don't break.
    category_id = Column(String(36), ForeignKey("behaviour_categories.id"), nullable=True, index=True)
    subcategory_id = Column(String(36), ForeignKey("behaviour_subcategories.id"), nullable=True, index=True)
    description = Column(Text, nullable=False)
    points = Column(Integer, default=0)  # +ve or -ve
    incident_date = Column(Date, nullable=False, index=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        # Behaviour aggregate widget: filter by org, range-scan by date.
        Index("ix_behaviour_records_org_date", "org_id", "incident_date"),
    )


class BehaviourCategory(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Top-level behaviour taxonomy ("Manage behaviourTracker"). A category is
    positive/negative/neutral, may carry a default point value, and is what a
    behaviour record is filed under."""
    __tablename__ = "behaviour_categories"

    name = Column(String(100), nullable=False)
    type = Column(Enum(BehaviourType), default=BehaviourType.POSITIVE, nullable=False)
    default_points = Column(Integer, nullable=True)  # suggested points; record may override
    description = Column(Text, nullable=True)
    position = Column(Integer, default=0, nullable=False)  # display order
    is_active = Column(Boolean, default=True, nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class BehaviourSubCategory(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Sub-item under a BehaviourCategory ("Sub-manage behaviourTracker") — e.g.
    "Late to class" under a "Punctuality" category."""
    __tablename__ = "behaviour_subcategories"

    category_id = Column(String(36), ForeignKey("behaviour_categories.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    default_points = Column(Integer, nullable=True)  # overrides the category default when set
    position = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class BehaviourLevel(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A named conduct band ("Manage behaviour levels"). A student's cumulative
    conduct points fall into the band whose [min_points, max_points] contains
    them (max_points NULL = open-ended top). min_points may be negative."""
    __tablename__ = "behaviour_levels"

    name = Column(String(100), nullable=False)
    min_points = Column(Integer, nullable=False)          # inclusive lower bound (can be negative)
    max_points = Column(Integer, nullable=True)           # inclusive upper bound; NULL = no cap
    colour = Column(String(20), nullable=True)            # optional UI accent, e.g. "emerald"
    description = Column(Text, nullable=True)
    position = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class BehaviourSettings(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Per-org Behaviour Tracker configuration ("BehaviourTracker settings")."""
    __tablename__ = "behaviour_settings"

    default_points = Column(Integer, default=1, nullable=False)     # pre-fill for new records
    visible_to_students = Column(Boolean, default=False, nullable=False)
    visible_to_parents = Column(Boolean, default=False, nullable=False)
    auto_derive_levels = Column(Boolean, default=True, nullable=False)  # classify from cumulative points
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, unique=True, index=True)


# ── Feedback ─────────────────────────────────────────────────────────────────


class FeedbackCategory(str, enum.Enum):
    GENERAL = "general"
    FACILITIES = "facilities"
    TEACHING = "teaching"
    BULLYING = "bullying"
    SUGGESTION = "suggestion"
    OTHER = "other"


class StudentFeedback(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "student_feedback"

    submitted_by = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("students.id"), nullable=True)
    subject = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    category = Column(Enum(FeedbackCategory), default=FeedbackCategory.GENERAL, nullable=False)
    is_anonymous = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)
    admin_response = Column(Text, nullable=True)
    responded_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    responded_at = Column(DateTime(timezone=True), nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class TeacherRating(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A student's 1–5 star rating (+ optional comment) of a teacher. One current
    rating per (student, teacher) — resubmitting updates the existing row."""
    __tablename__ = "teacher_ratings"

    teacher_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("students.id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)  # 1–5
    comment = Column(Text, nullable=True)
    subject_id = Column(String(36), ForeignKey("subjects.id"), nullable=True)
    term = Column(String(50), nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        Index("ix_teacher_ratings_teacher_org", "teacher_id", "org_id"),
    )


# ── Clubs & Activities ───────────────────────────────────────────────────────


class Club(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "clubs"

    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    advisor_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    meeting_day = Column(String(20), nullable=True)  # e.g. "Wednesday"
    meeting_time = Column(String(20), nullable=True)
    location = Column(String(100), nullable=True)
    max_members = Column(Integer, nullable=True)
    cover_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class ClubMembership(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "club_memberships"

    club_id = Column(String(36), ForeignKey("clubs.id"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("students.id"), nullable=False, index=True)
    joined_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    role = Column(String(50), default="member")  # member, president, secretary
    is_active = Column(Boolean, default=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


# ── Photo Journals ───────────────────────────────────────────────────────────


class PhotoJournal(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "photo_journals"

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    photo_url = Column(String(500), nullable=False)
    taken_date = Column(Date, nullable=True)
    posted_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    class_id = Column(String(36), ForeignKey("school_classes.id"), nullable=True)
    club_id = Column(String(36), ForeignKey("clubs.id"), nullable=True)
    tags = Column(JSON, default=list)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


# ── Weekly Remarks ───────────────────────────────────────────────────────────


class WeeklyRemark(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Teacher remarks on a student for a given week. Admin-visible."""
    __tablename__ = "weekly_remarks"

    student_id = Column(String(36), ForeignKey("students.id"), nullable=False, index=True)
    teacher_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    week_start = Column(Date, nullable=False, index=True)
    remark = Column(Text, nullable=False)
    strengths = Column(Text, nullable=True)
    areas_to_improve = Column(Text, nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


# ── Tuckshop ─────────────────────────────────────────────────────────────────


# ── Library (Phase 6.5) ──────────────────────────────────────────────────────
#
# Borrower identity is modelled as a User FK so the same table handles
# students (via their linked User row), teachers, and staff uniformly. We
# denormalise `available_copies` onto the book row because "is this book
# available?" is the hottest read in the catalogue, and it saves a COUNT
# on every page paint. The invariant — available_copies == total_copies
# minus active loans — is maintained atomically in the loan/return handlers.


class LibraryBook(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "library_books"

    title = Column(String(255), nullable=False, index=True)
    author = Column(String(255), nullable=False)
    isbn = Column(String(20), nullable=True, index=True)
    category = Column(String(60), nullable=True, index=True)   # Fiction, Science, etc.
    publisher = Column(String(255), nullable=True)
    publication_year = Column(Integer, nullable=True)
    cover_url = Column(String(500), nullable=True)
    shelf_location = Column(String(30), nullable=True)         # e.g. "A3-15"
    total_copies = Column(Integer, default=1, nullable=False)
    available_copies = Column(Integer, default=1, nullable=False)
    description = Column(Text, nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        # Catalogue search: "books where title LIKE :q AND org=?" is the hot path.
        Index("ix_library_books_title_org", "title", "org_id"),
    )


class LoanStatus(str, enum.Enum):
    BORROWED = "borrowed"
    RETURNED = "returned"
    # Note: `overdue` is a derived state (status==BORROWED and due_date < today),
    # never stored — see routers/modules/library.py.


class LibraryLoan(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "library_loans"

    book_id = Column(String(36), ForeignKey("library_books.id"), nullable=False, index=True)
    borrower_user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    issued_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    borrowed_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    due_date = Column(Date, nullable=False, index=True)
    returned_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(Enum(LoanStatus), default=LoanStatus.BORROWED, nullable=False, index=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        # "My current loans" — student home + My Library page.
        Index("ix_library_loans_borrower_status", "borrower_user_id", "status"),
        # "All overdue books" — admin overdue filter.
        Index("ix_library_loans_status_due", "status", "due_date"),
    )


class LibrarySettings(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Per-org library configuration (Library Setup → General + borrowing rules).
    One row per org. ``loan_period_days`` defaults a loan's due date; the borrowing
    limits are the "permissions" (how many books a member may hold at once)."""
    __tablename__ = "library_settings"

    loan_period_days = Column(Integer, default=14, nullable=False)
    max_books_per_user = Column(Integer, default=3, nullable=False)
    allow_reviews = Column(Boolean, default=True, nullable=False)
    review_needs_approval = Column(Boolean, default=True, nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, unique=True, index=True)


class LibraryCategory(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A managed book category (Library Setup → Book Category). Feeds the catalogue
    picklist; ``LibraryBook.category`` keeps its free-text value for back-compat."""
    __tablename__ = "library_categories"

    name = Column(String(80), nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_library_category_org_name"),
    )


class LibraryLocation(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A managed shelf/location (Library Setup → Library Locations). Feeds the
    catalogue's shelf picklist; ``LibraryBook.shelf_location`` stays free-text."""
    __tablename__ = "library_locations"

    name = Column(String(80), nullable=False)      # e.g. "Aisle A — Fiction"
    code = Column(String(30), nullable=True)       # e.g. "A3"
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_library_location_org_name"),
    )


class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class BookReview(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A reader's review of a book (Library → Manage Reviews). Moderated: a review
    is PENDING until a librarian approves it (only approved reviews are public)."""
    __tablename__ = "book_reviews"

    book_id = Column(String(36), ForeignKey("library_books.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    rating = Column(Integer, nullable=False)       # 1..5
    comment = Column(Text, nullable=True)
    status = Column(Enum(ReviewStatus), default=ReviewStatus.PENDING, nullable=False, index=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        Index("ix_book_reviews_book_status", "book_id", "status"),
    )


class TuckshopProduct(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "tuckshop_products"

    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0)
    image_url = Column(String(500), nullable=True)
    category = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)


class TuckshopPurchase(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tuckshop_purchases"

    student_id = Column(String(36), ForeignKey("students.id"), nullable=False, index=True)
    product_id = Column(String(36), ForeignKey("tuckshop_products.id"), nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    sold_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        # Tuckshop sales summary: today's revenue is org_id + created_at range.
        Index("ix_tuckshop_purchases_org_created", "org_id", "created_at"),
    )


# ── Feedback module extras ───────────────────────────────────────────────────
# The reference groups several loosely-related surfaces under "Feedback":
# module settings, staff daily reports, per-student daily reports, and a light
# CRM/enquiry pipeline. Kept minimal + tenant-scoped.

class FeedbackSettings(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Per-org configuration for the feedback channel ("Feedback Settings")."""
    __tablename__ = "feedback_settings"

    allow_anonymous = Column(Boolean, default=True, nullable=False)
    notify_on_submit = Column(Boolean, default=False, nullable=False)
    acknowledgement_message = Column(Text, nullable=True)   # auto-shown to a submitter
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, unique=True, index=True)


class DailyReport(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A staff member's daily activity log ("Daily Report")."""
    __tablename__ = "daily_reports"

    author_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    report_date = Column(Date, nullable=False, index=True)
    class_id = Column(String(36), ForeignKey("school_classes.id"), nullable=True)
    summary = Column(Text, nullable=False)
    highlights = Column(Text, nullable=True)
    challenges = Column(Text, nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        Index("ix_daily_reports_org_date", "org_id", "report_date"),
    )


class StudentDailyReport(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A per-student daily note ("Student Daily Report") — mood + academic/
    behaviour observations for a given day, authored by a staff member."""
    __tablename__ = "student_daily_reports"

    student_id = Column(String(36), ForeignKey("students.id"), nullable=False, index=True)
    author_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    report_date = Column(Date, nullable=False, index=True)
    mood = Column(String(20), nullable=True)               # happy | neutral | sad | …
    academic = Column(Text, nullable=True)
    behaviour = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        Index("ix_student_daily_reports_student_date", "student_id", "report_date"),
    )


# NOTE: A standalone CRMContact model was briefly added here, then removed — the
# "CRM" surface duplicated Admissions & Enquiries (AdmissionApplication already
# tracks prospective-parent contact + source + a status stage pipeline + notes).
# The CRM page is now a thin view over admission-application data; there is no
# parallel CRM table. See migration 052 (drops crm_contacts).
