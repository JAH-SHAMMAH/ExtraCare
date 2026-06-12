import enum
from sqlalchemy import Column, String, Integer, Float, JSON, Text, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class ImportStatus(str, enum.Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ImportJob(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """
    Tracks every CSV import operation. Provides audit trail, error storage,
    and batch-level undo (soft-delete all records created by this import).
    """
    __tablename__ = "import_jobs"

    # What was imported
    entity = Column(String(50), nullable=False, index=True)    # students, patients, employees, inventory, transactions
    filename = Column(String(500), nullable=False)
    status = Column(Enum(ImportStatus), default=ImportStatus.PROCESSING, nullable=False, index=True)

    # Counts
    total_rows = Column(Integer, default=0)
    valid_rows = Column(Integer, default=0)
    created = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    skipped_invalid = Column(Integer, default=0)
    skipped_duplicate = Column(Integer, default=0)

    # Timing
    duration_ms = Column(Integer, default=0)

    # IDs of records created by this import (for undo/rollback)
    created_ids = Column(JSON, default=list)  # ["uuid1", "uuid2", ...]

    # Error details — stored as JSON array: [{ row, error, data }]
    error_details = Column(JSON, default=list)

    # Who ran the import
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user_email = Column(String(320), nullable=True)  # denormalized for permanence

    # Conflict resolution strategy used
    duplicate_strategy = Column(String(20), default="skip")  # skip, overwrite, merge

    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], lazy="raise")
    organization = relationship("Organization", lazy="raise")
