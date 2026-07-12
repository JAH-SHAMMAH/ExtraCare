"""Admissions & Enrollment models (Batch 2).

The student lifecycle: enquiry → application → entrance exam → admit (→ creates a
Student) → promote / transfer-out. All tenant-scoped (``org_id``). Status/stage/
outcome/type are stored as plain strings and validated in the schema layer —
keeps migrations simple (no DB enums) and matches the Batch 1 convention.

Cross-model display names (student, class) are resolved in the router via cheap
id→name lookups rather than ORM relationships, so these tables stay
self-contained and free of async lazy-load pitfalls.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, Date, Integer, Boolean, DateTime, ForeignKey, Index

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


class AdmissionApplication(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A prospective student's enquiry / application."""
    __tablename__ = "admission_applications"

    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True)

    guardian_name = Column(String(200), nullable=True)
    guardian_phone = Column(String(50), nullable=True)
    guardian_email = Column(String(320), nullable=True)

    applying_for_class_id = Column(String(36), ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True)
    applying_for_level = Column(String(80), nullable=True)
    source = Column(String(80), nullable=True)  # walk-in / referral / online / …
    # enquiry | applied | screening | offered | admitted | rejected | withdrawn
    status = Column(String(20), default="enquiry", nullable=False)
    notes = Column(Text, nullable=True)

    # Set when the application is admitted and converted into a Student.
    admitted_student_id = Column(String(36), ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_admission_applications_org_status", "org_id", "status"),
    )


class EntranceExam(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """An entrance examination event applicants sit for assessment."""
    __tablename__ = "entrance_exams"

    title = Column(String(200), nullable=False)
    exam_date = Column(Date, nullable=True)
    subject = Column(String(120), nullable=True)
    max_score = Column(Integer, default=100, nullable=False)
    status = Column(String(20), default="scheduled", nullable=False)  # scheduled | completed
    notes = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_entrance_exams_org_date", "org_id", "exam_date"),
    )


class EntranceExamResult(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A single applicant's score on an entrance exam."""
    __tablename__ = "entrance_exam_results"

    exam_id = Column(String(36), ForeignKey("entrance_exams.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(String(36), ForeignKey("admission_applications.id", ondelete="SET NULL"), nullable=True, index=True)
    candidate_name = Column(String(200), nullable=False)  # denormalised for display
    score = Column(Integer, nullable=True)
    outcome = Column(String(20), default="pending", nullable=False)  # pending | pass | fail
    remark = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_entrance_results_exam_org", "exam_id", "org_id"),
    )


class PromotionRecord(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """An audit row for moving a student between classes at term/year roll-over.

    ``batch_id`` groups every record produced by a single bulk run so the run
    can be previewed, audited, and reversed atomically. The record itself is a
    before/after snapshot (``from_class_id`` → ``to_class_id`` + ``outcome``).
    """
    __tablename__ = "promotion_records"

    batch_id = Column(String(36), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    from_class_id = Column(String(36), ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True)
    to_class_id = Column(String(36), ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True)
    academic_year = Column(String(20), nullable=True)
    outcome = Column(String(20), default="promoted", nullable=False)  # promoted | repeated | graduated
    # Snapshot of the student's active flag BEFORE the run, so a revert can
    # restore it precisely (graduation flips it; revert flips it back).
    prev_is_active = Column(Boolean, default=True, nullable=False)
    reverted_at = Column(DateTime(timezone=True), nullable=True)
    promoted_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_promotion_records_student_org", "student_id", "org_id"),
        Index("ix_promotion_records_batch", "batch_id", "org_id"),
    )


class StudentAuthorizedPickup(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A person authorised to collect a student from school.

    Registry only — no per-day pickup/dismissal log (deferred). Deactivate-not-
    delete: removing an authorisation flips ``is_active`` rather than dropping
    the row, preserving the history of who could collect a child.
    """
    __tablename__ = "student_authorized_pickups"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name = Column(String(200), nullable=False)
    relationship_type = Column(String(50), nullable=True)  # parent | guardian | driver | sibling | other
    phone = Column(String(50), nullable=True)
    id_document = Column(String(120), nullable=True)       # ID type/number for gate verification
    photo_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_student_pickups_student_org", "student_id", "org_id"),
    )


class TransferRecord(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A student leaving the school (transfer-out or withdrawal)."""
    __tablename__ = "transfer_records"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    transfer_type = Column(String(20), default="transfer_out", nullable=False)  # transfer_out | withdrawal
    destination_school = Column(String(200), nullable=True)
    reason = Column(Text, nullable=True)
    transfer_date = Column(Date, nullable=True)
    status = Column(String(20), default="pending", nullable=False)  # pending | completed
    processed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_transfer_records_student_org", "student_id", "org_id"),
    )
