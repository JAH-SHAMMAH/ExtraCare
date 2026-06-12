"""Add payment infrastructure and branding fields

Revision ID: 001_add_payment_infrastructure
Revises: 5cd65d550812
Create Date: 2026-05-22 00:00:00.000000

This migration adds:
- Payment infrastructure tables (tenant settings, transactions, audits)
- Student fee and tuckshop transaction tracking
- Subscription invoice management
- Organization branding fields
- Preserves all existing data (non-destructive)
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers used by Alembic
revision = "001_add_payment_infrastructure"
down_revision = "5cd65d550812"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema."""
    
    # 1. Add branding fields to organizations
    op.add_column("organizations", sa.Column("favicon_url", sa.String(500), nullable=True))
    op.add_column("organizations", sa.Column("secondary_color", sa.String(7), server_default="#f0fdf4"))
    op.add_column("organizations", sa.Column("branding_settings", sa.JSON(), server_default=sa.text("'{}'"), nullable=True))
    
    # Update primary_color default from blue to green
    op.execute("UPDATE organizations SET primary_color = '#16a34a' WHERE primary_color = '#0057c2'")
    op.alter_column("organizations", "primary_color", server_default="#16a34a")

    # 2. Create tenant_payment_settings table
    op.create_table(
        "tenant_payment_settings",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("provider", sa.Enum("paystack", "flutterwave", "stripe", "bank_transfer", name="paymentprovider"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("encrypted_secret_key", sa.Text(), nullable=True),
        sa.Column("encrypted_public_key", sa.Text(), nullable=True),
        sa.Column("encrypted_webhook_secret", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("settlement_account", sa.String(255), nullable=True),
        sa.Column("settlement_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("webhook_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("webhook_url", sa.String(500), nullable=True),
        sa.Column("webhook_last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("verification_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("daily_limit", sa.Numeric(15, 2), nullable=True),
        sa.Column("transaction_limit", sa.Numeric(15, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("configured_by_user_id", sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_tenant_payment_settings_org_id", "org_id"),
        sa.Index("ix_tenant_payment_settings_provider", "provider"),
        sa.Index("ix_tenant_payment_settings_is_active", "is_active"),
    )

    # 3. Create payment_transactions table
    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("payment_settings_id", sa.String(36), nullable=False),
        sa.Column("reference", sa.String(255), nullable=False),
        sa.Column("provider_reference", sa.String(255), nullable=True),
        sa.Column("payment_type", sa.Enum("school_fees", "tuckshop", "subscription", "plan_upgrade", "other", name="paymenttype"), nullable=False),
        sa.Column("status", sa.Enum("pending", "processing", "successful", "failed", "cancelled", "refunded", name="paymentstatus"), server_default="pending", nullable=False),
        sa.Column("provider", sa.Enum("paystack", "flutterwave", "stripe", "bank_transfer", name="paymentprovider"), nullable=False),
        sa.Column("amount_ngn", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="NGN"),
        sa.Column("fee_ngn", sa.Numeric(15, 2), nullable=True),
        sa.Column("net_amount_ngn", sa.Numeric(15, 2), nullable=True),
        sa.Column("student_id", sa.String(36), nullable=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("related_id", sa.String(36), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("metadata", sa.JSON(), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("last_4_digits", sa.String(4), nullable=True),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("authorization_url", sa.String(500), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_code", sa.String(255), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciled_by_user_id", sa.String(36), nullable=True),
        sa.Column("reconciliation_notes", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_response", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_settings_id"], ["tenant_payment_settings.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_payment_transactions_org_id", "org_id"),
        sa.Index("ix_payment_transactions_reference", "reference", unique=True),
        sa.Index("ix_payment_transactions_provider_reference", "provider_reference"),
        sa.Index("ix_payment_transactions_status", "status"),
        sa.Index("ix_payment_transactions_student_id", "student_id"),
        sa.Index("ix_payment_transactions_payment_type", "payment_type"),
    )

    # 4. Create payment_audits table
    op.create_table(
        "payment_audits",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("transaction_id", sa.String(36), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("action_by_user_id", sa.String(36), nullable=True),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transaction_id"], ["payment_transactions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["action_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_payment_audits_org_id", "org_id"),
        sa.Index("ix_payment_audits_transaction_id", "transaction_id"),
    )

    # 5. Create student_fee_records table
    op.create_table(
        "student_fee_records",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("term", sa.String(50), nullable=False),
        sa.Column("session_year", sa.String(10), nullable=False),
        sa.Column("tuition_fee", sa.Numeric(15, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("exam_fee", sa.Numeric(15, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("activity_fee", sa.Numeric(15, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("transport_fee", sa.Numeric(15, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("hostel_fee", sa.Numeric(15, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("other_fees", sa.Numeric(15, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("total_fee", sa.Numeric(15, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("paid_amount", sa.Numeric(15, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("outstanding_balance", sa.Numeric(15, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_paid", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("payment_status", sa.String(50), server_default="unpaid"),
        sa.Column("discount_amount", sa.Numeric(15, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("discount_reason", sa.String(255), nullable=True),
        sa.Column("assigned_to_parent_id", sa.String(36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_student_fee_records_org_id", "org_id"),
        sa.Index("ix_student_fee_records_student_id", "student_id"),
        sa.Index("ix_student_fee_records_is_paid", "is_paid"),
    )

    # 6. Create tuckshop_transactions table
    op.create_table(
        "tuckshop_transactions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("items", sa.JSON(), server_default=sa.text("'[]'")),
        sa.Column("total_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("paid_amount", sa.Numeric(15, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("outstanding", sa.Numeric(15, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("payment_status", sa.String(50), server_default="unpaid"),
        sa.Column("payment_transaction_id", sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_transaction_id"], ["payment_transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_tuckshop_transactions_org_id", "org_id"),
        sa.Index("ix_tuckshop_transactions_student_id", "student_id"),
    )

    # 7. Create subscription_invoices table
    op.create_table(
        "subscription_invoices",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("subscription_tier", sa.String(50), nullable=False),
        sa.Column("billing_type", sa.String(50), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subtotal", sa.Numeric(15, 2), nullable=False),
        sa.Column("tax", sa.Numeric(15, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("discount", sa.Numeric(15, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("total_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("payment_status", sa.String(50), server_default="unpaid"),
        sa.Column("payment_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_transaction_id", sa.String(36), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_transaction_id"], ["payment_transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_subscription_invoices_org_id", "org_id"),
        sa.Index("ix_subscription_invoices_invoice_number", "invoice_number", unique=True),
    )


def downgrade() -> None:
    """Downgrade database schema (rollback)."""
    # Drop tables in reverse order of creation
    op.drop_table("subscription_invoices")
    op.drop_table("tuckshop_transactions")
    op.drop_table("student_fee_records")
    op.drop_table("payment_audits")
    op.drop_table("payment_transactions")
    op.drop_table("tenant_payment_settings")
    
    # Remove branding columns
    op.drop_column("organizations", "branding_settings")
    op.drop_column("organizations", "secondary_color")
    op.drop_column("organizations", "favicon_url")
    
    # Revert primary_color to original blue
    op.alter_column("organizations", "primary_color", server_default="#0057c2")
    op.execute("UPDATE organizations SET primary_color = '#0057c2' WHERE primary_color = '#16a34a'")
