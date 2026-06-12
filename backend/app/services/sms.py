"""
SMS provider abstraction (Phase 6.6).

Keep this layer dumb: the provider turns (phone, body, sender_id) into a
(accepted? provider_message_id? error?) tuple. Anything higher-level
(recipient resolution, counter updates, audit logs) lives in the router.

Providers are resolved by name through `get_provider(name)`. Default is
the mock — swapping to a real provider later is one line in settings plus
adding the subclass here.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SendResult:
    accepted: bool
    provider_message_id: str | None
    # Whether the provider confirmed *delivery* in addition to acceptance.
    # Real providers confirm delivery async via DLR webhooks; for the mock
    # we resolve the eventual status immediately so the demo can show
    # delivered/failed without a webhook loop.
    delivered: bool = False
    error_message: str | None = None


class SmsProvider(Protocol):
    name: str

    async def send(self, *, to: str, body: str, sender_id: str) -> SendResult: ...


class MockSmsProvider:
    """Deterministic in-process provider used for the demo.

    Rules (keep them obvious and tuneable):
      - "Accepted" → always true unless the phone fails basic validation.
      - "Delivered" → true for ~92% of recipients, false for ~8%. The hash of
        phone+body seeds the coin so the same message to the same phone always
        produces the same outcome — reruns look stable in screenshots.
      - Artificial delay stays under 50ms per message so a bulk send of
        dozens of recipients still completes inside a demo click.
    """

    name = "mock"

    # Fraction of messages that simulate a delivery failure.
    FAIL_RATE = 0.08

    async def send(self, *, to: str, body: str, sender_id: str) -> SendResult:
        phone = (to or "").strip()
        if not phone or not phone.startswith("+") or len(phone) < 8:
            return SendResult(
                accepted=False,
                provider_message_id=None,
                delivered=False,
                error_message="Invalid phone number",
            )

        # Deterministic failure pick — same (phone, body) always produces
        # the same outcome. Lets the demo be repeatable.
        digest = hashlib.sha1(f"{phone}|{body}".encode("utf-8")).hexdigest()
        bucket = int(digest[:4], 16) / 0xFFFF  # 0..1
        failed = bucket < self.FAIL_RATE

        # Small async yield so a large fan-out doesn't block the event loop.
        await asyncio.sleep(0.005)

        return SendResult(
            accepted=True,
            provider_message_id=f"mock_{uuid.uuid4().hex[:16]}",
            delivered=not failed,
            error_message="Handset unreachable" if failed else None,
        )


# Registry. Keyed by provider name (matches `SmsCampaign.provider`).
_PROVIDERS: dict[str, SmsProvider] = {
    "mock": MockSmsProvider(),
}


def get_provider(name: str | None = None) -> SmsProvider:
    """Resolve a provider by name. Falls back to the configured default
    (env `SMS_PROVIDER`, else `mock`) when `name` is None."""
    if name is None:
        name = os.getenv("SMS_PROVIDER", "mock")
    provider = _PROVIDERS.get(name)
    if not provider:
        # Unknown name means a misconfiguration — fail loudly rather than
        # silently falling back, so tests and ops see the error.
        raise ValueError(f"Unknown SMS provider: {name!r}. Registered: {sorted(_PROVIDERS)}")
    return provider


def list_providers() -> list[str]:
    return sorted(_PROVIDERS.keys())


# ── Utilities ────────────────────────────────────────────────────────────────


def estimate_sms_units(body: str) -> int:
    """How many 160-char SMS segments this message consumes.
    Admins are billed per unit, so the compose screen previews this."""
    n = len(body or "")
    if n == 0:
        return 0
    # Standard GSM: first segment 160 chars, subsequent 153 (7 chars overhead
    # for concatenation headers). Not GSM-alphabet-aware — good enough.
    if n <= 160:
        return 1
    return 1 + (n - 160 + 152) // 153


# Indicative price per SMS unit on Nigerian aggregators (Termii alphanumeric
# DND-allowed, mid-tier). Single source of truth — UI references this so it
# stays in sync with the actual billed rate when we plug in a real provider.
COST_PER_UNIT_NGN: float = 4.0


def estimate_sms_cost_ngn(body: str, recipient_count: int) -> float:
    """Total NGN cost for sending `body` to `recipient_count` recipients."""
    return round(estimate_sms_units(body) * COST_PER_UNIT_NGN * max(0, recipient_count), 2)


def default_sender_id(org_name: str | None) -> str:
    """Collapse an org name into a valid alphanumeric sender id — letters
    + digits only, max 11 chars (Termii/Africa's Talking hard cap)."""
    cleaned = "".join(ch for ch in (org_name or "ExtraCare") if ch.isalnum())
    return (cleaned or "ExtraCare")[:11].upper()


# ── Phone normalisation ──────────────────────────────────────────────────────

# Default country code applied when a phone number has no leading "+". Africa-
# first project, so Nigeria (+234) is the right default; configurable later
# via org setting if we ever need to.
_DEFAULT_COUNTRY_CODE = "234"


# ── Rate limit ───────────────────────────────────────────────────────────────
#
# Per-org sliding window. In-memory is fine for the demo (single process)
# and any real deployment will swap this for Redis without touching callers.
# We keep it deliberately small so a careless admin spamming "Send" sees
# the 429 — providers throttle at the same shape, so we surface it early.

import time as _time

_RATE_WINDOW_SEC = 60
_RATE_MAX_CAMPAIGNS = 5

_org_send_log: dict[str, list[float]] = {}


def check_rate_limit(org_id: str) -> tuple[bool, int]:
    """Returns (allowed, retry_after_seconds). When not allowed, the caller
    should return 429 with the retry hint so the UI can show a real
    'try again in N seconds' message."""
    now = _time.time()
    log = _org_send_log.setdefault(org_id, [])
    cutoff = now - _RATE_WINDOW_SEC
    # Trim entries that fell out of the window. List append+filter is O(N)
    # but N is tiny (a handful of recent sends per org).
    log[:] = [t for t in log if t > cutoff]
    if len(log) >= _RATE_MAX_CAMPAIGNS:
        oldest = log[0]
        retry_in = max(1, int(oldest + _RATE_WINDOW_SEC - now) + 1)
        return False, retry_in
    log.append(now)
    return True, 0


def normalise_phone_e164(raw: str | None) -> str | None:
    """Best-effort E.164 normaliser.

    Rules (simple by design — phonenumbers lib is overkill for the demo):
      - Strip spaces, dashes, parens, dots.
      - Already starts with "+" → keep verbatim if it's plausibly E.164.
      - Starts with "00" (international dialling prefix) → replace with "+".
      - Starts with "0" and has 10–11 digits → assume Nigerian local trunk
        prefix, replace with "+234".
      - Otherwise prepend "+" if it begins with a digit string of plausible
        length. If the result doesn't look like a phone, return None so we
        don't store junk.
    """
    if not raw:
        return None
    s = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    if not s:
        return None
    if s.startswith("+"):
        digits = s[1:]
        return "+" + digits if 8 <= len(digits) <= 15 else None
    if s.startswith("00"):
        digits = s[2:]
        return "+" + digits if 8 <= len(digits) <= 15 else None
    if s.startswith("0"):
        # Local trunk prefix — chop it and prepend Nigerian country code.
        digits = s[1:]
        if 9 <= len(digits) <= 11:
            return f"+{_DEFAULT_COUNTRY_CODE}{digits}"
        return None
    # Bare digits: assume already missing only the "+".
    if 8 <= len(s) <= 15:
        return "+" + s
    return None
