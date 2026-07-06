"""
Library coverage — loan lifecycle + tenant isolation.

Success (issue decrements available_copies, return increments) plus forbidden/
validation paths: no copies available (409), cross-tenant borrower (404), and a
double-return (409).
"""

import uuid
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.organization import Organization, IndustryType
from app.models.user import User, UserStatus
from app.models.modules.school import LibraryBook
from app.routers.modules.library import issue_loan, return_loan

pytestmark = pytest.mark.asyncio


async def _book(db, org, copies=2):
    b = LibraryBook(
        id=str(uuid.uuid4()), title="Python 101", author="A. Author",
        total_copies=copies, available_copies=copies, org_id=org.id,
    )
    db.add(b)
    await db.flush()
    return b


def _future_due(days=14):
    return (date.today() + timedelta(days=days)).isoformat()


async def test_issue_loan_decrements_available(db, org, teacher):
    book = await _book(db, org, copies=2)
    await issue_loan(
        payload={"book_id": book.id, "borrower_user_id": teacher.id, "due_date": _future_due()},
        db=db, current_user=teacher,
    )
    b = (await db.execute(select(LibraryBook).where(LibraryBook.id == book.id))).scalar_one()
    assert b.available_copies == 1


async def test_issue_loan_no_copies_409(db, org, teacher):
    book = await _book(db, org, copies=0)
    with pytest.raises(HTTPException) as ei:
        await issue_loan(
            payload={"book_id": book.id, "borrower_user_id": teacher.id, "due_date": _future_due()},
            db=db, current_user=teacher,
        )
    assert ei.value.status_code == 409


async def test_issue_loan_cross_tenant_borrower_404(db, org, teacher):
    book = await _book(db, org, copies=2)
    other = Organization(
        id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:8]}",
        industry=IndustryType.SCHOOL, modules_enabled=["school"],
    )
    db.add(other)
    await db.flush()
    foreign_user = User(
        id=str(uuid.uuid4()), email="x@x.example.com", full_name="X",
        status=UserStatus.ACTIVE, org_id=other.id,
    )
    db.add(foreign_user)
    await db.flush()
    with pytest.raises(HTTPException) as ei:
        await issue_loan(
            payload={"book_id": book.id, "borrower_user_id": foreign_user.id, "due_date": _future_due()},
            db=db, current_user=teacher,
        )
    assert ei.value.status_code == 404


async def test_return_increments_and_double_return_409(db, org, teacher):
    book = await _book(db, org, copies=1)
    loan = await issue_loan(
        payload={"book_id": book.id, "borrower_user_id": teacher.id, "due_date": _future_due()},
        db=db, current_user=teacher,
    )
    await return_loan(loan_id=loan["id"], db=db, current_user=teacher)
    b = (await db.execute(select(LibraryBook).where(LibraryBook.id == book.id))).scalar_one()
    assert b.available_copies == 1
    with pytest.raises(HTTPException) as ei:
        await return_loan(loan_id=loan["id"], db=db, current_user=teacher)
    assert ei.value.status_code == 409
