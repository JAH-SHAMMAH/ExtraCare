"""Super Settings API. Writes and the full list are Super-User-only; the boolean
flags are readable by any signed-in user so the UI can hide switched-off pages."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
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
