"""Photo Journals — ownership scoping on DELETE.

The gap (logged 2026-08-05, teacher parity audit item #2) was that
`DELETE /journals/{id}` checked only `org_id`, so any teacher could delete any
other teacher's journal. The check landed the same day in `fcb80be` but was
never covered by a test, so this file locks the invariant in.

The bypass is `school:write`, which only matters because of how
`User.has_permission` resolves scopes: the hierarchy is ONE-DIRECTIONAL. A broad
two-part grant covers its children (`school:write` satisfies
`school:journals:write`), but never the reverse — so a teacher holding
`school:journals:write` does NOT satisfy `school:write`. That is precisely what
makes the gate real for teachers and transparent for administrators, and it is
the part a refactor could silently break, so it is asserted here directly.

Every actor carries a REAL role preset rather than a hand-made permission list:
a roleless fixture has no permissions at all, which would make the ownership
branch pass for the wrong reason.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select

from app.models.modules.school import PhotoJournal
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.journals import create_journal, delete_journal
from app.schemas.school_experience import JournalCreate

pytestmark = pytest.mark.asyncio


async def _make_user(db, org, preset: str, email: str, name: str) -> User:
    role = Role(
        id=str(uuid.uuid4()), name=preset.title(),
        slug=f"{preset}-{uuid.uuid4().hex[:6]}",
        permissions=list(SCHOOL_PERMISSION_PRESETS[preset]),
        org_id=org.id, is_system=False,
    )
    db.add(role)
    u = User(
        id=str(uuid.uuid4()), email=email, full_name=name,
        status=UserStatus.ACTIVE, org_id=org.id,
    )
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


@pytest_asyncio.fixture
async def other_teacher(db, org) -> User:
    """A SECOND teacher — the one whose journal must be safe from the first."""
    return await _make_user(db, org, "teacher", "teacher2@example.com", "Teacher Two")


@pytest_asyncio.fixture
async def school_admin(db, org) -> User:
    """`org_admin`, which holds `school:*` and so bypasses the ownership check."""
    return await _make_user(db, org, "org_admin", "admin@example.com", "Org Admin")


async def _post(db, user, title="A day out") -> str:
    created = await create_journal(
        payload=JournalCreate(title=title, photo_url="/uploads/x/journals/a.jpg"),
        db=db, current_user=user,
    )
    return created["id"]


async def _is_deleted(db, journal_id: str) -> bool:
    row = (await db.execute(
        select(PhotoJournal).where(PhotoJournal.id == journal_id)
    )).scalar_one()
    return bool(row.is_deleted)


async def test_teacher_cannot_delete_another_teachers_journal(db, teacher, other_teacher):
    journal_id = await _post(db, other_teacher)
    with pytest.raises(HTTPException) as exc:
        await delete_journal(journal_id=journal_id, db=db, current_user=teacher)
    assert exc.value.status_code == 403
    # The refusal must also not have soft-deleted it on the way out.
    assert await _is_deleted(db, journal_id) is False


async def test_teacher_can_delete_own_journal(db, teacher):
    journal_id = await _post(db, teacher)
    await delete_journal(journal_id=journal_id, db=db, current_user=teacher)
    assert await _is_deleted(db, journal_id) is True


async def test_admin_can_delete_any_journal(db, teacher, school_admin):
    """The bypass exists so moderation stays possible; assert it still works.

    Without this, tightening the ownership rule further could lock administrators
    out of their own moderation tool and nothing would catch it.
    """
    journal_id = await _post(db, teacher)
    await delete_journal(journal_id=journal_id, db=db, current_user=school_admin)
    assert await _is_deleted(db, journal_id) is True


async def test_teacher_preset_does_not_satisfy_the_admin_bypass(teacher, school_admin):
    """The load-bearing fact behind the gate, asserted on its own.

    If `school:journals:write` ever started satisfying `school:write` — a
    plausible "simplification" of the hierarchy in `User.has_permission` — the
    ownership check above would quietly become a no-op for every teacher while
    all three tests above still passed.
    """
    assert teacher.has_permission("school:journals:write") is True
    assert teacher.has_permission("school:write") is False
    assert school_admin.has_permission("school:write") is True
