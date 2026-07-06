"""Flutterwave provider (parent fee payments) — Standard Checkout, API v3.

Mirrors the PaystackProvider surface the fee flow consumes, so it slots into the
same `resolve_for_org` factory + school-payments initiate/verify path:
  • initialize_payment() — POST /v3/payments → hosted checkout `link` + our tx_ref.
  • verify_transaction() — GET /v3/transactions/verify_by_reference → normalised
    `{status, id, metadata, amount}` (status "success" when Flutterwave says
    "successful"), so the caller reads the same fields it does for Paystack.
  • webhook_signature_valid() — Flutterwave sends the *secret hash you set* verbatim
    in the `verif-hash` header; verification is a constant-time equality check.

Keys are injected at construction (per-org, decrypted upstream) — the adapter never
reads settings inside a method body, so it stays unit-testable and can be pointed at
a stub. TEST vs LIVE is selected by the key PREFIX (FLWSECK_TEST- vs FLWSECK-), not a
different host.
"""
from __future__ import annotations

import hmac
import logging
import secrets
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx


_logger = logging.getLogger("extracare.flutterwave")


@dataclass
class FlutterwaveError(Exception):
    """Raised when Flutterwave returns a non-success envelope."""
    message: str
    status_code: int = 502

    def __str__(self) -> str:
        return self.message


def _reference() -> str:
    return f"ec_{secrets.token_urlsafe(16)}"


class FlutterwaveProvider:
    name = "flutterwave"

    def __init__(
        self,
        *,
        secret_key: str,
        base_url: str = "https://api.flutterwave.com",
        callback_url: str = "",
        http_client: httpx.AsyncClient | None = None,
    ):
        if not secret_key:
            raise ValueError("FlutterwaveProvider requires a secret_key.")
        self._secret_key = secret_key
        self._base_url = base_url.rstrip("/")
        self._callback_url = callback_url
        self._http_client = http_client

    # ── Internals ────────────────────────────────────────────────────────
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._secret_key}", "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        client = self._http_client or httpx.AsyncClient(timeout=20.0)
        try:
            resp = await client.request(method, url, headers=self._headers(), **kwargs)
        finally:
            if self._http_client is None:
                await client.aclose()

        if resp.status_code >= 500:
            raise FlutterwaveError(f"Flutterwave returned {resp.status_code}.", status_code=502)
        try:
            body = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise FlutterwaveError(f"Flutterwave returned non-JSON body: {exc}") from exc

        # Flutterwave envelope: {status: "success"|"error", message, data}.
        if not isinstance(body, dict) or body.get("status") != "success":
            msg = (body or {}).get("message", "Flutterwave rejected the request.")
            raise FlutterwaveError(msg, status_code=400)
        return body

    # ── Fee-flow surface (matches PaystackProvider) ──────────────────────
    async def initialize_payment(
        self,
        *,
        email: str,
        amount_ngn: int | Decimal,
        org_id: str,
        metadata: dict | None = None,
        callback_url: str | None = None,
        reference: str | None = None,
    ) -> dict[str, Any]:
        """POST /v3/payments → hosted checkout link. Flutterwave works in whole
        naira (NOT kobo). Returns `{authorization_url, reference}` for the caller."""
        amount = Decimal(amount_ngn)
        if amount <= 0:
            raise FlutterwaveError("Amount must be positive.", status_code=400)
        tx_ref = reference or _reference()
        payload = {
            "tx_ref": tx_ref,
            "amount": str(amount),                 # whole naira
            "currency": "NGN",
            "redirect_url": callback_url or self._callback_url,
            "customer": {"email": email},
            "meta": metadata or {"org_id": org_id},
            "payment_options": "card,banktransfer,ussd,account",
            "customizations": {"title": "School Fees"},
        }
        body = await self._request("POST", "/v3/payments", json=payload)
        link = (body.get("data") or {}).get("link")
        if not link:
            raise FlutterwaveError("Flutterwave did not return a checkout link.", status_code=502)
        _logger.info("flutterwave.init org=%s tx_ref=%s", org_id, tx_ref)
        # Normalise to the shape school_payments reads (authorization_url + reference).
        return {"authorization_url": link, "reference": tx_ref, "data": {"authorization_url": link, "reference": tx_ref}, "_raw": body}

    async def verify_transaction(self, reference: str) -> dict[str, Any]:
        """GET /v3/transactions/verify_by_reference?tx_ref=… → normalised status.

        Flutterwave's success value is "successful"; we map it to "success" so the
        caller's `status == "success"` check is provider-agnostic. Metadata comes
        back under `meta`; we surface it as `metadata`."""
        if not reference or not reference.strip():
            raise FlutterwaveError("Reference required.", status_code=400)
        body = await self._request("GET", "/v3/transactions/verify_by_reference", params={"tx_ref": reference})
        data = body.get("data") or {}
        raw_status = str(data.get("status") or "").lower()
        _logger.info("flutterwave.verify tx_ref=%s status=%s", reference, raw_status)
        return {
            "status": "success" if raw_status == "successful" else (raw_status or "failed"),
            "id": data.get("id"),
            "metadata": data.get("meta") or {},
            "amount": data.get("amount"),
            "currency": data.get("currency"),
            "flw_ref": data.get("flw_ref"),
            "_raw": body,
        }

    # ── Webhook ──────────────────────────────────────────────────────────
    @staticmethod
    def webhook_signature_valid(verif_hash_header: str | None, secret_hash: str | None) -> bool:
        """Flutterwave posts the *secret hash you configured* verbatim in the
        `verif-hash` header (it is NOT an HMAC of the body). Reject when either side
        is missing; compare constant-time. Static so the webhook route can verify
        without needing the API secret key."""
        if not verif_hash_header or not secret_hash:
            return False
        return hmac.compare_digest(str(verif_hash_header), str(secret_hash))
