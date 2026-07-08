from sqlalchemy import Column, String, Integer, Float, Date, DateTime, Text, Boolean, Enum, ForeignKey, JSON, Index, UniqueConstraint
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
    level = Column(String(50), nullable=True)   # e.g. "Secondary", "Primary" (UI: grade_level)
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
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    student = relationship("Student", back_populates="attendance_records")


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
    term = Column(String(50), nullable=True)  # e.g. "Term 1", "Semester 2"
    score = Column(Float, nullable=True)
    max_score = Column(Float, default=100.0)
    grade_letter = Column(String(5), nullable=True)  # A, B, C+...
    remarks = Column(Text, nullable=True)
    status = Column(Enum(GradeStatus), default=GradeStatus.DRAFT)
    graded_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    student = relationship("Student", back_populates="grades")


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

    status = Column(Enum(LessonPlanStatus), default=LessonPlanStatus.DRAFT, nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        # Hot path: "plans for my class this week" — teacher opens the planner.
        Index("ix_lesson_plans_teacher_date", "teacher_id", "lesson_date"),
        # "What lessons does this class have planned on day X?" — student view.
        Index("ix_lesson_plans_class_date", "class_id", "lesson_date"),
    )


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
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration_minutes = Column(Integer, default=60)
    total_points = Column(Float, default=0.0)
    shuffle_questions = Column(Boolean, default=False)
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
    category = Column(String(100), nullable=True)  # e.g. "Punctuality", "Teamwork"
    description = Column(Text, nullable=False)
    points = Column(Integer, default=0)  # +ve or -ve
    incident_date = Column(Date, nullable=False, index=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    __table_args__ = (
        # Behaviour aggregate widget: filter by org, range-scan by date.
        Index("ix_behaviour_records_org_date", "org_id", "incident_date"),
    )


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
