"""
In-process rate limiter.

Intentionally dependency-free: a single-process sliding-window counter keyed
by (bucket, client_ip). Good enough for login / refresh / industry-change
abuse protection on a single app instance. When we scale horizontally, swap
the backing store for Redis without changing the call sites.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from threading import Lock
from typing import Deque

from fastapi import Depends, HTTPException, Request, status

_logger = logging.getLogger("extracare.access")
_lock = Lock()
_hits: dict[tuple[str, str], Deque[float]] = {}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str, max_hits: int, window_seconds: int):
    """
    Dependency factory. `bucket` scopes the limiter (e.g. "login"), so
    different endpoints don't compete for the same budget.

    Usage:
        @router.post("/login", dependencies=[Depends(rate_limit("login", 20, 60))])
    """

    async def _check(request: Request):
        key = (bucket, _client_ip(request))
        now = time.monotonic()
        cutoff = now - window_seconds

        with _lock:
            q = _hits.get(key)
            if q is None:
                q = deque()
                _hits[key] = q
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= max_hits:
                retry_in = int(window_seconds - (now - q[0])) + 1
                _logger.warning(
                    "rate_limit_exceeded",
                    extra={
                        "event": "rate_limit_exceeded",
                        "bucket": bucket,
                        "client_ip": key[1],
                        "path": request.url.path,
                        "limit": max_hits,
                        "window_seconds": window_seconds,
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many requests. Retry in ~{retry_in}s.",
                    headers={"Retry-After": str(retry_in)},
                )
            q.append(now)

    return _check
