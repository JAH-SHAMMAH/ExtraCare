"""The entry grid can be scoped to one sub-term, like the rest of the pipeline.

report_broadsheet and report_card have always taken a sub_term_id. The entry
grid was the one stage that could not, so a term carrying both a Half-Term and a
Full-Term assessment put both in front of the teacher at once, as two columns
distinguishable only by the label added in 9b6bc4a.

The parameter is OPTIONAL on purpose. Omitting it returns the whole term, which
is exactly what the grid did before, so nothing that already calls this endpoint
changes behaviour. That backward compatibility is asserted here rather than
assumed, because the admin Report Entry page and this teacher page share the
endpoint and they were updated in the same change.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, Assessment,
)
from app.models.modules.school import SchoolClass, Student, Subject
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.platform import report_entry_grid

TERM = "Term 1"


async def _admin(db, org) -> User:
    role = Role(id=str(uuid.uuid4()), name="admin", slug=f"a-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["org_admin"]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@example.com",
             full_name="Admin", status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _fixture(db, org):
    """A class and subject, plus the SAME assessment name in two sub-terms —
    the collision the sub-term selector exists to resolve."""
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="Secondary", org_id=org.id)
    subj = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    term = AcademicTerm(id=str(uuid.uuid4()), name=TERM, org_id=org.id)
    half = AcademicSubTerm(id=str(uuid.uuid4()), name="Half-Term", org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", org_id=org.id)
    db.add_all([cls, subj, term, half, full])
    await db.commit()

    a_half = Assessment(id=str(uuid.uuid4()), name="EXAM", max_score=100,
                        term_id=term.id, sub_term_id=half.id, org_id=org.id)
    a_full = Assessment(id=str(uuid.uuid4()), name="EXAM", max_score=100,
                        term_id=term.id, sub_term_id=full.id, org_id=org.id)
    stu = Student(id=str(uuid.uuid4()), student_id="S-1", first_name="A", last_name="B",
                  class_id=cls.id, org_id=org.id)
    db.add_all([a_half, a_full, stu])
    await db.commit()
    return cls, subj, term, half, full, a_half, a_full


async def _grid(db, user, cls, subj, term, sub_term_id=None):
    return await report_entry_grid(
        class_id=cls.id, subject_id=subj.id, term_id=term.id,
        sub_term_id=sub_term_id, db=db, current_user=user,
    )


@pytest.mark.asyncio
async def test_without_a_sub_term_the_grid_is_unchanged(db, org):
    """Backward compatibility, asserted. Any caller that does not pass one — and
    every caller predating this change — still sees the whole term."""
    cls, subj, term, _, _, _, _ = await _fixture(db, org)
    admin = await _admin(db, org)

    g = await _grid(db, admin, cls, subj, term)
    assert len(g.assessments) == 2, "omitting sub_term_id must not filter anything"


@pytest.mark.asyncio
async def test_a_sub_term_narrows_the_grid_to_that_sub_term(db, org):
    cls, subj, term, half, full, a_half, a_full = await _fixture(db, org)
    admin = await _admin(db, org)

    g = await _grid(db, admin, cls, subj, term, sub_term_id=half.id)
    assert [a.id for a in g.assessments] == [a_half.id]
    assert g.assessments[0].sub_term_name == "Half-Term"

    g = await _grid(db, admin, cls, subj, term, sub_term_id=full.id)
    assert [a.id for a in g.assessments] == [a_full.id]
    assert g.assessments[0].sub_term_name == "Full-Term"


@pytest.mark.asyncio
async def test_a_sub_term_with_no_assessments_yields_an_empty_grid_not_an_error(db, org):
    """Fairview today has assessments in Full-Term only, so picking Half-Term is a
    real and immediate case. It must be an empty grid the page can explain, not a
    404 or a fallback to showing everything."""
    cls, subj, term, half, full, _, a_full = await _fixture(db, org)
    await db.delete((await db.execute(
        select(Assessment).where(Assessment.sub_term_id == half.id)
    )).scalars().one())
    await db.commit()
    admin = await _admin(db, org)

    g = await _grid(db, admin, cls, subj, term, sub_term_id=half.id)
    assert g.assessments == []
    assert len(g.students) == 1, "the class still loads; only the columns are gone"


@pytest.mark.asyncio
async def test_an_unknown_sub_term_returns_nothing_rather_than_everything(db, org):
    """Failing open here would silently undo the filter — the teacher would think
    they had scoped the grid when they had not."""
    cls, subj, term, _, _, _, _ = await _fixture(db, org)
    admin = await _admin(db, org)

    g = await _grid(db, admin, cls, subj, term, sub_term_id=str(uuid.uuid4()))
    assert g.assessments == []


@pytest.mark.asyncio
async def test_sub_term_filtering_still_respects_year_group_scoping(db, org):
    """The two filters compose: sub-term narrowing must not bypass the existing
    level rule, or a teacher would be shown another level's assessment."""
    cls, subj, term, half, full, _, a_full = await _fixture(db, org)
    db.add(Assessment(id=str(uuid.uuid4()), name="PRIMARY ONLY", max_score=100,
                      term_id=term.id, sub_term_id=full.id, year_group="Primary",
                      org_id=org.id))
    await db.commit()
    admin = await _admin(db, org)

    g = await _grid(db, admin, cls, subj, term, sub_term_id=full.id)
    names = [a.name for a in g.assessments]
    assert "PRIMARY ONLY" not in names, "year_group scoping was bypassed"
    assert names == ["EXAM"]


@pytest.mark.asyncio
async def test_scores_already_entered_survive_the_narrowing(db, org):
    """Filtering changes which columns are shown, never which marks exist."""
    from app.models.modules.platform import StudentAssessmentScore

    cls, subj, term, half, full, a_half, a_full = await _fixture(db, org)
    stu = (await db.execute(select(Student))).scalars().one()
    db.add(StudentAssessmentScore(id=str(uuid.uuid4()), student_id=stu.id,
                                  subject_id=subj.id, assessment_id=a_half.id,
                                  score=71, org_id=org.id))
    await db.commit()
    admin = await _admin(db, org)

    # Hidden while viewing Full-Term...
    g = await _grid(db, admin, cls, subj, term, sub_term_id=full.id)
    assert a_half.id not in (g.scores.get(stu.id) or {})

    # ...and still there when viewing Half-Term.
    g = await _grid(db, admin, cls, subj, term, sub_term_id=half.id)
    assert float(g.scores[stu.id][a_half.id]) == 71.0
