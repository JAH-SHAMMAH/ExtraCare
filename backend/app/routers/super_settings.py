"""Super Settings API. Writes and the full list are Super-User-only; the boolean
flags are readable by any signed-in user so the UI can hide switched-off pages."""
from __future__ import annotations

import io

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.services import super_settings as ss
from app.services.audit_service import log_action
from app.models.audit import AuditAction

router = APIRouter(prefix="/super-settings", tags=["Super Settings"])


def _must_be_super(user: User = Depends(get_current_active_user)) -> User:
    if not ss.is_super_user(user):
        raise HTTPException(status_code=403, detail="Only the Super User can change these settings.")
    return user


@router.get("/flags")
async def flags(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    vals = await ss.get_values(db, user.org_id)
    return {f["key"]: bool(vals[f["key"]]) for f in ss.FIELDS if f["kind"] == "bool"}


@router.get("")
async def read_all(db: AsyncSession = Depends(get_db), user: User = Depends(_must_be_super)):
    vals = await ss.get_values(db, user.org_id)
    return {"fields": ss.FIELDS, "values": vals}


@router.put("")
async def write(body: dict, request: Request, db: AsyncSession = Depends(get_db),
                user: User = Depends(_must_be_super)):
    updates = body.get("values")
    if not isinstance(updates, dict) or not updates:
        raise HTTPException(422, detail="Send {\"values\": {key: value}}.")
    vals = await ss.set_values(db, user.org_id, updates)
    changed = ", ".join(sorted(k for k in updates if ss.BY_KEY.get(k, {}).get("kind") not in ss.SECRET_KINDS))
    await log_action(db, AuditAction.RECORD_UPDATED, user.org_id, actor=user,
                     resource_type="SuperSettings", resource_id=user.org_id,
                     resource_label=f"Super settings: {changed or 'secret fields'}", request=request)
    return {"values": vals}


@router.post("/images/{key}")
async def upload_image(key: str, file: UploadFile = File(...), user: User = Depends(_must_be_super)):
    """Check a logo/picture against the minimum size, store it, and return its address.
    The address is saved with the rest of the settings (Save Change)."""
    from PIL import Image
    from app.services.storage import save_upload
    if key not in ss.IMAGE_SPECS:
        raise HTTPException(404, detail="Unknown image.")
    if (file.content_type or "") not in ("image/png", "image/jpeg", "image/webp"):
        raise HTTPException(422, detail="Use a PNG, JPG or WebP image.")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(422, detail="The image is bigger than 5 MB.")
    try:
        w, h = Image.open(io.BytesIO(data)).size
    except Exception:
        raise HTTPException(422, detail="That file is not a valid image.")
    mw, mh = ss.IMAGE_SPECS[key]
    if w < mw or h < mh:
        raise HTTPException(422, detail=f"The image is {w}x{h}px. It should not be less than {mw}x{mh}px.")
    url = await save_upload(user.org_id, "branding", file.filename, data, file.content_type or "")
    return {"url": url, "width": w, "height": h}


# ── Structured settings ──────────────────────────────────────────────────────
@router.get("/ui")
async def ui(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    """Everything the shell needs to hide switched-off pages for THIS user. Booleans
    and page lists only: no text fields, no passwords."""
    vals = await ss.get_values(db, user.org_id)
    st = await ss.get_struct(db, user.org_id)
    return {
        "flags": {f["key"]: bool(vals[f["key"]]) for f in ss.FIELDS if f["kind"] == "bool"},
        "student_dashboard": st["student_dashboard"],
        "teacher_dashboard": st["teacher_dashboard"],
        "hidden_hrefs": ss.hidden_hrefs_for(st, user),
    }


@router.get("/structured")
async def read_struct(db: AsyncSession = Depends(get_db), user: User = Depends(_must_be_super)):
    return {"values": await ss.get_struct(db, user.org_id), "meta": ss.struct_meta()}


@router.put("/structured/{key}")
async def write_struct(key: str, body: dict, request: Request, db: AsyncSession = Depends(get_db),
                       user: User = Depends(_must_be_super)):
    if "value" not in body:
        raise HTTPException(422, detail="Send {\"value\": ...}.")
    out = await ss.set_struct(db, user.org_id, key, body["value"])
    await log_action(db, AuditAction.RECORD_UPDATED, user.org_id, actor=user,
                     resource_type="SuperSettings", resource_id=user.org_id,
                     resource_label=f"Super settings: {key}", request=request)
    return {"value": out}
