"""HR Documents & Templates — org HR documents (policies, forms, templates).

Each row references a file already stored via POST /upload/document (which returns
the /uploads/... URL). Confidential HR admin: gated ``hr:write``.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, ForeignKey, Index

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


class HrDocument(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """One HR document / template entry pointing at an uploaded file."""
    __tablename__ = "hr_documents"

    title = Column(String(200), nullable=False)
    category = Column(String(80), nullable=True)
    description = Column(Text, nullable=True)
    file_url = Column(String(500), nullable=False)     # /uploads/<org>/documents/<file>
    filename = Column(String(255), nullable=True)      # original upload name
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (Index("ix_hr_documents_org_category", "org_id", "category"),)
