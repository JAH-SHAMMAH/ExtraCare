"""Tests for POST /upload/avatar and /upload/document.

The frontend upload hooks (profile page avatar) called /upload/* which didn't
exist (only /messenger/upload did). Proves:
  • avatar upload writes the file, returns a /uploads/... url, and persists it
    as the caller's avatar_url
  • document upload stores under the org and echoes category
  • both reject disallowed content types (415)
"""
from __future__ import annotations

import os
from io import BytesIO

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile

from app.config import get_settings
from app.routers.upload import upload_avatar, upload_document

pytestmark = pytest.mark.asyncio


def _file(filename: str, content_type: str, data: bytes = b"payload-bytes") -> UploadFile:
    return UploadFile(file=BytesIO(data), filename=filename, headers=Headers({"content-type": content_type}))


async def test_avatar_upload_persists_url(db, org, teacher, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "UPLOAD_DIR", str(tmp_path))
    res = await upload_avatar(file=_file("me.png", "image/png"), db=db, current_user=teacher)
    assert res["url"].startswith(f"/uploads/{org.id}/avatars/")
    # the file was actually written
    assert os.path.exists(os.path.join(str(tmp_path), org.id, "avatars", res["url"].split("/")[-1]))
    # and avatar_url was set on the user
    await db.refresh(teacher)
    assert teacher.avatar_url == res["url"]


async def test_avatar_rejects_non_image(db, org, teacher, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "UPLOAD_DIR", str(tmp_path))
    with pytest.raises(HTTPException) as exc:
        await upload_avatar(file=_file("x.pdf", "application/pdf"), db=db, current_user=teacher)
    assert exc.value.status_code == 415


async def test_document_upload(db, org, teacher, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "UPLOAD_DIR", str(tmp_path))
    res = await upload_document(file=_file("report.pdf", "application/pdf"), category="report",
                                db=db, current_user=teacher)
    assert res["url"].startswith(f"/uploads/{org.id}/documents/")
    assert res["category"] == "report" and res["filename"] == "report.pdf"


async def test_document_rejects_bad_type(db, org, teacher, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "UPLOAD_DIR", str(tmp_path))
    with pytest.raises(HTTPException) as exc:
        await upload_document(file=_file("x.exe", "application/x-msdownload"), category=None,
                              db=db, current_user=teacher)
    assert exc.value.status_code == 415
