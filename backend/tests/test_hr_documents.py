"""Tests for HR Documents & Templates. Gated hr:write.

Covers CRUD, category filtering, soft-delete, org isolation and the hr:write gate.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.core.permissions import PermissionChecker
from app.routers.hr_documents import list_documents, create_document, update_document, delete_document
from app.schemas.hr_document import DocumentCreate, DocumentUpdate

pytestmark = pytest.mark.asyncio


async def _preset_user(db, org, slug) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def test_create_and_list(db, org, teacher):
    d = await create_document(DocumentCreate(title="  Staff Handbook  ", category="Policy",
                                             file_url="/uploads/o/documents/x.pdf", filename="handbook.pdf"),
                              db=db, current_user=teacher)
    assert d.title == "Staff Handbook" and d.file_url.endswith("x.pdf")
    listed = await list_documents(category=None, db=db, current_user=teacher)
    assert [x.id for x in listed] == [d.id]


async def test_category_filter(db, org, teacher):
    await create_document(DocumentCreate(title="A", category="Policy", file_url="/u/a.pdf"), db=db, current_user=teacher)
    await create_document(DocumentCreate(title="B", category="Template", file_url="/u/b.pdf"), db=db, current_user=teacher)
    pol = await list_documents(category="Policy", db=db, current_user=teacher)
    assert {x.title for x in pol} == {"A"}


async def test_update_and_delete(db, org, teacher):
    d = await create_document(DocumentCreate(title="X", file_url="/u/x.pdf"), db=db, current_user=teacher)
    up = await update_document(d.id, DocumentUpdate(title="Renamed", category="HR"), db=db, current_user=teacher)
    assert up.title == "Renamed" and up.category == "HR"
    await delete_document(d.id, db=db, current_user=teacher)
    assert d.id not in [x.id for x in await list_documents(category=None, db=db, current_user=teacher)]
    with pytest.raises(HTTPException) as exc:
        await update_document(d.id, DocumentUpdate(title="Z"), db=db, current_user=teacher)
    assert exc.value.status_code == 404


async def test_org_isolation(db, org, teacher):
    d = await create_document(DocumentCreate(title="Mine", file_url="/u/m.pdf"), db=db, current_user=teacher)
    other = SimpleNamespace(org_id=str(uuid.uuid4()))
    assert d.id not in [x.id for x in await list_documents(category=None, db=db, current_user=other)]
    with pytest.raises(HTTPException) as exc:
        await update_document(d.id, DocumentUpdate(title="Hijack"), db=db, current_user=other)
    assert exc.value.status_code == 404


async def _run_gate(user, org, db):
    checker = PermissionChecker("hr:write")
    request = SimpleNamespace(state=SimpleNamespace(org=org, org_id=org.id))
    return await checker(request=request, current_user=user, db=db)


async def test_documents_rbac(db, org):
    tchr = await _preset_user(db, org, "teacher")
    assert not tchr.has_permission("hr:write")
    with pytest.raises(HTTPException) as exc:
        await _run_gate(tchr, org, db)
    assert exc.value.status_code == 403
    for slug in ("org_admin", "manager"):
        u = await _preset_user(db, org, slug)
        assert (await _run_gate(u, org, db)).id == u.id
