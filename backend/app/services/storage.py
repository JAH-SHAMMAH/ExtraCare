"""Pluggable upload storage.

One entry point — ``save_upload`` — persists an uploaded file and returns a
durable, browser-servable URL. Backend is chosen at runtime:

  • Cloudinary  (when ``CLOUDINARY_URL`` is set) — files live on Cloudinary's CDN,
    so they survive redeploys AND work across multiple app instances. Returns an
    absolute ``https://res.cloudinary.com/…`` URL (the frontend's resolveMediaUrl
    passes absolute URLs through unchanged).
  • Local disk  (default, dev) — writes under ``UPLOAD_DIR`` and returns a
    ``/uploads/<org>/<kind>/<file>`` path served by the StaticFiles mount. NOT
    durable on an ephemeral filesystem (see DEPLOYMENT.md §5b) — Cloudinary is the
    production answer.

The ``cloudinary`` package is imported LAZILY (only when actually uploading), so
the app imports fine without it installed and tests that don't configure
Cloudinary never touch it.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from pathlib import Path
from urllib.parse import urlparse

from app.config import get_settings

logger = logging.getLogger("extracare.storage")


def cloudinary_enabled() -> bool:
    return bool(get_settings().CLOUDINARY_URL)


def _resource_type(content_type: str) -> str:
    """Cloudinary resource_type — images/videos get transforms/CDN; everything
    else (pdf/word/excel/…) is 'raw' so it's stored + served verbatim."""
    ct = (content_type or "").lower()
    if ct.startswith("image/"):
        return "image"
    if ct.startswith("video/"):
        return "video"
    return "raw"


def _local_save(org_id: str, kind: str, filename: str | None, content: bytes) -> str:
    org_dir = Path(get_settings().UPLOAD_DIR) / org_id / kind
    org_dir.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(filename or "")[1].lower()[:10]
    safe = f"{uuid.uuid4().hex}{ext}"
    with open(org_dir / safe, "wb") as fh:
        fh.write(content)
    return f"/uploads/{org_id}/{kind}/{safe}"


def _cloudinary_upload_sync(org_id: str, kind: str, filename: str | None, content: bytes, content_type: str) -> str:
    import io
    import cloudinary
    import cloudinary.uploader

    # Configure from CLOUDINARY_URL (cloudinary://<key>:<secret>@<cloud>). Parsed
    # explicitly so it works whether the value came from a real env var or a .env.
    parsed = urlparse(get_settings().CLOUDINARY_URL)
    cloudinary.config(cloud_name=parsed.hostname, api_key=parsed.username,
                      api_secret=parsed.password, secure=True)

    res = cloudinary.uploader.upload(
        io.BytesIO(content),
        folder=f"extracare/{org_id}/{kind}",
        resource_type=_resource_type(content_type),
        public_id=uuid.uuid4().hex,     # no PII / original name in the URL
        overwrite=False,
    )
    return res["secure_url"]


async def save_upload(org_id: str, kind: str, filename: str | None, content: bytes, content_type: str = "") -> str:
    """Persist bytes and return a servable URL. Cloudinary when configured (run in
    a thread — the SDK is blocking), else local disk."""
    if cloudinary_enabled():
        url = await asyncio.to_thread(_cloudinary_upload_sync, org_id, kind, filename, content, content_type)
        logger.info("storage.cloudinary org=%s kind=%s bytes=%s", org_id, kind, len(content))
        return url
    return _local_save(org_id, kind, filename, content)
