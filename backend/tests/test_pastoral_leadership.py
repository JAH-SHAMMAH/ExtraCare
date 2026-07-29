"""Pastoral Batch F-1: Leadership Roles + Pastoral Heads + Head Dashboard."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.modules.pastoral import Hostel
from app.routers.modules.pastoral import (
    create_leadership_role, list_leadership_roles, update_leadership_role, delete_leadership_role,
    create_pastoral_head, list_pastoral_heads, update_pastoral_head, delete_pastoral_head,
    head_dashboard,
    create_disciplinary_case,
)
from app.schemas.pastoral import (
    LeadershipRoleCreate, LeadershipRoleUpdate,
    PastoralHeadCreate, PastoralHeadUpdate, DisciplinaryCaseCreate,
)


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Head Hana",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def test_leadership_roles(db, org):
    admin = await _admin(db, org)
    await create_leadership_role(payload=LeadershipRoleCreate(name="Prefect", sort_order=2), db=db, current_user=admin)
    a = await create_leadership_role(payload=LeadershipRoleCreate(name="Head Boy", sort_order=1), db=db, current_user=admin)
    rows = await list_leadership_roles(db=db, current_user=admin)
    assert [r.name for r in rows] == ["Head Boy", "Prefect"]   # sort_order
    b = await update_leadership_role(a.id, LeadershipRoleUpdate(is_active=False), db=db, current_user=admin)
    assert b.is_active is False
    await delete_leadership_role(a.id, db=db, current_user=admin)
    assert len(await list_leadership_roles(db=db, current_user=admin)) == 1


async def test_pastoral_heads(db, org):
    admin = await _admin(db, org)
    h = await create_pastoral_head(payload=PastoralHeadCreate(user_id=admin.id, title="Head of Boarding", scope="Green House"), db=db, current_user=admin)
    assert h.user_name == "Head Hana" and h.title == "Head of Boarding"

    # Unknown user rejected.
    with pytest.raises(HTTPException) as ei:
        await create_pastoral_head(payload=PastoralHeadCreate(user_id="nope", title="X"), db=db, current_user=admin)
    assert ei.value.status_code == 422

    h2 = await update_pastoral_head(h.id, PastoralHeadUpdate(title="Head of Pastoral Care"), db=db, current_user=admin)
    assert h2.title == "Head of Pastoral Care"
    assert len(await list_pastoral_heads(db=db, current_user=admin)) == 1
    await delete_pastoral_head(h.id, db=db, current_user=admin)
    assert len(await list_pastoral_heads(db=db, current_user=admin)) == 0


async def test_head_dashboard(db, org, student):
    admin = await _admin(db, org)
    db.add(Hostel(id=str(uuid.uuid4()), name="Green House", org_id=org.id))
    await db.commit()
    await create_pastoral_head(payload=PastoralHeadCreate(user_id=admin.id, title="Head of Boarding"), db=db, current_user=admin)
    await create_leadership_role(payload=LeadershipRoleCreate(name="Prefect"), db=db, current_user=admin)
    await create_disciplinary_case(payload=DisciplinaryCaseCreate(student_id=student.id, offence="Test", status="pending"), db=db, current_user=admin)

    d = await head_dashboard(db=db, current_user=admin)
    assert d.hostels == 1
    assert d.pastoral_heads == 1 and len(d.heads) == 1
    assert d.leadership_roles == 1
    assert d.open_cases == 1 and len(d.recent_cases) == 1
    assert d.recent_cases[0].student_name
