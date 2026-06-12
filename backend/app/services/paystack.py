"""
Paystack billing provider.

Implements the `BillingProvider` Protocol defined in services/billing.py
plus payment-verification helpers Paystack-specific code needs.

Talks to Paystack over httpx (already a runtime dep). Keys come from
settings and are injected at construction so this class remains
unit-testable without touching env. We never read settings inside a
method body — the adapter is a pure function of its constructor args.

Money model
-----------
Paystack works in kobo (NGN × 100). The adapter converts exactly once,
at the boundary: every internal amount stays in NGN. Plan prices live
in core/plans.py as `monthly_price_ngn` so tier → price is a single
dict lookup and never travels over the wire from the client.

Security
--------
- Amounts and target tiers are derived server-side from the org's
  requested upgrade. Clients cannot influence the amount.
- Webhook signatures are verified with HMAC-SHA512 against the secret
  key before any state mutation.
- Verify calls hit Paystack directly; we never trust the callback URL
  alone to indicate success (the redirect can be forged).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.core.plans import plan_for
from app.models.organization import SubscriptionTier
from app.services.billing import CheckoutSession


_logger = logging.getLogger("extracare.paystack")


@dataclass
class PaystackError(Exception):
    """Raised when Paystack returns a non-success envelope. Carries the
    upstream message so callers can surface it (optionally) to admins."""

    message: str
    status_code: int = 502

    def __str__(self) -> str:
        return self.message


def _kobo(amount_ngn: int | Decimal) -> int:
    try:
        amount = Decimal(amount_ngn)
    except (TypeError, InvalidOperation) as exc:
        raise ValueError("Amount must be a numeric value.") from exc

    if amount < 0:
        raise ValueError("Amount must be non-negative.")

    # Paystack requires an integer amount in kobo. Validate 2 decimal places.
    try:
        amount = amount.quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError("Amount must have at most two decimal places.") from exc

    return int(amount * 100)


def _reference() -> str:
    # Paystack accepts any unique string. A URL-safe token is enough —
    # we prefix with `ec_` so rows are recognisable in Paystack's
    # dashboard next to non-ExtraCare traffic.
    return f"ec_{secrets.token_urlsafe(16)}"


class PaystackProvider:
    """Concrete `BillingProvider`. Wire via set_billing_provider(...)
    at startup when PAYSTACK_SECRET_KEY is configured."""

    name = "paystack"

    def __init__(
        self,
        *,
        secret_key: str,
        public_key: str = "",
        api_url: str = "https://api.paystack.co",
        callback_url: str = "",
        http_client: httpx.AsyncClient | None = None,
    ):
        if not secret_key:
            raise ValueError("PaystackProvider requires a secret_key.")
        self._secret_key = secret_key
        self.public_key = public_key
        self._api_url = api_url.rstrip("/")
        self._callback_url = callback_url
        # Allow tests to inject a stubbed client. When None we build one
        # lazily per call so the adapter stays stateless at rest.
        self._http_client = http_client

    # ── Internals ────────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._secret_key}",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self._api_url}{path}"
        client = self._http_client or httpx.AsyncClient(timeout=20.0)
        try:
            resp = await client.request(method, url, headers=self._headers(), **kwargs)
        finally:
            if self._http_client is None:
                await client.aclose()

        if resp.status_code >= 500:
            raise PaystackError(
                message=f"Paystack returned {resp.status_code}.",
                status_code=502,
            )
        try:
            body = resp.json()
        except Exception as exc:
            raise PaystackError(message=f"Paystack returned non-JSON body: {exc}") from exc

        if not isinstance(body, dict) or not body.get("status"):
            # Paystack envelope: {status: bool, message: str, data: ...}.
            # status=false means the call reached the API but the action
            # was rejected (bad amount, duplicate reference, etc.).
            msg = (body or {}).get("message", "Paystack rejected the request.")
            raise PaystackError(message=msg, status_code=400)

        data = body.get("data")
        return data if isinstance(data, dict) else {"_raw": data}

    # ── BillingProvider surface ──────────────────────────────────────────

    async def create_checkout(
        self,
        *,
        org_id: str,
        target_tier: SubscriptionTier,
        return_url: str,
    ) -> CheckoutSession:
        """Initialize a Paystack transaction and return the checkout URL.

        Note: `return_url` here is the *caller's* override; if empty we
        fall back to the configured PAYSTACK_CALLBACK_URL so the frontend
        lands on a known route where /payments/verify fires.
        """
        plan = plan_for(target_tier)
        if plan.monthly_price_ngn <= 0:
            raise PaystackError(
                message=f"Plan {target_tier.value!r} is not available for checkout.",
                status_code=400,
            )
        # Email is required by Paystack. Callers pass it via kwargs once
        # we wire `initialize_transaction` below; create_checkout stays
        # spec-compatible by building a minimal payload.
        raise PaystackError(
            message="Use initialize_transaction(...) — create_checkout is kept for protocol parity only.",
            status_code=500,
        )

    async def cancel_subscription(self, *, org_id: str) -> None:
        # Paystack subscriptions are managed outside our scope today —
        # we only charge one-off transactions to upgrade tiers. A full
        # recurring-billing integration is a separate piece of work.
        return None

    # ── Paystack-specific API ────────────────────────────────────────────

    async def initialize_transaction(
        self,
        *,
        email: str,
        amount_ngn: int,
        org_id: str,
        target_tier: SubscriptionTier,
        callback_url: str | None = None,
        reference: str | None = None,
    ) -> dict[str, Any]:
        """POST /transaction/initialize.

        Returns Paystack's data envelope verbatim (`authorization_url`,
        `access_code`, `reference`). The caller hands the URL to the
        browser; the browser returns to `callback_url?reference=...`.

        Amount is fixed server-side: we derive kobo from `amount_ngn`
        which the router computed from `target_tier` via plan_for(...).
        Clients never supply the amount.
        """
        if amount_ngn <= 0:
            raise PaystackError(message="Amount must be positive.", status_code=400)
        payload = {
            "email": email,
            "amount": _kobo(amount_ngn),
            "reference": reference or _reference(),
            "callback_url": callback_url or self._callback_url,
            # metadata is echoed back in /verify and in webhooks —
            # keeps tier/org pinning tamper-evident without us storing
            # an extra pending-subscription row.
            "metadata": {
                "org_id": org_id,
                "target_tier": target_tier.value,
            },
        }
        data = await self._request("POST", "/transaction/initialize", json=payload)
        _logger.info(
            "paystack.init org=%s tier=%s ref=%s",
            org_id, target_tier.value, payload["reference"],
        )
        return data

    async def initialize_payment(
        self,
        *,
        email: str,
        amount_ngn: int,
        org_id: str,
        metadata: dict | None = None,
        callback_url: str | None = None,
        reference: str | None = None,
    ) -> dict[str, Any]:
        """Generic /transaction/initialize for non-subscription payments.

        Accepts arbitrary metadata which is echoed back in verification
        and webhooks. Returns Paystack's initialization payload including
        `authorization_url` and `reference`.
        """
        if amount_ngn <= 0:
            raise PaystackError(message="Amount must be positive.", status_code=400)
        payload = {
            "email": email,
            "amount": _kobo(amount_ngn),
            "reference": reference or _reference(),
            "callback_url": callback_url or self._callback_url,
            "metadata": metadata or {"org_id": org_id},
        }
        data = await self._request("POST", "/transaction/initialize", json=payload)
        _logger.info(
            "paystack.init_generic org=%s ref=%s",
            org_id, payload["reference"],
        )
        return data

    async def verify_transaction(self, reference: str) -> dict[str, Any]:
        """GET /transaction/verify/{reference}.

        Paystack returns the full transaction record; the router checks
        `status == "success"` and matches `metadata.org_id` / tier
        before granting any upgrade."""
        if not reference or not reference.strip():
            raise PaystackError(message="Reference required.", status_code=400)
        data = await self._request("GET", f"/transaction/verify/{reference}")
        _logger.info(
            "paystack.verify ref=%s status=%s",
            reference, data.get("status"),
        )
        return data

    # ── Webhooks ─────────────────────────────────────────────────────────

    def webhook_signature_valid(self, raw_body: bytes, signature: str) -> bool:
        """Paystack signs webhook bodies with HMAC-SHA512 of the raw
        request body, using the secret key. Compare with constant-time
        equality so we don't leak signature bytes via timing."""
        if not signature:
            return False
        expected = hmac.new(
            self._secret_key.encode("utf-8"),
            raw_body,
            hashlib.sha512,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
