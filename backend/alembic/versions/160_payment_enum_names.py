"""Add the enum NAMES the payment models write to the Postgres payment enums.

Migration 001 created `paymentprovider`, `paymenttype` and `paymentstatus` with
lower-case VALUES ('paystack', 'pending', ...). SQLAlchemy's Enum(PaymentProvider)
writes/filters on the member NAMES ('PAYSTACK', 'PENDING', ...), so on Postgres every
query on those columns failed with "invalid input value for enum paymentprovider:
'PAYSTACK'" -- saving a gateway key and every parent card payment 503'd (tests pass
because SQLite rebuilds the enum from the model). `remita` was never in the type.

Same fix as 096 (auditaction): add the missing names. Add-only + IF NOT EXISTS, so
safe to re-run; Postgres only.

Revision ID: 160_payment_enum_names
Revises: 159_backfill_fee_record_payments
"""
from alembic import op

revision = "160_payment_enum_names"
down_revision = "159_backfill_fee_record_payments"
branch_labels = None
depends_on = None

_TYPES = {
    "paymentprovider": ["PAYSTACK", "REMITA", "FLUTTERWAVE", "STRIPE", "BANK_TRANSFER"],
    "paymenttype": ["SCHOOL_FEES", "TUCKSHOP", "SUBSCRIPTION", "PLAN_UPGRADE", "OTHER"],
    "paymentstatus": ["PENDING", "PROCESSING", "SUCCESSFUL", "FAILED", "CANCELLED", "REFUNDED"],
}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        for typ, names in _TYPES.items():
            for n in names:
                op.execute(f"ALTER TYPE {typ} ADD VALUE IF NOT EXISTS '{n}'")


def downgrade() -> None:
    pass
