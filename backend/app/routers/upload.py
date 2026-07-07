"""File uploads — avatar (image) and generic document.

Saves under UPLOAD_DIR/{org_id}/{kind}/ with a random filename and returns the
/uploads/... URL served by the static mount in main.py. Avatar upload also sets
the caller's avatar_url so the profile page reflects it after a ["me"] refetch.
"""
import logging
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.config import get_settings

_logger = logging.getLogger("extracare.upload")
router = APIRouter(prefix="/upload", tags=["Upload"])

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_DOC_TYPES = _IMAGE_TYPES | {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "text/csv",
}
_MAX_AVATAR = 5 * 1024 * 1024    # 5 MB
_MAX_DOC = 15 * 1024 * 1024      # 15 MB


async def _read_validated(file: UploadFile, allowed: set[str], max_size: int) -> bytes:
    if not file.filename:
        raise HTTPException(status_code=422, detail="No file provided.")
    if file.content_type not in allowed:
        raise HTTPException(status_code=415, detail=f"File type not allowed: {file.content_type or 'unknown'}")
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail=f"File exceeds the {max_size // 1024 // 1024} MB limit.")
    return content


def _save(org_id: str, kind: str, filename: str | None, content: bytes) -> tuple[str, str]:
    org_dir = os.path.join(get_settings().UPLOAD_DIR, org_id, kind)
    os.makedirs(org_dir, exist_ok=True)
    ext = os.path.splitext(filename or "")[1].lower()[:10]
    safe = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(org_dir, safe), "wb") as fh:
        fh.write(content)
    return safe, f"/uploads/{org_id}/{kind}/{safe}"


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload the caller's profile photo, persist it as avatar_url, return the URL."""
    content = await _read_validated(file, _IMAGE_TYPES, _MAX_AVATAR)
    _, url = _save(current_user.org_id, "avatars", file.filename, content)
    await db.execute(update(User).where(User.id == current_user.id).values(avatar_url=url))
    _logger.info("upload.avatar user=%s url=%s", current_user.id, url)
    return {"url": url, "filename": file.filename}


@router.post("/document")
async def upload_document(
    file: UploadFile = File(...),
    category: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Store a document under the org and return its URL."""
    content = await _read_validated(file, _DOC_TYPES, _MAX_DOC)
    _, url = _save(current_user.org_id, "documents", file.filename, content)
    _logger.info("upload.document user=%s category=%s url=%s", current_user.id, category, url)
    return {"url": url, "filename": file.filename, "category": category}
