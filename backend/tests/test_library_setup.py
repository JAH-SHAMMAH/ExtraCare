"""Library Setup + Manage Reviews coverage.

Proves the Setup surface + moderation:
  • settings singleton defaults then persists; the loan period defaults a due date
    and the per-user limit is enforced at issue;
  • category/location CRUD is tenant-scoped with duplicate protection;
  • reviews are moderated — pending until approved, non-admins only ever see the
    approved (public) set, an admin approves/deletes.
"""
import uuid
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role
from app.models.modules.school import LibraryBook
from app.routers.modules.library import (
    issue_loan,
    get_library_settings, update_library_settings,
    list_library_categories, create_library_category, delete_library_category,
    list_library_locations, create_library_location, delete_library_location,
    list_reviews, create_review, moderate_review, delete_review,
)
from app.schemas.library import (
    LibrarySettingsUpdate, LibraryCategoryCreate, LibraryLocationCreate,
    ReviewCreate, ReviewModerate,
)

pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"admin-{uuid.uuid4().hex[:6]}@x.com",
             full_name="Librarian", status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name="org_admin", slug="org_admin", permissions=[], org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _book(db, org, title="Book"):
    b = LibraryBook(id=str(uuid.uuid4()), title=title, author="A", total_copies=2, available_copies=2, org_id=org.id)
    db.add(b)
    await db.flush()
    return b


# ── Settings + loan wiring ────────────────────────────────────────────────────

async def test_settings_default_then_update(db, org):
    admin = await _admin(db, org)
    s = await get_library_settings(db=db, current_user=admin)
    assert s["loan_period_days"] == 14 and s["max_books_per_user"] == 3 and s["review_needs_approval"] is True

    upd = await update_library_settings(LibrarySettingsUpdate(loan_period_days=7, max_books_per_user=1), db=db, current_user=admin)
    assert upd["loan_period_days"] == 7 and upd["max_books_per_user"] == 1


async def test_loan_due_defaults_from_settings_and_limit_enforced(db, org, teacher):
    admin = await _admin(db, org)
    await update_library_settings(LibrarySettingsUpdate(loan_period_days=7, max_books_per_user=1), db=db, current_user=admin)
    b1 = await _book(db, org, "One")
    b2 = await _book(db, org, "Two")

    # No due_date supplied → defaults to today + loan_period_days.
    loan = await issue_loan(payload={"book_id": b1.id, "borrower_user_id": teacher.id}, db=db, current_user=admin)
    assert loan["due_date"] == (date.today() + timedelta(days=7)).isoformat()

    # Second concurrent loan exceeds the per-user limit of 1.
    with pytest.raises(HTTPException) as ei:
        await issue_loan(payload={"book_id": b2.id, "borrower_user_id": teacher.id}, db=db, current_user=admin)
    assert ei.value.status_code == 409


# ── Categories + locations ────────────────────────────────────────────────────

async def test_category_crud(db, org):
    admin = await _admin(db, org)
    c = await create_library_category(LibraryCategoryCreate(name="Fiction"), db=db, current_user=admin)
    assert c["name"] == "Fiction"
    assert any(x["id"] == c["id"] for x in await list_library_categories(db=db, current_user=admin))
    await delete_library_category(c["id"], db=db, current_user=admin)
    assert await list_library_categories(db=db, current_user=admin) == []


async def test_category_duplicate_conflicts(db, org):
    # A duplicate name 409s. (Left as the last DB op — the IntegrityError leaves the
    # async session unusable without a rollback the request lifecycle would do.)
    admin = await _admin(db, org)
    await create_library_category(LibraryCategoryCreate(name="Fiction"), db=db, current_user=admin)
    with pytest.raises(HTTPException) as ei:
        await create_library_category(LibraryCategoryCreate(name="Fiction"), db=db, current_user=admin)
    assert ei.value.status_code == 409


async def test_location_crud(db, org):
    admin = await _admin(db, org)
    loc = await create_library_location(LibraryLocationCreate(name="Aisle A", code="A3"), db=db, current_user=admin)
    assert loc["code"] == "A3"
    listed = await list_library_locations(db=db, current_user=admin)
    assert any(x["id"] == loc["id"] for x in listed)
    await delete_library_location(loc["id"], db=db, current_user=admin)
    assert await list_library_locations(db=db, current_user=admin) == []


# ── Reviews moderation ────────────────────────────────────────────────────────

async def test_review_moderation_flow(db, org, teacher):
    admin = await _admin(db, org)
    book = await _book(db, org, "Reviewed")

    # Default settings require approval → new review is pending.
    r = await create_review(ReviewCreate(book_id=book.id, rating=5, comment="Loved it"), db=db, current_user=teacher)
    assert r["status"] == "pending" and r["reviewer_name"]

    # A non-admin only sees approved reviews; the admin sees the pending one.
    assert await list_reviews(status=None, book_id=None, db=db, current_user=teacher) == []
    pending = await list_reviews(status="pending", book_id=None, db=db, current_user=admin)
    assert any(x["id"] == r["id"] for x in pending)

    # Approve → now visible to everyone.
    await moderate_review(r["id"], ReviewModerate(status="approved"), db=db, current_user=admin)
    public = await list_reviews(status=None, book_id=None, db=db, current_user=teacher)
    assert [x["id"] for x in public] == [r["id"]]

    await delete_review(r["id"], db=db, current_user=admin)
    assert await list_reviews(status=None, book_id=None, db=db, current_user=admin) == []
