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

import httpx

from app.config import get_settings

logger = logging.getLogger("extracare.remita")

_INIT_PATH = "/remita/exapp/api/v1/send/api/echannelsvc/merchant/api/paymentinit"
_STATUS_PATH = "/remita/exapp/api/v1/send/api/echannelsvc/{merchant}/{rrr}/{hash}/status.reg"


def _sha512(*parts: str) -> str:
    return hashlib.sha512("".join(parts).encode()).hexdigest()


def _unwrap_jsonp(text: str) -> dict:
    """Remita wraps responses as ``jsonp_xxx({...})``. Extract the JSON object."""
    text = (text or "").strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"unexpected response: {text[:200]}")
    return json.loads(m.group(0))


async def generate_rrr(*, order_id: str, amount: float, payer_name: str, payer_email: str,
                       payer_phone: str = "", description: str = "School fees") -> dict:
    s = get_settings()
    api_hash = _sha512(s.REMITA_MERCHANT_ID, s.REMITA_SERVICE_TYPE_ID, order_id, f"{amount:.2f}", s.REMITA_API_KEY)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"remitaConsumerKey={s.REMITA_MERCHANT_ID},remitaConsumerToken={api_hash}",
    }
    body = {
        "serviceTypeId": s.REMITA_SERVICE_TYPE_ID,
        "amount": f"{amount:.2f}",
        "orderId": order_id,
        "payerName": payer_name,
        "payerEmail": payer_email,
        "payerPhone": payer_phone or "08000000000",
        "description": description,
    }
    url = f"{s.REMITA_BASE_URL}{_INIT_PATH}"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, headers=headers, json=body)
        data = _unwrap_jsonp(resp.text)
        logger.info("remita.init order=%s status=%s rrr=%s", order_id, data.get("statuscode"), data.get("RRR"))
        return data
    except Exception as exc:  # noqa: BLE001 — never break the request
        logger.error("remita.init.failed order=%s error=%s", order_id, exc)
        return {"error": str(exc)}


async def query_status(rrr: str) -> dict:
    s = get_settings()
    api_hash = _sha512(rrr, s.REMITA_API_KEY, s.REMITA_MERCHANT_ID)
    url = f"{s.REMITA_BASE_URL}{_STATUS_PATH.format(merchant=s.REMITA_MERCHANT_ID, rrr=rrr, hash=api_hash)}"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers={"Content-Type": "application/json"})
        data = _unwrap_jsonp(resp.text)
        logger.info("remita.status rrr=%s status=%s", rrr, data.get("status"))
        return data
    except Exception as exc:  # noqa: BLE001
        logger.error("remita.status.failed rrr=%s error=%s", rrr, exc)
        return {"error": str(exc)}


# ┌─ GO-LIVE CHECKLIST (2 of 2) ─────────────────────────────────────────────────┐
# │ CONFIRM these success status codes against YOUR Remita account the moment    │
# │ live credentials are available. Remita Standard Ingestion documents "00" =   │
# │ "Approved/Successful" and "01" = "Transaction Successful (paid)", but code    │
# │ sets vary by integration/account — verify with a real test payment before    │
# │ trusting an invoice as settled. (is_paid() is the single place this is read.) │
# └───────────────────────────────────────────────────────────────────────────────┘
PAID_STATUS_CODES = {"00", "01"}


def is_paid(status_response: dict) -> bool:
    return str(status_response.get("status") or status_response.get("statuscode") or "") in PAID_STATUS_CODES
