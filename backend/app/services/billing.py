"""
Billing provider abstraction.

Deliberately minimal — the production path will be one of Stripe or
Paystack, but we don't want guard code scattered with provider-specific
branches. Every call site depends on `BillingProvider`, and we swap the
implementation at startup based on config.

Today only `NoopBillingProvider` is wired. When a real adapter lands
(e.g. PaystackAdapter) it implements this same interface and
`get_billing_provider()` returns it instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.models.organization import SubscriptionTier


@dataclass(frozen=True)
class CheckoutSession:
    url: str
    provider_reference: str


class BillingProvider(Protocol):
    """What every concrete provider must implement. Kept narrow — more
    surface gets added only when a route actually needs it, to avoid
    shipping dead interface methods."""

    name: str

    async def create_checkout(self, *, org_id: str, target_tier: SubscriptionTier, return_url: str) -> CheckoutSession:
        ...

    async def cancel_subscription(self, *, org_id: str) -> None:
        ...


class NoopBillingProvider:
    """Null implementation. `create_checkout` returns a synthetic URL so
    the frontend checkout flow is exercisable in dev without a live
    payment integration. Never wire this in production."""

    name = "noop"

    async def create_checkout(self, *, org_id: str, target_tier: SubscriptionTier, return_url: str) -> CheckoutSession:
        return CheckoutSession(
            url=f"{return_url}?simulated=true&tier={target_tier.value}&org={org_id}",
            provider_reference=f"noop_{org_id}_{target_tier.value}",
        )

    async def cancel_subscription(self, *, org_id: str) -> None:
        return None


_provider: BillingProvider = NoopBillingProvider()


def get_billing_provider() -> BillingProvider:
    return _provider


def set_billing_provider(provider: BillingProvider) -> None:
    """Used by app startup (and tests) to swap the active provider."""
    global _provider
    _provider = provider
