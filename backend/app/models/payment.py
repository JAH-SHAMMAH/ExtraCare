"""
Payment Infrastructure Models
==============================

Multi-tenant, multi-provider payment system.

Key principles:
- Each tenant can eventually manage their own payment provider credentials
- Credentials are encrypted at rest
- Payment records are scoped by org_id and never leak across tenants
- Transaction audit trail maintained for compliance
- No single global Paystack account assumption
"""

from sqlalchemy import Column, String, Boolean, Enum, JSON, Text, Integer, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin
import enum


class PaymentProvider(str, enum.Enum):
    """Supported payment gateway providers."""
    PAYSTACK = "paystack"
    FLUTTERWAVE = "flutterwave"
    STRIPE = "stripe"
    BANK_TRANSFER = "bank_transfer"


class PaymentStatus(str, enum.Enum):
    """Payment transaction status."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESSFUL = "successful"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentType(str, enum.Enum):
    """Payment categorization."""
    SCHOOL_FEES = "school_fees"
    TUCKSHOP = "tuckshop"
    SUBSCRIPTION = "subscription"
    PLAN_UPGRADE = "plan_upgrade"
    OTHER = "other"


class TenantPaymentSettings(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    Per-tenant payment provider configuration.
    
    Supports:
    - Organizations with their own provider accounts
    - Platform-level defaults (MVP phase)
    - Encrypted credential storage
    - Multiple providers per tenant
    """
    __tablename__ = "tenant_payment_settings"

    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Provider type (paystack, flutterwave, stripe, etc.)
    provider = Column(Enum(PaymentProvider), nullable=False, index=True)
    
    # Whether this is the active provider for the organization
    is_active = Column(Boolean, default=True, index=True)
    
    # Encrypted credentials (backend stores these via encryption service)
    # Frontend must NEVER see these values
    encrypted_secret_key = Column(Text, nullable=True)
    encrypted_public_key = Column(Text, nullable=True)
    encrypted_webhook_secret = Column(Text, nullable=True)
    
    # Provider metadata (non-sensitive configuration)
    # e.g. {"paystack_account_id": "...", "business_name": "...", "settle_to": "..."}
    metadata_ = Column("metadata", JSON, default=dict)
    
    # Payment verification and settlement
    settlement_account = Column(String(255), nullable=True)  # Bank account or wallet for settlements
    settlement_enabled = Column(Boolean, default=False)  # Whether automatic settlement is enabled
    
    # Provider-specific settings
    webhook_enabled = Column(Boolean, default=True)
    webhook_url = Column(String(500), nullable=True)
    webhook_last_validated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Status tracking
    is_verified = Column(Boolean, default=False)  # Has provider credentials been verified
    verification_attempted_at = Column(DateTime(timezone=True), nullable=True)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Rate limiting and thresholds
    daily_limit = Column(Numeric(15, 2), nullable=True)  # Daily transaction limit in NGN
    transaction_limit = Column(Numeric(15, 2), nullable=True)  # Per-transaction limit in NGN
    
    # Audit and compliance
    notes = Column(Text, nullable=True)  # Internal notes about this configuration
    configured_by_user_id = Column(String(36), nullable=True)  # Which admin configured this

    # Relationships
    organization = relationship("Organization", foreign_keys=[org_id])
    transactions = relationship("PaymentTransaction", back_populates="payment_settings", lazy="dynamic")


class PaymentTransaction(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    Complete audit trail for every payment transaction.
    
    Immutable record of what happened, when, and with whom.
    Used for reconciliation, compliance, and debugging.
    """
    __tablename__ = "payment_transactions"

    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_settings_id = Column(String(36), ForeignKey("tenant_payment_settings.id"), nullable=False, index=True)
    
    # Transaction identification
    reference = Column(String(255), nullable=False, unique=True, index=True)  # e.g. "ec_xyz" or provider's ID
    provider_reference = Column(String(255), nullable=True, index=True)  # Provider's reference ID
    
    # Categorization
    payment_type = Column(Enum(PaymentType), nullable=False, index=True)
    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING, index=True)
    provider = Column(Enum(PaymentProvider), nullable=False, index=True)
    
    # Financial details
    amount_ngn = Column(Numeric(15, 2), nullable=False)  # Always in NGN for consistency
    currency = Column(String(3), default="NGN")
    fee_ngn = Column(Numeric(15, 2), nullable=True)  # Provider fee
    net_amount_ngn = Column(Numeric(15, 2), nullable=True)  # After fees
    
    # Related entities (flexible schema for different payment types)
    student_id = Column(String(36), nullable=True, index=True)  # For school fees
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)  # Who paid / requested payment
    related_id = Column(String(36), nullable=True)  # Subscription ID, invoice ID, etc.
    
    # Payment description
    description = Column(String(500), nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)  # Flexible data: {fee_category, term, class, etc}
    
    # Payment method details
    payment_method = Column(String(50), nullable=True)  # card, bank_transfer, wallet, etc
    last_4_digits = Column(String(4), nullable=True)  # Card last 4 digits if applicable
    
    # Email used for payment
    customer_email = Column(String(255), nullable=True)
    customer_name = Column(String(255), nullable=True)
    
    # Authorization & verification
    authorization_url = Column(String(500), nullable=True)  # For hosted checkout redirect
    verified_at = Column(DateTime(timezone=True), nullable=True)  # When Paystack verified this
    verification_code = Column(String(255), nullable=True)  # Verification status from provider
    
    # Reconciliation
    reconciled_at = Column(DateTime(timezone=True), nullable=True)  # When accountant confirmed
    reconciled_by_user_id = Column(String(36), nullable=True)  # Which admin reconciled
    reconciliation_notes = Column(Text, nullable=True)
    
    # Retry logic
    retry_count = Column(Integer, default=0)
    last_retry_at = Column(DateTime(timezone=True), nullable=True)
    
    # Raw provider response (for debugging and audit)
    provider_response = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    organization = relationship("Organization", foreign_keys=[org_id])
    payment_settings = relationship("TenantPaymentSettings", back_populates="transactions")
    user = relationship("User", foreign_keys=[user_id])
    audits = relationship("PaymentAudit", back_populates="transaction", lazy="dynamic")


class PaymentAudit(Base, UUIDMixin, TimestampMixin):
    """
    Immutable audit log for all payment-related actions.
    
    Compliance requirement: track every access, modification, or decision.
    """
    __tablename__ = "payment_audits"

    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_id = Column(String(36), ForeignKey("payment_transactions.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Action tracking
    action = Column(String(100), nullable=False)  # "initialize", "verify", "reconcile", "refund", "webhook"
    action_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # What changed
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    
    # Context
    description = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(String(500), nullable=True)
    
    # Relationships
    organization = relationship("Organization", foreign_keys=[org_id])
    transaction = relationship("PaymentTransaction", back_populates="audits")
    user = relationship("User", foreign_keys=[action_by_user_id])


class PaymentWebhookEvent(Base, UUIDMixin, TimestampMixin):
    """
    Registry of received webhook events to provide idempotency and
    replay protection. Stores a short hash of the raw payload so the
    same webhook cannot be processed twice.
    """
    __tablename__ = "payment_webhook_events"

    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_id = Column(String(36), ForeignKey("payment_transactions.id"), nullable=True, index=True)
    provider = Column(Enum(PaymentProvider), nullable=False, index=True)
    event_type = Column(String(255), nullable=True)
    event_reference = Column(String(255), nullable=True, index=True)
    raw_hash = Column(String(128), nullable=False, unique=True, index=True)
    received_at = Column(DateTime(timezone=True), nullable=False)
    processed = Column(Boolean, default=False, nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    raw_payload = Column(JSON, nullable=True)

    organization = relationship("Organization", foreign_keys=[org_id])
    transaction = relationship("PaymentTransaction", foreign_keys=[transaction_id])


class StudentFeeRecord(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    School fee structure and outstanding balances.
    
    Tracks what a student owes, broken down by fee category and term.
    """
    __tablename__ = "student_fee_records"

    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(36), nullable=False, index=True)  # Reference to Student model
    
    # Fee categorization
    term = Column(String(50), nullable=False)  # e.g. "term1_2024", "annual_2024"
    session_year = Column(String(10), nullable=False)  # e.g. "2024"
    
    # Fee breakdown
    tuition_fee = Column(Numeric(15, 2), nullable=False, default=0)
    exam_fee = Column(Numeric(15, 2), nullable=False, default=0)
    activity_fee = Column(Numeric(15, 2), nullable=False, default=0)
    transport_fee = Column(Numeric(15, 2), nullable=False, default=0)
    hostel_fee = Column(Numeric(15, 2), nullable=False, default=0)
    other_fees = Column(Numeric(15, 2), nullable=False, default=0)
    
    # Totals
    total_fee = Column(Numeric(15, 2), nullable=False, default=0)
    paid_amount = Column(Numeric(15, 2), nullable=False, default=0)
    outstanding_balance = Column(Numeric(15, 2), nullable=False, default=0)
    
    # Due dates and status
    due_date = Column(DateTime(timezone=True), nullable=True)
    is_paid = Column(Boolean, default=False, index=True)
    payment_status = Column(String(50), default="unpaid")  # unpaid, partial, paid
    
    # Discount/concession
    discount_amount = Column(Numeric(15, 2), nullable=False, default=0)
    discount_reason = Column(String(255), nullable=True)
    
    # Parent/guardian assigned
    assigned_to_parent_id = Column(String(36), nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)


class TuckshopTransaction(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    Tuckshop (school canteen) purchase tracking.
    
    For schools that want to track tuckshop purchases and allow
    parents to pay via the payments portal.
    """
    __tablename__ = "tuckshop_transactions"

    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(36), nullable=False, index=True)
    
    # Transaction details
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    items = Column(JSON, default=list)  # [{item: "lunch", quantity: 1, price: 500}, ...]
    
    # Totals
    total_amount = Column(Numeric(15, 2), nullable=False)
    paid_amount = Column(Numeric(15, 2), nullable=False, default=0)
    outstanding = Column(Numeric(15, 2), nullable=False, default=0)
    
    # Status
    payment_status = Column(String(50), default="unpaid")  # unpaid, partial, paid
    
    # Related payment
    payment_transaction_id = Column(String(36), ForeignKey("payment_transactions.id"), nullable=True)


class SubscriptionInvoice(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    Invoice generation for subscription upgrades and renewals.
    """
    __tablename__ = "subscription_invoices"

    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Invoice identification
    invoice_number = Column(String(50), nullable=False, unique=True, index=True)
    reference = Column(String(255), nullable=True)  # Payment reference
    
    # What's being charged
    subscription_tier = Column(String(50), nullable=False)
    billing_type = Column(String(50), nullable=False)  # "upgrade", "renewal", "addon"
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    
    # Financial details
    subtotal = Column(Numeric(15, 2), nullable=False)
    tax = Column(Numeric(15, 2), nullable=False, default=0)
    discount = Column(Numeric(15, 2), nullable=False, default=0)
    total_amount = Column(Numeric(15, 2), nullable=False)
    
    # Payment status
    payment_status = Column(String(50), default="unpaid")  # unpaid, paid, refunded
    payment_date = Column(DateTime(timezone=True), nullable=True)
    payment_transaction_id = Column(String(36), ForeignKey("payment_transactions.id"), nullable=True)
    
    # Tracking
    issued_at = Column(DateTime(timezone=True), nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)
    notes = Column(Text, nullable=True)
