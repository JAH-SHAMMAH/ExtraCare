"""Pastoral Setup → settings: GET auto-creates defaults, PUT merges flags +
validates the School-Nurse role. One row per org."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role
from app.routers.modules.pastoral import get_pastoral_settings, update_pastoral_settings
from app.schemas.pastoral import PastoralSettingsUpdate


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Admin",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def _role(db, org, name="School Nurse") -> Role:
    r = Role(id=str(uuid.uuid4()), name=name, slug=f"r-{uuid.uuid4().hex[:6]}", permissions=[], org_id=org.id, is_system=False)
    db.add(r)
    await db.commit()
    return r


async def test_settings_defaults_and_update(db, org):
    admin = await _admin(db, org)

    s = await get_pastoral_settings(db=db, current_user=admin)
    # Sensible defaults (Educare-style): notify parent + pastoral head + allow referral/observation on.
    assert s.notify_parent_on_exeat_approval is True and s.notify_pastoral_head_on_new_request is True
    assert s.allow_referral_in_mentor_comment is True and s.allow_observation_in_mentor_comment is True
    assert s.enable_head_only_approval is False and s.school_nurse_role_id is None

    nurse = await _role(db, org, "School Nurse")
    upd = await update_pastoral_settings(
        payload=PastoralSettingsUpdate(enable_head_only_approval=True, show_award_in_point_analysis=True,
                                       allow_referral_in_mentor_comment=False, school_nurse_role_id=nurse.id),
        request=None, db=db, current_user=admin,
    )
    assert upd.enable_head_only_approval is True and upd.show_award_in_point_analysis is True
    assert upd.allow_referral_in_mentor_comment is False
    assert upd.school_nurse_role_id == nurse.id and upd.school_nurse_role_name == "School Nurse"

    # Untouched flags keep their prior value (merge, not replace).
    assert (await get_pastoral_settings(db=db, current_user=admin)).notify_parent_on_exeat_approval is True


async def test_settings_rejects_foreign_nurse_role(db, org):
    admin = await _admin(db, org)
    with pytest.raises(HTTPException) as exc:
        await update_pastoral_settings(payload=PastoralSettingsUpdate(school_nurse_role_id="not-a-role"),
                                       request=None, db=db, current_user=admin)
    assert exc.value.status_code == 422

    # Empty string clears it (no error).
    cleared = await update_pastoral_settings(payload=PastoralSettingsUpdate(school_nurse_role_id=""),
                                             request=None, db=db, current_user=admin)
    assert cleared.school_nurse_role_id is None
