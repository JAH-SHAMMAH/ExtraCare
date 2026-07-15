"""
Library Management Router (Phase 6.5)
=====================================

Two tables, seven endpoints: enough to run a real school library without
being a distraction from the rest of the product.

  - /library/books         — catalogue CRUD (admin/librarian)
  - /library/loans         — issue + return (admin/librarian)
  - /library/loans/mine    — "my borrowed books" (every role)
  - /library/stats         — lightweight dashboard numbers

RBAC:
  - school:read   → browse catalogue, view one's own loans
  - school:write  → add books, issue/return loans

Scoping:
  - Students (non-admins) can list loans only for themselves. The `borrower_user_id`
    query param is silently forced to the current user unless the caller holds
    an admin/manager role.
"""

from datetime import date, datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.import_files import rows_from_upload

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.modules.school import (
    LibraryBook, LibraryLoan, LoanStatus, Student,
    LibrarySettings, LibraryCategory, LibraryLocation, BookReview, ReviewStatus,
)
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker
from app.schemas.library import (
    LibrarySettingsResponse, LibrarySettingsUpdate,
    LibraryCategoryCreate, LibraryCategoryResponse,
    LibraryLocationCreate, LibraryLocationResponse,
    ReviewCreate, ReviewModerate, ReviewResponse,
)
from sqlalchemy.exc import IntegrityError


router = APIRouter(
    prefix="/library",
    tags=["Library"],
    dependencies=[Depends(require_role_module("school"))],
)

_can_read = Depends(PermissionChecker("school:library:read"))
_can_write = Depends(PermissionChecker("school:library:write"))


# ── Helpers ──────────────────────────────────────────────────────────────────


def _is_admin(user: User) -> bool:
    return user.is_superadmin or any(
        r.slug in {"org_admin", "manager", "super_admin"} for r in user.roles
    )


def _book_dict(b: LibraryBook) -> dict[str, Any]:
    return {
        "id": b.id,
        "title": b.title,
        "author": b.author,
        "isbn": b.isbn,
        "category": b.category,
        "publisher": b.publisher,
        "publication_year": b.publication_year,
        "cover_url": b.cover_url,
        "shelf_location": b.shelf_location,
        "total_copies": b.total_copies,
        "available_copies": b.available_copies,
        "description": b.description,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }


def _loan_dict(
    loan: LibraryLoan,
    *,
    book: LibraryBook | None = None,
    borrower: User | None = None,
) -> dict[str, Any]:
    # "Overdue" is DERIVED from status + due_date. We never store it — a
    # stored overdue would need a cron to update nightly and drift whenever
    # that job fails. This single boolean is read-side only.
    is_overdue = (
        loan.status == LoanStatus.BORROWED
        and loan.due_date is not None
        and loan.due_date < date.today()
    )
    return {
        "id": loan.id,
        "book_id": loan.book_id,
        "book_title": book.title if book else None,
        "book_author": book.author if book else None,
        "book_category": book.category if book else None,
        "borrower_user_id": loan.borrower_user_id,
        "borrower_name": borrower.full_name if borrower else None,
        "borrower_email": borrower.email if borrower else None,
        "borrowed_at": loan.borrowed_at.isoformat() if loan.borrowed_at else None,
        "due_date": loan.due_date.isoformat() if loan.due_date else None,
        "returned_at": loan.returned_at.isoformat() if loan.returned_at else None,
        "status": loan.status.value if hasattr(loan.status, "value") else loan.status,
        "is_overdue": is_overdue,
        "notes": loan.notes,
    }


async def _hydrate_loans(
    db: AsyncSession,
    loans: list[LibraryLoan],
) -> list[dict[str, Any]]:
    book_ids = {l.book_id for l in loans}
    user_ids = {l.borrower_user_id for l in loans}
    books: dict[str, LibraryBook] = {}
    users: dict[str, User] = {}
    if book_ids:
        for b in (await db.execute(
            select(LibraryBook).where(LibraryBook.id.in_(book_ids))
        )).scalars().all():
            books[b.id] = b
    if user_ids:
        for u in (await db.execute(
            select(User).where(User.id.in_(user_ids))
        )).scalars().all():
            users[u.id] = u
    return [_loan_dict(l, book=books.get(l.book_id), borrower=users.get(l.borrower_user_id)) for l in loans]


# ── Catalogue ────────────────────────────────────────────────────────────────


@router.get("/books", dependencies=[_can_read])
async def list_books(
    search: str | None = None,
    category: str | None = None,
    available_only: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(LibraryBook).where(
        LibraryBook.org_id == current_user.org_id,
        LibraryBook.is_deleted == False,
    )
    if search:
        term = f"%{search}%"
        query = query.where(or_(
            LibraryBook.title.ilike(term),
            LibraryBook.author.ilike(term),
            LibraryBook.isbn.ilike(term),
        ))
    if category:
        query = query.where(LibraryBook.category == category)
    if available_only:
        query = query.where(LibraryBook.available_copies > 0)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(LibraryBook.title.asc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().all()

    # Distinct categories for the frontend filter — cheap enough to always
    # return so the dropdown hydrates in a single call.
    cats = (await db.execute(
        select(LibraryBook.category).where(
            LibraryBook.org_id == current_user.org_id,
            LibraryBook.is_deleted == False,
            LibraryBook.category.isnot(None),
        ).distinct()
    )).scalars().all()

    return {
        "items": [_book_dict(b) for b in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "categories": sorted([c for c in cats if c]),
    }


@router.post("/books", status_code=201, dependencies=[_can_write])
async def create_book(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    required = ("title", "author")
    missing = [k for k in required if not str(payload.get(k) or "").strip()]
    if missing:
        raise HTTPException(422, detail=f"Missing required fields: {', '.join(missing)}")
    total = int(payload.get("total_copies") or 1)
    if total < 1:
        raise HTTPException(422, detail="total_copies must be at least 1")
    book = LibraryBook(
        title=str(payload["title"]).strip(),
        author=str(payload["author"]).strip(),
        isbn=(payload.get("isbn") or None),
        category=(payload.get("category") or None),
        publisher=(payload.get("publisher") or None),
        publication_year=int(payload["publication_year"]) if payload.get("publication_year") else None,
        cover_url=(payload.get("cover_url") or None),
        shelf_location=(payload.get("shelf_location") or None),
        total_copies=total,
        available_copies=total,  # on creation, all copies are available
        description=(payload.get("description") or None),
        org_id=current_user.org_id,
    )
    db.add(book)
    await db.flush()
    return _book_dict(book)


async def _load_book_or_404(db: AsyncSession, book_id: str, user: User) -> LibraryBook:
    b = (await db.execute(
        select(LibraryBook).where(
            LibraryBook.id == book_id,
            LibraryBook.org_id == user.org_id,
            LibraryBook.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not b:
        raise HTTPException(404, detail=f"Book not found: {book_id}")
    return b


@router.patch("/books/{book_id}", dependencies=[_can_write])
async def update_book(
    book_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    b = await _load_book_or_404(db, book_id, current_user)

    editable_str = {"title", "author", "isbn", "category", "publisher",
                    "cover_url", "shelf_location", "description"}
    for k in editable_str:
        if k in payload:
            b.__setattr__(k, (payload[k] or None))

    if "publication_year" in payload:
        b.publication_year = int(payload["publication_year"]) if payload["publication_year"] else None

    # Adjusting total_copies: only allow growing, or shrinking down to the
    # count of active loans (never below available_copies + loans_out).
    if "total_copies" in payload:
        new_total = int(payload["total_copies"])
        if new_total < 1:
            raise HTTPException(422, detail="total_copies must be at least 1")
        loans_out = b.total_copies - b.available_copies
        if new_total < loans_out:
            raise HTTPException(
                409, detail=f"Cannot reduce below active loans ({loans_out} currently out)"
            )
        b.available_copies = new_total - loans_out
        b.total_copies = new_total

    await db.flush()
    return _book_dict(b)


@router.delete("/books/{book_id}", status_code=204, dependencies=[_can_write])
async def delete_book(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    b = await _load_book_or_404(db, book_id, current_user)
    # Guard: can't soft-delete a book with active loans — would orphan the loan.
    active_loans = (await db.execute(
        select(func.count(LibraryLoan.id)).where(
            LibraryLoan.book_id == b.id,
            LibraryLoan.status == LoanStatus.BORROWED,
        )
    )).scalar_one()
    if active_loans:
        raise HTTPException(
            409, detail=f"Cannot remove: {active_loans} active loan(s) for this book"
        )
    b.is_deleted = True
    b.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ── Loans ────────────────────────────────────────────────────────────────────


@router.get("/loans", dependencies=[_can_read])
async def list_loans(
    status: str | None = None,        # "borrowed" | "returned" | "overdue"
    borrower_user_id: str | None = None,
    book_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(LibraryLoan).where(LibraryLoan.org_id == current_user.org_id)

    # Non-admins can only list their own loans. Ignore any borrower_user_id
    # the client may have sent — don't 403, just narrow silently.
    if not _is_admin(current_user):
        query = query.where(LibraryLoan.borrower_user_id == current_user.id)
    elif borrower_user_id:
        query = query.where(LibraryLoan.borrower_user_id == borrower_user_id)

    if book_id:
        query = query.where(LibraryLoan.book_id == book_id)

    if status == "borrowed":
        query = query.where(LibraryLoan.status == LoanStatus.BORROWED)
    elif status == "returned":
        query = query.where(LibraryLoan.status == LoanStatus.RETURNED)
    elif status == "overdue":
        query = query.where(
            LibraryLoan.status == LoanStatus.BORROWED,
            LibraryLoan.due_date < date.today(),
        )

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(LibraryLoan.borrowed_at.desc()).offset((page - 1) * page_size).limit(page_size)
    loans = (await db.execute(query)).scalars().all()
    return {
        "items": await _hydrate_loans(db, list(loans)),
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/loans/mine", dependencies=[_can_read])
async def list_my_loans(
    include_returned: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Convenience endpoint for the student "My Library" page. Returns the
    current user's active loans, and (by default) their most recent returned
    loans so the history section isn't empty."""
    active = (await db.execute(
        select(LibraryLoan).where(
            LibraryLoan.org_id == current_user.org_id,
            LibraryLoan.borrower_user_id == current_user.id,
            LibraryLoan.status == LoanStatus.BORROWED,
        ).order_by(LibraryLoan.due_date.asc())
    )).scalars().all()

    history: list[LibraryLoan] = []
    if include_returned:
        history = list((await db.execute(
            select(LibraryLoan).where(
                LibraryLoan.org_id == current_user.org_id,
                LibraryLoan.borrower_user_id == current_user.id,
                LibraryLoan.status == LoanStatus.RETURNED,
            ).order_by(LibraryLoan.returned_at.desc()).limit(10)
        )).scalars().all())

    return {
        "active": await _hydrate_loans(db, list(active)),
        "history": await _hydrate_loans(db, history),
    }


@router.post("/loans", status_code=201, dependencies=[_can_write])
async def issue_loan(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    required = ("book_id", "borrower_user_id")
    missing = [k for k in required if not str(payload.get(k) or "").strip()]
    if missing:
        raise HTTPException(422, detail=f"Missing required fields: {', '.join(missing)}")
    settings = await _get_or_create_library_settings(db, current_user.org_id)
    # due_date defaults from the configured loan period when the caller omits it.
    if str(payload.get("due_date") or "").strip():
        try:
            due_date = date.fromisoformat(str(payload["due_date"]))
        except (TypeError, ValueError):
            raise HTTPException(422, detail="due_date must be YYYY-MM-DD")
    else:
        due_date = date.today() + timedelta(days=settings.loan_period_days)
    if due_date < date.today():
        raise HTTPException(422, detail="due_date must be today or later")

    book = await _load_book_or_404(db, str(payload["book_id"]), current_user)
    if book.available_copies < 1:
        raise HTTPException(409, detail=f"No copies available for '{book.title}'")

    # Enforce the borrowing limit (Library Setup "permissions").
    active = (await db.execute(
        select(func.count(LibraryLoan.id)).where(
            LibraryLoan.org_id == current_user.org_id,
            LibraryLoan.borrower_user_id == str(payload["borrower_user_id"]),
            LibraryLoan.status == LoanStatus.BORROWED,
        )
    )).scalar_one() or 0
    if active >= settings.max_books_per_user:
        raise HTTPException(409, detail=f"Borrower already holds the maximum of {settings.max_books_per_user} book(s).")

    # Ensure the borrower is in-tenant. Looking up (and not trusting the id
    # blindly) protects against cross-tenant loan issuance via a crafted payload.
    borrower = (await db.execute(
        select(User).where(
            User.id == str(payload["borrower_user_id"]),
            User.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()
    if not borrower:
        raise HTTPException(404, detail="Borrower not found in this organisation")

    loan = LibraryLoan(
        book_id=book.id,
        borrower_user_id=borrower.id,
        issued_by=current_user.id,
        due_date=due_date,
        notes=(payload.get("notes") or None),
        status=LoanStatus.BORROWED,
        org_id=current_user.org_id,
    )
    db.add(loan)
    # Decrement counter atomically in the same tx. If anything later in this
    # handler raises, the whole tx rolls back — no orphaned counter drift.
    book.available_copies = book.available_copies - 1
    await db.flush()
    return _loan_dict(loan, book=book, borrower=borrower)


@router.post("/loans/{loan_id}/return", dependencies=[_can_write])
async def return_loan(
    loan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    loan = (await db.execute(
        select(LibraryLoan).where(
            LibraryLoan.id == loan_id,
            LibraryLoan.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()
    if not loan:
        raise HTTPException(404, detail="Loan not found")
    if loan.status == LoanStatus.RETURNED:
        raise HTTPException(409, detail="Loan already returned")

    book = (await db.execute(
        select(LibraryBook).where(LibraryBook.id == loan.book_id)
    )).scalar_one_or_none()
    # Defensive: if the book was soft-deleted mid-loan, we still complete the
    # return — counter adjust is a no-op because available_copies clamps to
    # total_copies below.
    loan.status = LoanStatus.RETURNED
    loan.returned_at = datetime.now(timezone.utc)
    if book:
        book.available_copies = min(book.total_copies, book.available_copies + 1)
    await db.flush()
    borrower = (await db.execute(
        select(User).where(User.id == loan.borrower_user_id)
    )).scalar_one_or_none()
    return _loan_dict(loan, book=book, borrower=borrower)


@router.get("/stats", dependencies=[_can_read])
async def library_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Small set of counters for the library dashboard header strip."""
    org_id = current_user.org_id
    total_books = (await db.execute(
        select(func.count(LibraryBook.id)).where(
            LibraryBook.org_id == org_id,
            LibraryBook.is_deleted == False,
        )
    )).scalar_one() or 0
    total_copies = (await db.execute(
        select(func.coalesce(func.sum(LibraryBook.total_copies), 0)).where(
            LibraryBook.org_id == org_id,
            LibraryBook.is_deleted == False,
        )
    )).scalar_one() or 0
    loans_out = (await db.execute(
        select(func.count(LibraryLoan.id)).where(
            LibraryLoan.org_id == org_id,
            LibraryLoan.status == LoanStatus.BORROWED,
        )
    )).scalar_one() or 0
    overdue = (await db.execute(
        select(func.count(LibraryLoan.id)).where(
            LibraryLoan.org_id == org_id,
            LibraryLoan.status == LoanStatus.BORROWED,
            LibraryLoan.due_date < date.today(),
        )
    )).scalar_one() or 0
    return {
        "total_books": int(total_books),
        "total_copies": int(total_copies),
        "loans_out": int(loans_out),
        "overdue": int(overdue),
    }


# ── Library Setup: settings + categories + locations ───────────────────────────────

async def _get_or_create_library_settings(db, org_id) -> LibrarySettings:
    s = (await db.execute(select(LibrarySettings).where(LibrarySettings.org_id == org_id))).scalar_one_or_none()
    if not s:
        s = LibrarySettings(org_id=org_id)
        db.add(s)
        await db.flush()
    return s


def _settings_dict(s: LibrarySettings) -> dict:
    return {
        "loan_period_days": s.loan_period_days, "max_books_per_user": s.max_books_per_user,
        "allow_reviews": s.allow_reviews, "review_needs_approval": s.review_needs_approval, "org_id": s.org_id,
    }


@router.get("/settings", response_model=LibrarySettingsResponse, dependencies=[_can_read])
async def get_library_settings(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return _settings_dict(await _get_or_create_library_settings(db, current_user.org_id))


@router.put("/settings", response_model=LibrarySettingsResponse, dependencies=[_can_write])
async def update_library_settings(payload: LibrarySettingsUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _get_or_create_library_settings(db, current_user.org_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    await db.flush()
    return _settings_dict(s)


@router.get("/categories", response_model=list[LibraryCategoryResponse], dependencies=[_can_read])
async def list_library_categories(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(LibraryCategory).where(
        LibraryCategory.org_id == current_user.org_id).order_by(LibraryCategory.name))).scalars().all()
    return [{"id": c.id, "name": c.name, "org_id": c.org_id} for c in rows]


@router.post("/categories", response_model=LibraryCategoryResponse, status_code=201, dependencies=[_can_write])
async def create_library_category(payload: LibraryCategoryCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = LibraryCategory(name=payload.name.strip(), org_id=current_user.org_id)
    db.add(c)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(409, detail="A category with that name already exists.")
    return {"id": c.id, "name": c.name, "org_id": c.org_id}


@router.delete("/categories/{category_id}", status_code=204, dependencies=[_can_write])
async def delete_library_category(category_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = (await db.execute(select(LibraryCategory).where(
        LibraryCategory.id == category_id, LibraryCategory.org_id == current_user.org_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(404, detail="Category not found.")
    await db.delete(c)
    await db.flush()


@router.get("/locations", response_model=list[LibraryLocationResponse], dependencies=[_can_read])
async def list_library_locations(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(LibraryLocation).where(
        LibraryLocation.org_id == current_user.org_id).order_by(LibraryLocation.name))).scalars().all()
    return [{"id": r.id, "name": r.name, "code": r.code, "org_id": r.org_id} for r in rows]


@router.post("/locations", response_model=LibraryLocationResponse, status_code=201, dependencies=[_can_write])
async def create_library_location(payload: LibraryLocationCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    loc = LibraryLocation(name=payload.name.strip(), code=(payload.code or None), org_id=current_user.org_id)
    db.add(loc)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(409, detail="A location with that name already exists.")
    return {"id": loc.id, "name": loc.name, "code": loc.code, "org_id": loc.org_id}


@router.delete("/locations/{location_id}", status_code=204, dependencies=[_can_write])
async def delete_library_location(location_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    loc = (await db.execute(select(LibraryLocation).where(
        LibraryLocation.id == location_id, LibraryLocation.org_id == current_user.org_id))).scalar_one_or_none()
    if not loc:
        raise HTTPException(404, detail="Location not found.")
    await db.delete(loc)
    await db.flush()


# ── Manage Reviews (moderated reader reviews) ──────────────────────────────────────

async def _review_dict(db, r: BookReview, book_title: str | None = None, reviewer_name: str | None = None) -> dict:
    return {
        "id": r.id, "book_id": r.book_id, "book_title": book_title,
        "reviewer_id": r.reviewer_id, "reviewer_name": reviewer_name, "rating": r.rating,
        "comment": r.comment, "status": r.status.value if hasattr(r.status, "value") else r.status,
        "created_at": r.created_at, "org_id": r.org_id,
    }


@router.get("/reviews", response_model=list[ReviewResponse], dependencies=[_can_read])
async def list_reviews(
    status: str | None = Query(default=None),
    book_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Reviews for moderation (Manage Reviews). Non-admins only ever see approved
    reviews (the public set); admins/librarians see every status for moderation."""
    org_id = current_user.org_id
    q = select(BookReview).where(BookReview.org_id == org_id)
    if not _is_admin(current_user):
        q = q.where(BookReview.status == ReviewStatus.APPROVED)
    elif status in ("pending", "approved", "rejected"):
        q = q.where(BookReview.status == ReviewStatus(status))
    if book_id:
        q = q.where(BookReview.book_id == book_id)
    rows = (await db.execute(q.order_by(BookReview.created_at.desc()))).scalars().all()
    books = {b.id: b.title for b in (await db.execute(select(LibraryBook).where(LibraryBook.id.in_({r.book_id for r in rows})))).scalars().all()} if rows else {}
    names = {u.id: u.full_name for u in (await db.execute(select(User).where(User.id.in_({r.reviewer_id for r in rows if r.reviewer_id})))).scalars().all()} if rows else {}
    return [await _review_dict(db, r, books.get(r.book_id), names.get(r.reviewer_id)) for r in rows]


@router.post("/reviews", response_model=ReviewResponse, status_code=201, dependencies=[_can_read])
async def create_review(payload: ReviewCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Any member with library read may submit a review. Auto-approves unless the
    school requires moderation (Library Setup)."""
    org_id = current_user.org_id
    settings = await _get_or_create_library_settings(db, org_id)
    if not settings.allow_reviews:
        raise HTTPException(403, detail="Reviews are disabled for this library.")
    book = await _load_book_or_404(db, payload.book_id, current_user)
    status = ReviewStatus.PENDING if settings.review_needs_approval else ReviewStatus.APPROVED
    r = BookReview(book_id=book.id, reviewer_id=current_user.id, rating=payload.rating,
                   comment=(payload.comment or None), status=status, org_id=org_id)
    db.add(r)
    await db.flush()
    return await _review_dict(db, r, book.title, current_user.full_name)


@router.patch("/reviews/{review_id}", response_model=ReviewResponse, dependencies=[_can_write])
async def moderate_review(review_id: str, payload: ReviewModerate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.status not in ("pending", "approved", "rejected"):
        raise HTTPException(422, detail="status must be pending, approved or rejected.")
    r = (await db.execute(select(BookReview).where(
        BookReview.id == review_id, BookReview.org_id == current_user.org_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(404, detail="Review not found.")
    r.status = ReviewStatus(payload.status)
    await db.flush()
    return await _review_dict(db, r)


@router.delete("/reviews/{review_id}", status_code=204, dependencies=[_can_write])
async def delete_review(review_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = (await db.execute(select(BookReview).where(
        BookReview.id == review_id, BookReview.org_id == current_user.org_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(404, detail="Review not found.")
    await db.delete(r)
    await db.flush()


# ── Bulk import (CSV / Excel / Word / PDF) ─────────────────────────────────────────

@router.post("/books/import", dependencies=[_can_write])
async def import_books(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Bulk-import books from a CSV, Excel (.xlsx), Word (.docx) or PDF. Word/PDF
    must contain a table whose first row is the column headers. Columns
    (case-insensitive): title, author, isbn, category, publisher, publication_year,
    shelf_location, total_copies, description. Rows missing title/author are skipped."""
    content = await file.read()
    try:
        parsed = rows_from_upload(file.filename or "", content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    imported = 0
    errors: list[str] = []
    for i, raw in enumerate(parsed, start=2):
        row = {(k or "").strip().lower(): (v or "") for k, v in raw.items()}
        title = (row.get("title") or "").strip()
        author = (row.get("author") or "").strip()
        if not title or not author:
            errors.append(f"row {i}: missing title/author")
            continue
        try:
            copies = max(int(float(row.get("total_copies") or 1)), 1)
        except (ValueError, TypeError):
            copies = 1
        try:
            year = int(float(row["publication_year"])) if (row.get("publication_year") or "").strip() else None
        except (ValueError, TypeError):
            year = None
        db.add(LibraryBook(
            title=title, author=author,
            isbn=(row.get("isbn") or "").strip() or None,
            category=(row.get("category") or "").strip() or None,
            publisher=(row.get("publisher") or "").strip() or None,
            publication_year=year,
            shelf_location=(row.get("shelf_location") or row.get("shelf") or "").strip() or None,
            total_copies=copies, available_copies=copies,
            description=(row.get("description") or "").strip() or None,
            org_id=current_user.org_id,
        ))
        imported += 1
    await db.flush()
    return {"imported": imported, "errors": errors[:20]}
