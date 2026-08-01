"""Secondary Report parity S-1c: Result Type/Photo (level settings) + subject exclusion."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.modules.school import Subject
from app.routers.modules.platform import (
    upsert_level_setting, list_level_settings,
    create_subject_exclusion, list_subject_exclusions, delete_subject_exclusion,
)
from app.schemas.platform import LevelSettingUpsert, SubjectExclusionCreate


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Registrar",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def _subject(db, org, name="Mathematics") -> Subject:
    s = Subject(id=str(uuid.uuid4()), name=name, org_id=org.id)
    db.add(s)
    await db.commit()
    return s


async def test_level_settings_upsert(db, org):
    admin = await _admin(db, org)
    s = await upsert_level_setting(payload=LevelSettingUpsert(year_group="YEAR 7", result_type="junior", show_position=True, show_photo=False), db=db, current_user=admin)
    assert s.result_type == "junior" and s.show_photo is False

    # Upsert same year group updates in place (no duplicate).
    s2 = await upsert_level_setting(payload=LevelSettingUpsert(year_group="YEAR 7", result_type="senior", show_position=False, show_photo=True), db=db, current_user=admin)
    assert s2.id == s.id and s2.result_type == "senior" and s2.show_position is False and s2.show_photo is True
    assert len(await list_level_settings(db=db, current_user=admin)) == 1

    # Bad result_type rejected.
    with pytest.raises(HTTPException) as ei:
        await upsert_level_setting(payload=LevelSettingUpsert(year_group="YEAR 8", result_type="wizard"), db=db, current_user=admin)
    assert ei.value.status_code == 422


async def test_subject_exclusion(db, org):
    admin = await _admin(db, org)
    subj = await _subject(db, org)
    e = await create_subject_exclusion(payload=SubjectExclusionCreate(year_group="YEAR 7", subject_id=subj.id), db=db, current_user=admin)
    assert e.subject_name == "Mathematics" and e.year_group == "YEAR 7"

    # Unknown subject + duplicate guarded.
    with pytest.raises(HTTPException) as ei:
        await create_subject_exclusion(payload=SubjectExclusionCreate(year_group="YEAR 7", subject_id="nope"), db=db, current_user=admin)
    assert ei.value.status_code == 422
    with pytest.raises(HTTPException) as ei:
        await create_subject_exclusion(payload=SubjectExclusionCreate(year_group="YEAR 7", subject_id=subj.id), db=db, current_user=admin)
    assert ei.value.status_code == 409

    assert len(await list_subject_exclusions(year_group="YEAR 7", db=db, current_user=admin)) == 1
    assert len(await list_subject_exclusions(year_group="YEAR 8", db=db, current_user=admin)) == 0
    await delete_subject_exclusion(e.id, db=db, current_user=admin)
    assert len(await list_subject_exclusions(year_group=None, db=db, current_user=admin)) == 0
