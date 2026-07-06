"""Remita Standard Ingestion client (parent fee payments).

Implements the two server-to-server calls of Remita's documented flow:
  • generate_rrr() — POST paymentinit → returns an RRR for an order.
  • query_status() — GET status.reg → payment status for an RRR.

Auth is a SHA-512 hash of ordered fields + the API key (Remita's scheme). Ships
pointed at the PUBLIC demo host via config; set REMITA_BASE_URL + live Merchant
ID / API Key / Service Type ID env vars to go live. Every call is best-effort and
returns a dict with an ``error`` key on failure — it never raises, so callers can
record a failed attempt rather than 500.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.payment import TenantPaymentSettings, PaymentProvider
from app.services import crypto
from app.services.payment_resolver import PaymentConfigError

logger = logging.getLogger("extracare.remita")

_INIT_PATH = "/remita/exapp/api/v1/send/api/echannelsvc/merchant/api/paymentinit"
_STATUS_PATH = "/remita/exapp/api/v1/send/api/echannelsvc/{merchant}/{rrr}/{hash}/status.reg"


@dataclass(frozen=True)
class RemitaCredentials:
    """The 3-part Remita credential (+ host). Unlike Paystack's single secret,
    Remita needs a merchant id + service-type id + API key. Callers get these from
    :func:`resolve_credentials` (per-org config, or env fallback) — never globals."""
    merchant_id: str
    service_type_id: str
    api_key: str
    base_url: str


def env_credentials() -> RemitaCredentials:
    """Deployment-level Remita creds from settings (the pre-per-org default)."""
    s = get_settings()
    return RemitaCredentials(
        merchant_id=s.REMITA_MERCHANT_ID, service_type_id=s.REMITA_SERVICE_TYPE_ID,
        api_key=s.REMITA_API_KEY, base_url=s.REMITA_BASE_URL,
    )


async def resolve_credentials(db: AsyncSession, org_id: str) -> RemitaCredentials:
    """The org's OWN Remita credentials if configured (via the Payment Gateways UI),
    else the env defaults. The API key is stored encrypted
    (``TenantPaymentSettings.encrypted_secret_key``); merchant id / service-type id /
    base url live in ``metadata``. Fail loud (``PaymentConfigError``) if a config
    exists but the API key can't be decrypted — never silently fall back to the
    platform account (that would settle a school's fees to the wrong merchant)."""
    row = (await db.execute(
        select(TenantPaymentSettings).where(
            TenantPaymentSettings.org_id == org_id,
            TenantPaymentSettings.provider == PaymentProvider.REMITA,
            TenantPaymentSettings.is_active == True,   # noqa: E712
            TenantPaymentSettings.is_deleted == False,  # noqa: E712
        ).order_by(TenantPaymentSettings.created_at.desc())
    )).scalars().first()
    env = env_credentials()
    if row and row.encrypted_secret_key:
        try:
            api_key = crypto.decrypt(row.encrypted_secret_key)
        except Exception as exc:  # noqa: BLE001
            logger.error("remita.resolve.decrypt_failed org=%s err=%s", org_id, exc)
            raise PaymentConfigError(
                f"Remita API key for organization {org_id} could not be decrypted "
                "(encryption key missing or rotated). Fix the key or re-enter the gateway secret."
            ) from exc
        md = row.metadata_ or {}
        return RemitaCredentials(
            merchant_id=md.get("merchant_id") or env.merchant_id,
            service_type_id=md.get("service_type_id") or env.service_type_id,
            api_key=api_key,
            base_url=md.get("base_url") or env.base_url,
        )
    return env


def _sha512(*parts: str) -> str:
    return hashlib.sha512("".join(parts).encode()).hexdigest()


def _unwrap_jsonp(text: str) -> dict:
    """Remita wraps responses as ``jsonp_xxx({...})``. Extract the JSON object."""
    text = (text or "").strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"unexpected response: {text[:200]}")
    return json.loads(m.group(0))


async def generate_rrr(*, creds: RemitaCredentials, order_id: str, amount: float, payer_name: str,
                       payer_email: str, payer_phone: str = "", description: str = "School fees") -> dict:
    api_hash = _sha512(creds.merchant_id, creds.service_type_id, order_id, f"{amount:.2f}", creds.api_key)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"remitaConsumerKey={creds.merchant_id},remitaConsumerToken={api_hash}",
    }
    body = {
        "serviceTypeId": creds.service_type_id,
        "amount": f"{amount:.2f}",
        "orderId": order_id,
        "payerName": payer_name,
        "payerEmail": payer_email,
        "payerPhone": payer_phone or "08000000000",
        "description": description,
    }
    url = f"{creds.base_url}{_INIT_PATH}"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, headers=headers, json=body)
        data = _unwrap_jsonp(resp.text)
        logger.info("remita.init order=%s status=%s rrr=%s", order_id, data.get("statuscode"), data.get("RRR"))
        return data
    except Exception as exc:  # noqa: BLE001 — never break the request
        logger.error("remita.init.failed order=%s error=%s", order_id, exc)
        return {"error": str(exc)}


async def query_status(rrr: str, *, creds: RemitaCredentials) -> dict:
    api_hash = _sha512(rrr, creds.api_key, creds.merchant_id)
    url = f"{creds.base_url}{_STATUS_PATH.format(merchant=creds.merchant_id, rrr=rrr, hash=api_hash)}"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers={"Content-Type": "application/json"})
        data = _unwrap_jsonp(resp.text)
        logger.info("remita.status rrr=%s status=%s", rrr, data.get("status"))
        return data
    except Exception as exc:  # noqa: BLE001
        logger.error("remita.status.failed rrr=%s error=%s", rrr, exc)
        return {"error": str(exc)}


# ┌─ GO-LIVE CHECKLIST (3 of 3) ─────────────────────────────────────────────────┐
# │ CONFIRM these success status codes against YOUR Remita account the moment    │
# │ live credentials are available. Remita Standard Ingestion documents "00" =   │
# │ "Approved/Successful" and "01" = "Transaction Successful (paid)", but code    │
# │ sets vary by integration/account — verify with a real test payment before    │
# │ trusting an invoice as settled. (is_paid() is the single place this is read.) │
# └───────────────────────────────────────────────────────────────────────────────┘
PAID_STATUS_CODES = {"00", "01"}


def is_paid(status_response: dict) -> bool:
    return str(status_response.get("status") or status_response.get("statuscode") or "") in PAID_STATUS_CODES
