"""Student Wallet / PocketMoney + Cooperative models (Batch 6 money features).

Real student money, ledger-backed. Balances are NEVER stored — they are derived
by summing the subledger (``WalletEntry`` / ``CoopEntry``) over journal entries
that have not been reversed, and the aggregate liability control account in the
GL reconciles to the sum of all sub-balances.

  • StudentWallet      — per-student wallet identity + spend controls (PocketMoney
                          is the SAME wallet: a daily spend limit + the spend path).
  • WalletEntry        — subledger: +top-up / −spend / −withdrawal, linked to its GL entry.
  • CooperativeMember  — a cooperative member (funds held on their behalf = liability).
  • CoopEntry          — subledger: +contribution / −payout.

Top-up/withdrawal and cooperative cash-in/out post Dr/Cr **Cash ↔ liability** (no
income). A spend is the only moment income is recognised: Dr Wallet-Float / Cr
Income. All postings go through the shared ledger engine.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Date, Numeric, Boolean, ForeignKey, Index, UniqueConstraint

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class StudentWallet(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """One cashless account per student. Holds CONTROLS, not a balance."""
    __tablename__ = "student_wallets"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    spend_limit_daily = Column(Numeric(14, 2), nullable=True)   # PocketMoney control; None = unlimited
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "student_id", name="uq_student_wallets_org_student"),
        Index("ix_student_wallets_student_org", "student_id", "org_id"),
    )


class WalletSettings(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Per-org Wallet Manager configuration (Wallet Manager → Settings). One row
    per org. ``default_daily_limit`` is applied to a new wallet when the creator
    doesn't set one; ``low_balance_threshold`` flags wallets running low."""
    __tablename__ = "wallet_settings"

    default_daily_limit = Column(Numeric(14, 2), nullable=True)      # None = unlimited by default
    low_balance_threshold = Column(Numeric(14, 2), nullable=True)    # None = no low-balance flag
    notify_low_balance = Column(Boolean, default=False, nullable=False)
    allow_topup = Column(Boolean, default=True, nullable=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, unique=True, index=True)


class WalletEntry(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Wallet subledger row. ``signed_amount`` is + for top-up, − for spend /
    withdrawal. Balance = Σ signed_amount where the linked GL entry isn't reversed."""
    __tablename__ = "wallet_entries"

    wallet_id = Column(String(36), ForeignKey("student_wallets.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(20), nullable=False)              # top_up | spend | withdrawal
    signed_amount = Column(Numeric(14, 2), nullable=False)  # +/−
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    memo = Column(String(255), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_wallet_entries_student_org", "student_id", "org_id"),
        Index("ix_wallet_entries_wallet_org", "wallet_id", "org_id"),
    )


# ── Parent Wallet (family funding wallet — Wallet Manager) ──────────────────────
# A parent-level wallet keyed by the parent-role User. Distinct from StudentWallet
# (per-student PocketMoney): this is the family funding wallet a parent tops up and
# that pays their children's invoices. DVA / virtual-account funding is deferred to
# the Payment Gateways feature; today it funds via manual "Add Credit".

class ParentWallet(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """One funding wallet per parent (a parent-role User). Children are the
    students linked to that user via ParentGuardian. Holds no stored balance —
    balance is derived from ParentWalletEntry over non-reversed journal entries."""
    __tablename__ = "parent_wallets"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    # DVA / virtual-account fields intentionally omitted until Payment Gateways lands.

    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_parent_wallets_org_user"),
        Index("ix_parent_wallets_user_org", "user_id", "org_id"),
    )


class ParentWalletEntry(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Parent-wallet subledger. ``signed_amount`` + for credit (top-up), − for
    debit (invoice payment / manual debit). Balance = Σ over non-reversed entries."""
    __tablename__ = "parent_wallet_entries"

    wallet_id = Column(String(36), ForeignKey("parent_wallets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(20), nullable=False)              # credit | debit
    signed_amount = Column(Numeric(14, 2), nullable=False)  # +/−
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    memo = Column(String(255), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_parent_wallet_entries_wallet_org", "wallet_id", "org_id"),
        Index("ix_parent_wallet_entries_user_org", "user_id", "org_id"),
    )


class ParentWalletSettings(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Per-org Wallet Manager (parent wallet) configuration. Only the non-gateway
    settings are modelled; DVA/BVN/virtual-account gateway settings are deferred
    to the Payment Gateways feature."""
    __tablename__ = "parent_wallet_settings"

    auto_invoice_pay = Column(Boolean, default=False, nullable=False)   # auto-pay invoices from wallet balance
    correspondent_email = Column(String(320), nullable=True)           # receives wallet-credit notifications
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, unique=True, index=True)


class CooperativeMember(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A cooperative member. Their contributions are funds held on their behalf
    (a liability), not school income."""
    __tablename__ = "cooperative_members"

    member_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    member_name = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    joined_on = Column(Date, nullable=True)

    __table_args__ = (
        Index("ix_cooperative_members_org", "org_id"),
    )


class CoopEntry(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Cooperative subledger row. + contribution, − payout. Balance = Σ over
    non-reversed GL entries."""
    __tablename__ = "coop_entries"

    member_id = Column(String(36), ForeignKey("cooperative_members.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(20), nullable=False)              # contribution | payout
    signed_amount = Column(Numeric(14, 2), nullable=False)
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)
    memo = Column(String(255), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_coop_entries_member_org", "member_id", "org_id"),
    )
