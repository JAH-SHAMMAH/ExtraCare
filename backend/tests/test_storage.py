"""Storage backend dispatch: Cloudinary when CLOUDINARY_URL is set, else local
disk. The cloudinary SDK is never imported here — we monkeypatch the dispatch."""
from __future__ import annotations

import pytest

from app.services import storage


pytestmark = pytest.mark.asyncio


async def test_save_upload_uses_cloudinary_when_enabled(monkeypatch):
    monkeypatch.setattr(storage, "cloudinary_enabled", lambda: True)
    seen: dict = {}

    def fake_cl(org_id, kind, filename, content, content_type):
        seen.update(org_id=org_id, kind=kind, filename=filename, ct=content_type)
        return "https://res.cloudinary.com/demo/image/upload/v1/extracare/org1/avatars/abc.png"

    monkeypatch.setattr(storage, "_cloudinary_upload_sync", fake_cl)

    url = await storage.save_upload("org1", "avatars", "a.png", b"data", "image/png")
    assert url.startswith("https://res.cloudinary.com/")
    assert seen == {"org_id": "org1", "kind": "avatars", "filename": "a.png", "ct": "image/png"}


async def test_save_upload_local_disk_when_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "cloudinary_enabled", lambda: False)

    class _S:
        UPLOAD_DIR = str(tmp_path)

    monkeypatch.setattr(storage, "get_settings", lambda: _S())

    url = await storage.save_upload("org1", "documents", "d.pdf", b"hello", "application/pdf")
    assert url.startswith("/uploads/org1/documents/") and url.endswith(".pdf")
    written = list((tmp_path / "org1" / "documents").glob("*.pdf"))
    assert len(written) == 1 and written[0].read_bytes() == b"hello"


def test_resource_type_mapping():
    assert storage._resource_type("image/png") == "image"
    assert storage._resource_type("video/mp4") == "video"
    assert storage._resource_type("application/pdf") == "raw"
    assert storage._resource_type("") == "raw"
