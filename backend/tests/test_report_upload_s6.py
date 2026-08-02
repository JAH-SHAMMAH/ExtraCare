"""Secondary Report parity S-6: Reports Upload (bulk score import)."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.models.user import User, UserStatus
from app.models.modules.school import Subject, SchoolClass, Student
from app.models.modules.platform import AcademicTerm, AcademicSubTerm
from app.routers.modules.platform import (
    bootstrap_assessments, bootstrap_cumulatives, report_upload, report_card, list_assessments,
)


pytestmark = pytest.mark.asyncio


class _Upload:
    def __init__(self, filename, content):
        self.filename = filename
        self._content = content

    async def read(self):
        return self._content


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Officer",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def test_report_upload(db, org):
    admin = await _admin(db, org)
    autumn = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    half = AcademicSubTerm(id=str(uuid.uuid4()), name="Half-Term", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    cls = SchoolClass(id=str(uuid.uuid4()), name="Year 10", level="YEAR 10", org_id=org.id)
    maths = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    ada = Student(id=str(uuid.uuid4()), student_id="FS/1", first_name="Ada", last_name="Obi", class_id=cls.id, org_id=org.id)
    db.add_all([autumn, half, full, cls, maths, ada])
    await db.commit()
    await bootstrap_assessments(db=db, current_user=admin)
    await bootstrap_cumulatives(db=db, current_user=admin)

    csv = ("admission_no,student,subject,CBT,THEORY,PRJ,PBT,EXAM\n"
           "FS/1,Ada Obi,Mathematics,20,20,10,10,60\n"          # matched by admission -> full marks
           "NOPE,Ghost,Mathematics,10,10,10,10,10\n"            # unknown student
           "FS/1,Ada Obi,Biology,5,5,5,5,5\n").encode()          # unknown subject
    res = await report_upload(term_id=autumn.id, file=_Upload("scores.csv", csv), db=db, current_user=admin)
    assert res.rows == 3 and res.imported == 1 and len(res.errors) == 2

    # The imported marks flow through the engine to a full-marks card.
    card = await report_card(student_id=ada.id, term_id=autumn.id, sub_term_id=full.id, db=db, current_user=admin)
    row = next(r for r in card.subjects if r.subject_name == "Mathematics")
    total_col = next(c for c in card.columns if c.name == "TOTAL")
    assert row.values[total_col.key] == Decimal("100")

    # Re-upload updates in place (no duplicate rows, score changes).
    csv2 = ("admission_no,subject,EXAM\nFS/1,Mathematics,40\n").encode()
    res2 = await report_upload(term_id=autumn.id, file=_Upload("scores.csv", csv2), db=db, current_user=admin)
    assert res2.imported == 1
    card2 = await report_card(student_id=ada.id, term_id=autumn.id, sub_term_id=full.id, db=db, current_user=admin)
    row2 = next(r for r in card2.subjects if r.subject_name == "Mathematics")
    assert row2.values[total_col.key] == Decimal("80")   # EXAM 60 -> 40 lowers TOTAL 100 -> 80
