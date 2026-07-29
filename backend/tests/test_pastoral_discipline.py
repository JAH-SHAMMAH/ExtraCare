"""Pastoral Batch E: Discipline — sanction groups, disciplinary actions,
committees (+members) and Behaviour & Sanction cases."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.routers.modules.pastoral import (
    create_sanction_group, list_sanction_groups, update_sanction_group, delete_sanction_group,
    create_disciplinary_action, list_disciplinary_actions, update_disciplinary_action,
    create_committee, list_committees, add_committee_member, remove_committee_member, delete_committee,
    create_disciplinary_case, list_disciplinary_cases, update_disciplinary_case, delete_disciplinary_case,
)
from app.schemas.pastoral import (
    SanctionGroupCreate, SanctionGroupUpdate,
    DisciplinaryActionCreate, DisciplinaryActionUpdate,
    CommitteeCreate, CommitteeMemberCreate,
    DisciplinaryCaseCreate, DisciplinaryCaseUpdate,
)


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Dean Dara",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def test_sanction_groups_and_actions(db, org):
    admin = await _admin(db, org)
    g = await create_sanction_group(payload=SanctionGroupCreate(name="Major"), db=db, current_user=admin)
    assert g.is_active is True
    a = await create_disciplinary_action(
        payload=DisciplinaryActionCreate(name="Suspension", sanction_group_id=g.id, severity="severe"),
        db=db, current_user=admin)
    assert a.sanction_group_name == "Major" and a.severity == "severe"

    # Bad severity rejected.
    with pytest.raises(HTTPException) as ei:
        await create_disciplinary_action(payload=DisciplinaryActionCreate(name="X", severity="nuclear"), db=db, current_user=admin)
    assert ei.value.status_code == 422

    a2 = await update_disciplinary_action(a.id, DisciplinaryActionUpdate(is_active=False), db=db, current_user=admin)
    assert a2.is_active is False
    assert len(await list_disciplinary_actions(db=db, current_user=admin)) == 1

    await update_sanction_group(g.id, SanctionGroupUpdate(description="Serious offences"), db=db, current_user=admin)
    assert len(await list_sanction_groups(db=db, current_user=admin)) == 1
    await delete_sanction_group(g.id, db=db, current_user=admin)
    assert len(await list_sanction_groups(db=db, current_user=admin)) == 0


async def test_committee_members(db, org):
    admin = await _admin(db, org)
    member = await _admin(db, org)
    c = await create_committee(payload=CommitteeCreate(name="Senior Discipline Panel"), db=db, current_user=admin)
    c2 = await add_committee_member(c.id, CommitteeMemberCreate(user_id=member.id, role_label="Chair"), db=db, current_user=admin)
    assert len(c2.members) == 1 and c2.members[0].role_label == "Chair" and c2.members[0].user_name

    # Duplicate guarded.
    with pytest.raises(HTTPException) as ei:
        await add_committee_member(c.id, CommitteeMemberCreate(user_id=member.id), db=db, current_user=admin)
    assert ei.value.status_code == 409

    committees = await list_committees(db=db, current_user=admin)
    assert len(committees) == 1 and len(committees[0].members) == 1
    await remove_committee_member(c2.members[0].id, db=db, current_user=admin)
    committees = await list_committees(db=db, current_user=admin)
    assert len(committees[0].members) == 0
    await delete_committee(c.id, db=db, current_user=admin)
    assert len(await list_committees(db=db, current_user=admin)) == 0


async def test_disciplinary_cases(db, org, student):
    admin = await _admin(db, org)
    g = await create_sanction_group(payload=SanctionGroupCreate(name="Minor"), db=db, current_user=admin)
    a = await create_disciplinary_action(payload=DisciplinaryActionCreate(name="Detention", sanction_group_id=g.id), db=db, current_user=admin)
    comm = await create_committee(payload=CommitteeCreate(name="Panel"), db=db, current_user=admin)

    case = await create_disciplinary_case(
        payload=DisciplinaryCaseCreate(student_id=student.id, committee_id=comm.id, action_id=a.id,
                                       sanction_group_id=g.id, offence="Late repeatedly", status="pending"),
        db=db, current_user=admin)
    assert case.student_name and case.action_name == "Detention" and case.committee_name == "Panel"
    assert case.recorded_by_name == "Dean Dara" and case.status == "pending"

    # Bad status rejected.
    with pytest.raises(HTTPException) as ei:
        await create_disciplinary_case(payload=DisciplinaryCaseCreate(student_id=student.id, status="whoops"), db=db, current_user=admin)
    assert ei.value.status_code == 422

    upd = await update_disciplinary_case(case.id, DisciplinaryCaseUpdate(status="resolved", sanction="1 week detention served"), db=db, current_user=admin)
    assert upd.status == "resolved" and upd.sanction == "1 week detention served"

    assert len(await list_disciplinary_cases(student_id=student.id, status=None, db=db, current_user=admin)) == 1
    assert len(await list_disciplinary_cases(student_id=None, status="pending", db=db, current_user=admin)) == 0
    assert len(await list_disciplinary_cases(student_id=None, status="resolved", db=db, current_user=admin)) == 1

    await delete_disciplinary_case(case.id, db=db, current_user=admin)
    assert len(await list_disciplinary_cases(student_id=student.id, status=None, db=db, current_user=admin)) == 0
