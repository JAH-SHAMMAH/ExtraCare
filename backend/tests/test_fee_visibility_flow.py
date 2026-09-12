"""What a parent can see of their child's fees, and when.

The flow: an accountant raises an invoice (draft), posts it (which writes the
balanced Dr Receivable / Cr Income entry), and only then does it appear on the
parent's payments page. Verified through the REAL handlers rather than by
inserting rows, because the thing worth protecting is the flow, not the schema.

Three properties, each of which would be a real incident if it broke:

  DRAFT GATE   a draft invoice must NOT be payable. Posting is the act that bills
               a family, so a half-finished invoice appearing on a parent's page
               would be asking for money nobody approved.
  VISIBILITY   once posted it shows with the right child, payer and amount.
  OWNERSHIP    another family never sees it, and the PUPIL never sees it either —
               a pupil has no ParentGuardian row, so they are the subject of the
               invoice, not its payer.

Worth knowing for anyone reading this later: the parent's page reads `Invoice`,
NOT `StudentFeeRecord`. StudentFeeRecord looks like the fee table and even has an
`outstanding_balance` column, but nothing parent-facing reads it — a balance
written there shows the parent nothing.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.modules.finance import JournalLine, LedgerAccount
from app.models.modules.school import ParentGuardian, SchoolClass, Student
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.finance import create_invoice, post_invoice
from app.routers.remita import my_outstanding_invoices
from app.schemas.finance import InvoiceCreate, InvoiceLineInput

FEE_LABEL = "JSS1 Term 1 Tuition"
FEE_AMOUNT = Decimal("120000.00")


async def _user(db, org, slug: str, name: str, email: str | None = None) -> User:
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=email or f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=name, status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


@pytest.fixture
async def fees(db, org):
    """A family, a second family as control, and the two accounts an invoice needs.

    Posting requires a receivable (asset) account on the invoice and an income
    account on every line — InvoiceLine.income_account_id is NOT NULL with
    ondelete=RESTRICT — so a chart of accounts has to exist before any of this
    works at all.
    """
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="JSS1", org_id=org.id)
    db.add(cls)
    await db.commit()

    parent = await _user(db, org, "parent", "Chukwuma Yusuf")
    pupil_login = await _user(db, org, "student", "Musa Yusuf")
    accountant = await _user(db, org, "accountant", "School Accountant")
    other_parent = await _user(db, org, "parent", "Someone Else")

    child = Student(id=str(uuid.uuid4()), student_id="FSN-0031", first_name="Musa",
                    last_name="Yusuf", email=pupil_login.email, user_id=pupil_login.id,
                    class_id=cls.id, org_id=org.id)
    other_child = Student(id=str(uuid.uuid4()), student_id="FSN-0099", first_name="Ngozi",
                          last_name="Okafor", class_id=cls.id, org_id=org.id)
    ar = LedgerAccount(id=str(uuid.uuid4()), code="1200", name="Accounts Receivable",
                       type="asset", org_id=org.id)
    income = LedgerAccount(id=str(uuid.uuid4()), code="4100", name="School Fees Income",
                           type="income", org_id=org.id)
    db.add_all([child, other_child, ar, income])
    await db.commit()
    db.add_all([
        ParentGuardian(id=str(uuid.uuid4()), user_id=parent.id, student_id=child.id,
                       relationship_type="parent", is_primary=True, org_id=org.id),
        ParentGuardian(id=str(uuid.uuid4()), user_id=other_parent.id,
                       student_id=other_child.id, relationship_type="parent",
                       is_primary=True, org_id=org.id),
    ])
    await db.commit()
    return dict(parent=parent, pupil_login=pupil_login, accountant=accountant,
                other_parent=other_parent, child=child, ar=ar, income=income)


async def _reload(db, u: User) -> User:
    """Roles eager-loaded, as get_current_user does in production."""
    return (await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == u.id)
    )).scalar_one()


async def _raise_invoice(db, f) -> str:
    out = await create_invoice(
        InvoiceCreate(
            customer_name="Chukwuma Yusuf", student_id=f["child"].id,
            invoice_date=date(2026, 9, 3), due_date=date(2026, 9, 30),
            memo=f"{FEE_LABEL} — Musa Yusuf (FSN-0031)",
            receivable_account_id=f["ar"].id,
            lines=[InvoiceLineInput(description=FEE_LABEL, quantity=Decimal("1"),
                                    unit_price=FEE_AMOUNT,
                                    income_account_id=f["income"].id)],
        ),
        request=None, db=db, current_user=await _reload(db, f["accountant"]))
    await db.commit()
    return out.id


# ── the draft gate ────────────────────────────────────────────────────────────

async def test_a_draft_invoice_is_not_visible_to_the_parent(db, org, fees):
    """Posting is what bills a family. A draft must bill nobody."""
    await _raise_invoice(db, fees)
    rows = await my_outstanding_invoices(db=db, current_user=await _reload(db, fees["parent"]))
    assert rows == []


# ── visibility once posted ────────────────────────────────────────────────────

async def test_posting_makes_the_balance_visible_to_the_parent(db, org, fees):
    invoice_id = await _raise_invoice(db, fees)
    posted = await post_invoice(invoice_id, request=None, db=db,
                                current_user=await _reload(db, fees["accountant"]))
    await db.commit()
    assert posted.status == "posted"

    rows = await my_outstanding_invoices(db=db, current_user=await _reload(db, fees["parent"]))
    assert len(rows) == 1
    inv = rows[0]
    assert inv.status == "posted"
    assert Decimal(str(inv.total)) == FEE_AMOUNT
    assert inv.student_name == "Musa Yusuf"          # the right child
    assert inv.student_id == fees["child"].id
    assert inv.customer_name == "Chukwuma Yusuf"     # the right payer
    assert inv.invoice_date == "2026-09-03"


async def test_posting_writes_a_balanced_double_entry(db, org, fees):
    """The invoice is backed by real accounting, not just a status flag."""
    invoice_id = await _raise_invoice(db, fees)
    await post_invoice(invoice_id, request=None, db=db,
                       current_user=await _reload(db, fees["accountant"]))
    await db.commit()

    lines = (await db.execute(select(JournalLine))).scalars().all()
    debits = sum(Decimal(str(l.debit or 0)) for l in lines)
    credits = sum(Decimal(str(l.credit or 0)) for l in lines)
    assert debits == credits == FEE_AMOUNT

    by_account = {l.account_id: l for l in lines}
    assert Decimal(str(by_account[fees["ar"].id].debit)) == FEE_AMOUNT       # Dr Receivable
    assert Decimal(str(by_account[fees["income"].id].credit)) == FEE_AMOUNT  # Cr Income


# ── ownership boundaries ──────────────────────────────────────────────────────

async def test_another_family_never_sees_the_invoice(db, org, fees):
    invoice_id = await _raise_invoice(db, fees)
    await post_invoice(invoice_id, request=None, db=db,
                       current_user=await _reload(db, fees["accountant"]))
    await db.commit()

    rows = await my_outstanding_invoices(
        db=db, current_user=await _reload(db, fees["other_parent"]))
    assert rows == []


async def test_the_pupil_does_not_see_their_own_invoice(db, org, fees):
    """A pupil is the subject of the invoice, not its payer — they hold no
    ParentGuardian row, so the children resolver returns nothing for them."""
    invoice_id = await _raise_invoice(db, fees)
    await post_invoice(invoice_id, request=None, db=db,
                       current_user=await _reload(db, fees["accountant"]))
    await db.commit()

    rows = await my_outstanding_invoices(
        db=db, current_user=await _reload(db, fees["pupil_login"]))
    assert rows == []


async def test_a_parent_with_no_children_linked_sees_nothing(db, org, fees):
    """The resolver short-circuits on an empty child list rather than querying
    every invoice in the org."""
    stranger = await _user(db, org, "parent", "No Children")
    invoice_id = await _raise_invoice(db, fees)
    await post_invoice(invoice_id, request=None, db=db,
                       current_user=await _reload(db, fees["accountant"]))
    await db.commit()

    rows = await my_outstanding_invoices(db=db, current_user=await _reload(db, stranger))
    assert rows == []
