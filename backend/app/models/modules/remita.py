"""Remita payment gateway — transaction records for parent fee payments.

One row per payment attempt: links our Invoice to Remita's RRR (Remita Retrieval
Reference) and tracks status. Recording is idempotent off ``status`` + ``rrr`` so
the callback and the webhook can't double-pay an invoice.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Numeric, DateTime, JSON, ForeignKey, Index, UniqueConstraint

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class RemitaTransaction(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "remita_transactions"

    invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(36), nullable=True)
    order_id = Column(String(64), nullable=False)          # our unique order ref sent to Remita
    rrr = Column(String(64), nullable=True, index=True)    # Remita Retrieval Reference
    amount = Column(Numeric(14, 2), nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # pending | paid | failed
    payer_name = Column(String(200), nullable=True)
    payer_email = Column(String(255), nullable=True)
    payer_phone = Column(String(50), nullable=True)
    raw_init = Column(JSON, nullable=True)                 # Remita init response
    raw_status = Column(JSON, nullable=True)               # Remita status response
    journal_entry_id = Column(String(36), nullable=True)   # the recorded payment posting
    paid_at = Column(DateTime(timezone=True), nullable=True)
    initiated_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "order_id", name="uq_remita_tx_org_order"),
        Index("ix_remita_tx_org_status", "org_id", "status"),
    )
