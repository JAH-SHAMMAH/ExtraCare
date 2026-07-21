"""HR Documents & Templates router, prefix ``/hr``.

A registry of HR documents/templates, each pointing at a file uploaded via
POST /upload/document. Confidential HR admin — gated ``hr:write``.

ENDPOINTS:
  GET/POST     /hr/documents            (?category filter)
  PATCH/DELETE /hr/documents/{id}
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.permissions import PermissionChecker
from app.models.user import User
from app.models.hr_document import HrDocument
from app.schemas.hr_document import DocumentCreate, DocumentUpdate, DocumentResponse

router = APIRouter(prefix="/hr", tags=["HR — Documents"])

_can_hr = Depends(PermissionChecker("hr:write"))


def _response(d: HrDocument) -> DocumentResponse:
    return DocumentResponse(
        id=d.id, title=d.title, category=d.category, description=d.description,
        file_url=d.file_url, filename=d.filename, created_at=d.created_at, org_id=d.org_id,
    )


@router.get("/documents", response_model=list[DocumentResponse], dependencies=[_can_hr])
async def list_documents(
    category: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(HrDocument).where(HrDocument.org_id == current_user.org_id, HrDocument.is_deleted == False)  # noqa: E712
    if category:
        q = q.where(HrDocument.category == category)
    rows = (await db.execute(q.order_by(HrDocument.created_at.desc()))).scalars().all()
    return [_response(d) for d in rows]


@router.post("/documents", response_model=DocumentResponse, status_code=201, dependencies=[_can_hr])
async def create_document(payload: DocumentCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = HrDocument(
        title=payload.title.strip(), category=(payload.category or None),
        description=(payload.description or None), file_url=payload.file_url,
        filename=(payload.filename or None), created_by=current_user.id, org_id=current_user.org_id,
    )
    db.add(d)
    await db.flush()
    return _response(d)


async def _get_owned(db: AsyncSession, org_id: str, doc_id: str) -> HrDocument:
    d = (await db.execute(select(HrDocument).where(
        HrDocument.id == doc_id, HrDocument.org_id == org_id, HrDocument.is_deleted == False  # noqa: E712
    ))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Document not found.")
    return d


@router.patch("/documents/{doc_id}", response_model=DocumentResponse, dependencies=[_can_hr])
async def update_document(doc_id: str, payload: DocumentUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = await _get_owned(db, current_user.org_id, doc_id)
    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        data["title"] = data["title"].strip()
    for f, v in data.items():
        setattr(d, f, v)
    await db.flush()
    return _response(d)


@router.delete("/documents/{doc_id}", status_code=204, dependencies=[_can_hr])
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = await _get_owned(db, current_user.org_id, doc_id)
    d.is_deleted = True
    d.deleted_at = datetime.now(timezone.utc)
    await db.flush()
