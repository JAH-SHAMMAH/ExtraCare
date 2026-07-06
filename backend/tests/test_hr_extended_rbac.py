"""RBAC boundary for confidential HR (Recruitment + Disciplinary).

Both modules gate EVERY endpoint (read AND write) on ``hr:write``. This proves an
hr:read-only role (teacher / staff / nurse) genuinely cannot read or write that
data by exercising the exact ``PermissionChecker`` dependency the routers use —
not just asserting presets.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.core.permissions import PermissionChecker

pytestmark = pytest.mark.asyncio

# The single gate guarding recruitment + disciplinary (read AND write).
CONFIDENTIAL_HR_GATE = "hr:write"


async def _user(db, org, slug: str) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:5]}@example.com",
             full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:5]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _run_gate(user: User, org, db):
    """Invoke the exact dependency the recruitment + disciplinary routers use."""
    checker = PermissionChecker(CONFIDENTIAL_HR_GATE)
    request = SimpleNamespace(state=SimpleNamespace(org=org, org_id=org.id))
    return await checker(request=request, current_user=user, db=db)


async def test_hr_readonly_roles_cannot_touch_recruitment_or_disciplinary(db, org):
    # teacher / staff / nurse hold hr:READ (general HR) but NOT hr:write. The
    # confidential endpoints are all hr:write, so the gate must reject them.
    for slug in ("teacher", "staff", "nurse"):
        u = await _user(db, org, slug)
        assert u.has_permission("hr:read")            # can use general HR …
        assert not u.has_permission("hr:write")       # … but NOT confidential HR
        with pytest.raises(HTTPException) as exc:
            await _run_gate(u, org, db)
        assert exc.value.status_code == 403            # the gate blocks them


async def test_hr_admins_pass_the_confidential_gate(db, org):
    for slug in ("org_admin", "manager"):
        u = await _user(db, org, slug)
        assert u.has_permission("hr:write")
        granted = await _run_gate(u, org, db)
        assert granted.id == u.id                      # the gate grants access
