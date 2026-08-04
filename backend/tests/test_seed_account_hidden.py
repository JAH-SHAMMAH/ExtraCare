"""is_seed_account users are hidden from every roster/directory that lists users.

The seed logins now live on the school's REAL login domain (they must, to pass the
auth email-domain gate), so nothing about the address keeps them out of admin views
— only this flag does. Covers the four surfaces that list accounts: Users list,
staff directory, HR staff accounts and global search.
"""
from __future__ import annotations

import uuid

import pytest

from app.models.role import Role
from app.models.user import User, UserStatus
from app.routers.hr_pim import list_accounts
from app.routers.search import global_search
from app.routers.users import list_staff
from app.services.user_service import get_users_paginated


pytestmark = pytest.mark.asyncio

REAL_EMAIL = "real.staff@fairviewschoolng.com"
SEED_EMAIL = "seed-classteacher@fairviewschoolng.com"


async def _two_users(db, org) -> tuple[User, User]:
    """One real staff account + one seed account, both otherwise identical."""
    admin_role = Role(id=str(uuid.uuid4()), org_id=org.id, name="Admin", slug="admin", permissions=["*"])
    db.add(admin_role)
    real = User(id=str(uuid.uuid4()), email=REAL_EMAIL, full_name="Real Staff",
                status=UserStatus.ACTIVE, org_id=org.id, job_title="Accountant")
    seed = User(id=str(uuid.uuid4()), email=SEED_EMAIL, full_name="Seed Class Teacher",
                status=UserStatus.ACTIVE, org_id=org.id, is_seed_account=True)
    real.roles = [admin_role]
    seed.roles = []
    db.add_all([real, seed])
    await db.commit()
    return real, seed


async def test_seed_accounts_excluded_from_users_list(db, org):
    await _two_users(db, org)

    resp = await get_users_paginated(db=db, org_id=org.id, page=1, page_size=50)
    emails = {u.email for u in resp.items}
    assert REAL_EMAIL in emails
    assert SEED_EMAIL not in emails
    # The count reflects the same filter (not just the page slice).
    assert resp.total == 1


async def test_seed_accounts_excluded_from_staff_directory(db, org):
    real, _ = await _two_users(db, org)

    rows = await list_staff(search=None, db=db, current_user=real)
    emails = {r.email for r in rows}
    assert REAL_EMAIL in emails
    assert SEED_EMAIL not in emails


async def test_seed_accounts_excluded_from_hr_accounts(db, org):
    real, _ = await _two_users(db, org)

    rows = await list_accounts(search=None, db=db, current_user=real)
    emails = {r.email for r in rows}
    assert REAL_EMAIL in emails
    assert SEED_EMAIL not in emails


async def test_seed_accounts_excluded_from_global_search(db, org):
    real, _ = await _two_users(db, org)

    # Both accounts match the term; only the real one may surface.
    result = await global_search(q="a", modules="users", db=db, current_user=real)
    sublabels = {i["sublabel"] for i in result["items"]}
    assert REAL_EMAIL in sublabels
    assert SEED_EMAIL not in sublabels
