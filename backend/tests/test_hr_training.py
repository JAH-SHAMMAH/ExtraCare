"""Tests for Training (programs + sessions). Gated hr:write.

Covers CRUD, session_count, the all-sessions view with training title, cascade
soft-delete (deleting a training hides its sessions), org isolation and RBAC.
"""
from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.core.permissions import PermissionChecker
from app.routers.hr_training import (
    list_trainings, create_training, update_training, delete_training,
    list_training_sessions, create_session, list_all_sessions, update_session, delete_session,
)
from app.schemas.hr_training import TrainingCreate, TrainingUpdate, SessionCreate, SessionUpdate

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


async def test_create_training_and_sessions(db, org, teacher):
    t = await create_training(TrainingCreate(title="Safeguarding", category="Compliance"), db=db, current_user=teacher)
    assert t.status == "planned" and t.session_count == 0
    await create_session(t.id, SessionCreate(training_id=t.id, title="Intro", session_date=date(2026, 9, 1), facilitator="Ms A"), db=db, current_user=teacher)
    await create_session(t.id, SessionCreate(training_id=t.id, title="Practical", session_date=date(2026, 9, 8)), db=db, current_user=teacher)

    listed = await list_trainings(db=db, current_user=teacher)
    assert listed[0].session_count == 2                 # count reflected
    sessions = await list_training_sessions(t.id, db=db, current_user=teacher)
    assert {s.title for s in sessions} == {"Intro", "Practical"}
    assert all(s.training_title == "Safeguarding" for s in sessions)


async def test_all_sessions_view(db, org, teacher):
    t1 = await create_training(TrainingCreate(title="First Aid"), db=db, current_user=teacher)
    t2 = await create_training(TrainingCreate(title="Fire Drill"), db=db, current_user=teacher)
    await create_session(t1.id, SessionCreate(training_id=t1.id, session_date=date(2026, 8, 1)), db=db, current_user=teacher)
    await create_session(t2.id, SessionCreate(training_id=t2.id, session_date=date(2026, 8, 2)), db=db, current_user=teacher)
    all_s = await list_all_sessions(db=db, current_user=teacher)
    titles = {s.training_title for s in all_s}
    assert {"First Aid", "Fire Drill"} <= titles


async def test_update_training_and_session(db, org, teacher):
    t = await create_training(TrainingCreate(title="X"), db=db, current_user=teacher)
    tu = await update_training(t.id, TrainingUpdate(status="ongoing", title="  Updated  "), db=db, current_user=teacher)
    assert tu.status == "ongoing" and tu.title == "Updated"
    s = await create_session(t.id, SessionCreate(training_id=t.id), db=db, current_user=teacher)
    su = await update_session(s.id, SessionUpdate(location="Hall B"), db=db, current_user=teacher)
    assert su.location == "Hall B"


async def test_delete_training_cascades_sessions(db, org, teacher):
    t = await create_training(TrainingCreate(title="ToDelete"), db=db, current_user=teacher)
    await create_session(t.id, SessionCreate(training_id=t.id), db=db, current_user=teacher)
    await delete_training(t.id, db=db, current_user=teacher)
    assert t.id not in [x.id for x in await list_trainings(db=db, current_user=teacher)]
    # Its sessions are hidden from the all-sessions view.
    assert all(s.training_id != t.id for s in await list_all_sessions(db=db, current_user=teacher))


async def test_unknown_training_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_session("nope", SessionCreate(training_id="nope"), db=db, current_user=teacher)
    assert exc.value.status_code == 404


async def test_org_isolation(db, org, teacher):
    t = await create_training(TrainingCreate(title="Mine"), db=db, current_user=teacher)
    other = SimpleNamespace(org_id=str(uuid.uuid4()))
    assert t.id not in [x.id for x in await list_trainings(db=db, current_user=other)]
    with pytest.raises(HTTPException) as exc:
        await update_training(t.id, TrainingUpdate(title="Hijack"), db=db, current_user=other)
    assert exc.value.status_code == 404


async def _run_gate(user, org, db):
    checker = PermissionChecker("hr:write")
    request = SimpleNamespace(state=SimpleNamespace(org=org, org_id=org.id))
    return await checker(request=request, current_user=user, db=db)


async def test_training_rbac(db, org):
    tchr = await _preset_user(db, org, "teacher")
    assert not tchr.has_permission("hr:write")
    with pytest.raises(HTTPException) as exc:
        await _run_gate(tchr, org, db)
    assert exc.value.status_code == 403
    for slug in ("org_admin", "manager"):
        u = await _preset_user(db, org, slug)
        assert (await _run_gate(u, org, db)).id == u.id
