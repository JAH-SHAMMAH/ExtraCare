"""Secondary Report parity S-4d: Head/PC comment grids + wired into the card."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.modules.school import Subject, SchoolClass, Student
from app.models.modules.platform import AcademicTerm, AcademicSubTerm
from app.routers.modules.platform import (
    bootstrap_assessments, bootstrap_cumulatives, list_assessments, save_report_entry,
    report_comment_grid, save_report_comments, report_card,
)
from app.schemas.platform import ReportEntrySave, ScoreItem, CommentGridSave, CommentItem


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Head",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def test_comment_grid_and_card_wiring(db, org):
    admin = await _admin(db, org)
    autumn = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    half = AcademicSubTerm(id=str(uuid.uuid4()), name="Half-Term", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    cls = SchoolClass(id=str(uuid.uuid4()), name="Year 10", level="YEAR 10", org_id=org.id)
    maths = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    s1 = Student(id=str(uuid.uuid4()), student_id="FS/1", first_name="Ada", last_name="Obi", class_id=cls.id, org_id=org.id)
    db.add_all([autumn, half, full, cls, maths, s1])
    await db.commit()
    await bootstrap_assessments(db=db, current_user=admin)
    await bootstrap_cumulatives(db=db, current_user=admin)
    A = {a.name: a for a in await list_assessments(term_id=autumn.id, db=db, current_user=admin)}
    await save_report_entry(payload=ReportEntrySave(subject_id=maths.id, items=[
        ScoreItem(student_id=s1.id, assessment_id=A["EXAM"].id, score=Decimal("50"))]), db=db, current_user=admin)

    # Empty grid first.
    grid = await report_comment_grid(class_id=cls.id, term_id=autumn.id, sub_term_id=full.id, kind="head", db=db, current_user=admin)
    assert len(grid.rows) == 1 and grid.rows[0].text is None

    # Bad kind rejected.
    with pytest.raises(HTTPException) as ei:
        await report_comment_grid(class_id=cls.id, term_id=autumn.id, sub_term_id=full.id, kind="wizard", db=db, current_user=admin)
    assert ei.value.status_code == 422

    await save_report_comments(payload=CommentGridSave(term_id=autumn.id, sub_term_id=full.id, kind="head",
                               items=[CommentItem(student_id=s1.id, text="A promising term.")]), db=db, current_user=admin)
    await save_report_comments(payload=CommentGridSave(term_id=autumn.id, sub_term_id=full.id, kind="pc",
                               items=[CommentItem(student_id=s1.id, text="Settled well pastorally.")]), db=db, current_user=admin)

    grid2 = await report_comment_grid(class_id=cls.id, term_id=autumn.id, sub_term_id=full.id, kind="head", db=db, current_user=admin)
    assert grid2.rows[0].text == "A promising term."

    # Re-save updates in place.
    await save_report_comments(payload=CommentGridSave(term_id=autumn.id, sub_term_id=full.id, kind="head",
                               items=[CommentItem(student_id=s1.id, text="An excellent term.")]), db=db, current_user=admin)
    grid3 = await report_comment_grid(class_id=cls.id, term_id=autumn.id, sub_term_id=full.id, kind="head", db=db, current_user=admin)
    assert grid3.rows[0].text == "An excellent term."

    # Card picks up both comments.
    card = await report_card(student_id=s1.id, term_id=autumn.id, sub_term_id=full.id, db=db, current_user=admin)
    assert card.head_comment == "An excellent term." and card.pc_comment == "Settled well pastorally."
