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

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.modules.school import LibraryBook, LibraryLoan, LoanStatus, Student
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker


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
    required = ("book_id", "borrower_user_id", "due_date")
    missing = [k for k in required if not str(payload.get(k) or "").strip()]
    if missing:
        raise HTTPException(422, detail=f"Missing required fields: {', '.join(missing)}")
    try:
        due_date = date.fromisoformat(str(payload["due_date"]))
    except (TypeError, ValueError):
        raise HTTPException(422, detail="due_date must be YYYY-MM-DD")
    if due_date < date.today():
        raise HTTPException(422, detail="due_date must be today or later")

    book = await _load_book_or_404(db, str(payload["book_id"]), current_user)
    if book.available_copies < 1:
        raise HTTPException(409, detail=f"No copies available for '{book.title}'")

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
