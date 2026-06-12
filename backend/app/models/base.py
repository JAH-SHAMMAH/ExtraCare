import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean, func
from sqlalchemy.dialects.sqlite import TEXT as SQLITE_TEXT
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class TimestampMixin:
    """Adds created_at / updated_at to every model."""
    created_at = Column(DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class UUIDMixin:
    """UUID primary key — DB-agnostic, tenant-safe."""
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)


class TenantMixin:
    """Every tenant-scoped model carries org_id for row-level isolation."""
    org_id = Column(String(36), nullable=False, index=True)


class SoftDeleteMixin:
    """Soft delete: never physically remove records."""
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
