"""File uploads — avatar (image) and generic document.

Persists via app.services.storage.save_upload (Cloudinary when configured, else
local disk) and returns a servable URL. Avatar upload also sets the caller's
avatar_url so the profile page reflects it after a ["me"] refetch.
"""
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.services.storage import save_upload

_logger = logging.getLogger("extracare.upload")
from app.services.super_settings import require_role_perm

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
    if (file.content_type or "").startswith("image/"):
        # The declared type is only a claim: make sure the bytes really are a picture.
        try:
            import io
            from PIL import Image
            Image.open(io.BytesIO(content)).verify()
        except Exception:
            raise HTTPException(status_code=415, detail="That file is not a valid image.")
    return content


@router.post("/avatar", dependencies=[Depends(require_role_perm("avatar", "Changing your profile picture"))])
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload the caller's profile photo, persist it as avatar_url, return the URL."""
    content = await _read_validated(file, _IMAGE_TYPES, _MAX_AVATAR)
    url = await save_upload(current_user.org_id, "avatars", file.filename, content, file.content_type)
    await db.execute(update(User).where(User.id == current_user.id).values(avatar_url=url))
    _logger.info("upload.avatar user=%s url=%s", current_user.id, url)
    return {"url": url, "filename": file.filename}


@router.post("/avatar/{user_id}", dependencies=[Depends(PermissionChecker("users:write"))])
async def upload_avatar_for_user(
    user_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Admin-set another user's profile photo (users:write). Target must be in the
    caller's org. Makes staff/student directories — and the feed Select-Users
    modal — photo-rich for people who never uploaded their own avatar."""
    target = (await db.execute(
        select(User).where(User.id == user_id, User.org_id == current_user.org_id, User.is_deleted == False)
    )).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    content = await _read_validated(file, _IMAGE_TYPES, _MAX_AVATAR)
    url = await save_upload(current_user.org_id, "avatars", file.filename, content, file.content_type)
    await db.execute(update(User).where(User.id == target.id).values(avatar_url=url))
    _logger.info("upload.avatar.admin actor=%s target=%s url=%s", current_user.id, target.id, url)
    return {"url": url, "user_id": target.id, "filename": file.filename}


@router.post("/document")
async def upload_document(
    file: UploadFile = File(...),
    category: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Store a document under the org and return its URL."""
    content = await _read_validated(file, _DOC_TYPES, _MAX_DOC)
    url = await save_upload(current_user.org_id, "documents", file.filename, content, file.content_type)
    _logger.info("upload.document user=%s category=%s url=%s", current_user.id, category, url)
    return {"url": url, "filename": file.filename, "category": category}


@router.post("/report-photo")
async def upload_report_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """A picture of a child's work, for the Nursery report's SAMPLE PICTURE column.
    Returns a URL; attach it by sending photo_url with that goal's rating."""
    content = await _read_validated(file, _IMAGE_TYPES, _MAX_AVATAR)
    url = await save_upload(current_user.org_id, "report-photos", file.filename, content, file.content_type)
    _logger.info("upload.report_photo user=%s url=%s", current_user.id, url)
    return {"url": url, "filename": file.filename}


@router.post("/student-photo", dependencies=[Depends(PermissionChecker("school:write"))])
async def upload_student_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """A student's profile picture. Returns a URL; attach it by saving the student
    with photo_url (create/edit student)."""
    content = await _read_validated(file, _IMAGE_TYPES, _MAX_AVATAR)
    url = await save_upload(current_user.org_id, "student-photos", file.filename, content, file.content_type)
    return {"url": url, "filename": file.filename}
