"""ICE server configuration builder for WebRTC peers.

Produces the `iceServers` list that browsers pass to `RTCPeerConnection`.
Always includes configured STUN; adds TURN when credentials exist.

Three credential paths:

1. TURN_SECRET set  → mint ephemeral HMAC-SHA1 creds (coturn
   "use-auth-secret"). Username = "<expiry>:<user_id>"; credential =
   base64(HMAC_SHA1(secret, username)). Browsers cache these for the TTL.
2. TURN_USERNAME + TURN_CREDENTIAL set → pass static creds through.
3. Neither → TURN is omitted and peers fall back to STUN-only, which will
   fail on symmetric NAT but keeps dev simple.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Optional

from app.config import Settings


def build_ice_servers(settings: Settings, user_id: Optional[str] = None) -> list[dict]:
    servers: list[dict] = []

    for url in settings.stun_url_list:
        servers.append({"urls": url})

    turn_urls = settings.turn_url_list
    if turn_urls:
        if settings.TURN_SECRET:
            username, credential, ttl = _mint_ephemeral(
                secret=settings.TURN_SECRET,
                user_id=user_id or "anon",
                ttl_seconds=settings.TURN_TTL_SECONDS,
            )
            servers.append({
                "urls": turn_urls,
                "username": username,
                "credential": credential,
                # Non-standard hint the frontend uses for refresh scheduling.
                "credentialTtl": ttl,
            })
        elif settings.TURN_USERNAME and settings.TURN_CREDENTIAL:
            servers.append({
                "urls": turn_urls,
                "username": settings.TURN_USERNAME,
                "credential": settings.TURN_CREDENTIAL,
            })

    return servers


def _mint_ephemeral(secret: str, user_id: str, ttl_seconds: int) -> tuple[str, str, int]:
    """Return (username, credential, ttl_seconds) per coturn's REST API spec.

    See https://datatracker.ietf.org/doc/html/draft-uberti-behave-turn-rest-00.
    """
    expiry = int(time.time()) + ttl_seconds
    username = f"{expiry}:{user_id}"
    digest = hmac.new(secret.encode(), username.encode(), hashlib.sha1).digest()
    credential = base64.b64encode(digest).decode()
    return username, credential, ttl_seconds
