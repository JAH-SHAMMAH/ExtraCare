"""Two races that were real, reproduced and now guarded.

These need their own engine: the shared `db` fixture is a single in-memory
session, and a race needs two sessions over shared storage — one per simulated
request, exactly as get_db() hands one to each. So each test builds a file-backed
SQLite database under tmp_path.

Both tests fail without their fix — that was checked, not assumed. A concurrency
test that passes either way is worse than none, because it certifies the bug.

Fidelity note: SQLite serialises writers more aggressively than Postgres, so a
race that reproduces here reproduces there too; the window is wider in
production, not narrower.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.database import Base
from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, Assessment, StudentAssessmentScore,
)
from app.models.modules.school import (
    AttemptStatus, CBTAnswer, CBTAttempt, CBTExam, CBTQuestion, ExamStatus,
    QuestionType, SchoolClass, Student, Subject,
)
from app.models.organization import Organization, IndustryType
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus


class _SlowSession(AsyncSession):
    """Pauses right after the statement naming `pause_on`, to hold one request in
    its read->write gap while another completes. Widening the window is the only
    way to hit an interleaving reliably rather than hoping the scheduler obliges.
    """
    pause_on = ""
    pause_secs = 0.0
    _paused = False

    async def execute(self, *a, **kw):
        r = await super().execute(*a, **kw)
        if not self._paused and self.pause_secs and self.pause_on in str(a[0]).lower():
            self._paused = True
            await asyncio.sleep(self.pause_secs)
        return r


@pytest.fixture
async def races(tmp_path):
    """(Session, SlowSession, ids) over a file-backed database two sessions share."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'races.sqlite'}")
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    Slow = async_sessionmaker(engine, class_=_SlowSession, expire_on_commit=False)

    async with Session() as db:
        org = Organization(id=str(uuid.uuid4()), name="T", slug=f"t-{uuid.uuid4().hex[:8]}",
                           industry=IndustryType.SCHOOL, modules_enabled=["school"])
        db.add(org)
        await db.commit()
        cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="Secondary", org_id=org.id)
        subj = Subject(id=str(uuid.uuid4()), name="Maths", org_id=org.id)
        term = AcademicTerm(id=str(uuid.uuid4()), name="Term 1", org_id=org.id)
        sub = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", org_id=org.id)
        db.add_all([cls, subj, term, sub])
        await db.commit()

        email = f"p-{uuid.uuid4().hex[:6]}@example.com"
        srole = Role(id=str(uuid.uuid4()), name="student", slug=f"s-{uuid.uuid4().hex[:6]}",
                     permissions=list(SCHOOL_PERMISSION_PRESETS["student"]), org_id=org.id,
                     is_system=False)
        su = User(id=str(uuid.uuid4()), email=email, full_name="P",
                  status=UserStatus.ACTIVE, org_id=org.id)
        su.roles = [srole]
        stu = Student(id=str(uuid.uuid4()), student_id="S-1", first_name="A", last_name="B",
                      email=email, user_id=su.id, class_id=cls.id, org_id=org.id)
        arole = Role(id=str(uuid.uuid4()), name="admin", slug=f"a-{uuid.uuid4().hex[:6]}",
                     permissions=list(SCHOOL_PERMISSION_PRESETS["org_admin"]), org_id=org.id,
                     is_system=False)
        au = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@example.com",
                  full_name="Ad", status=UserStatus.ACTIVE, org_id=org.id)
        au.roles = [arole]
        a = Assessment(id=str(uuid.uuid4()), name="EXAM", max_score=100, term_id=term.id,
                       sub_term_id=sub.id, org_id=org.id)
        db.add_all([srole, su, stu, arole, au, a])
        await db.commit()
        ids = dict(org=org.id, cls=cls.id, subj=subj.id, stu=stu.id,
                   stu_user=su.id, admin=au.id, assessment=a.id)
    try:
        yield Session, Slow, ids
    finally:
        await engine.dispose()


async def _user(db, uid):
    return (await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == uid)
    )).scalar_one()


# ── CBT double-submit ─────────────────────────────────────────────────────────

async def test_simultaneous_submits_produce_one_graded_attempt(races):
    """Both requests pass the IN_PROGRESS check before either writes. Only the one
    that wins the conditional UPDATE may go on to record answers."""
    from app.routers.modules.cbt import submit_attempt
    from app.schemas.school_experience import AttemptSubmit, AttemptAnswerInput

    Session, _Slow, ids = races
    async with Session() as db:
        exam = CBTExam(id=str(uuid.uuid4()), title="Quiz", status=ExamStatus.PUBLISHED,
                       total_points=2.0, duration_minutes=60, subject_id=ids["subj"],
                       class_id=ids["cls"], term="Term 1", created_by=ids["admin"],
                       org_id=ids["org"])
        db.add(exam)
        await db.flush()
        q = CBTQuestion(id=str(uuid.uuid4()), exam_id=exam.id, question_text="2+2?",
                        question_type=QuestionType.MCQ, correct_answer="4", points=2.0,
                        org_id=ids["org"])
        att = CBTAttempt(id=str(uuid.uuid4()), exam_id=exam.id, student_id=ids["stu"],
                         status=AttemptStatus.IN_PROGRESS, max_score=2.0,
                         started_at=datetime.now(timezone.utc), org_id=ids["org"])
        db.add_all([q, att])
        await db.commit()
        q_id, att_id = q.id, att.id

    payload = AttemptSubmit(answers=[AttemptAnswerInput(question_id=q_id, answer_text="4")])

    async def submit():
        async with Session() as db:
            try:
                out = await submit_attempt(att_id, payload, db=db,
                                           current_user=await _user(db, ids["stu_user"]))
                await db.commit()
                return ("accepted", out["score"])
            except HTTPException as e:
                return ("rejected", e.status_code)

    results = await asyncio.gather(submit(), submit())
    accepted = [r for r in results if r[0] == "accepted"]
    rejected = [r for r in results if r[0] == "rejected"]

    assert len(accepted) == 1, f"expected exactly one accepted submit, got {results}"
    assert rejected[0][1] == 400

    async with Session() as db:
        n = (await db.execute(select(func.count()).select_from(CBTAnswer)
                              .where(CBTAnswer.attempt_id == att_id))).scalar()
        att = (await db.execute(select(CBTAttempt).where(CBTAttempt.id == att_id))).scalar_one()
    assert n == 1, f"one question answered once, but {n} CBTAnswer rows exist"
    assert att.status == AttemptStatus.GRADED
    assert att.score == 2.0


async def test_a_repeated_question_in_one_payload_stores_one_answer(races):
    """The other route to duplicates: the same question twice in a single submit."""
    from app.routers.modules.cbt import submit_attempt
    from app.schemas.school_experience import AttemptSubmit, AttemptAnswerInput

    Session, _Slow, ids = races
    async with Session() as db:
        exam = CBTExam(id=str(uuid.uuid4()), title="Quiz", status=ExamStatus.PUBLISHED,
                       total_points=2.0, duration_minutes=60, subject_id=ids["subj"],
                       class_id=ids["cls"], term="Term 1", created_by=ids["admin"],
                       org_id=ids["org"])
        db.add(exam)
        await db.flush()
        q = CBTQuestion(id=str(uuid.uuid4()), exam_id=exam.id, question_text="2+2?",
                        question_type=QuestionType.MCQ, correct_answer="4", points=2.0,
                        org_id=ids["org"])
        att = CBTAttempt(id=str(uuid.uuid4()), exam_id=exam.id, student_id=ids["stu"],
                         status=AttemptStatus.IN_PROGRESS, max_score=2.0,
                         started_at=datetime.now(timezone.utc), org_id=ids["org"])
        db.add_all([q, att])
        await db.commit()
        q_id, att_id = q.id, att.id

    async with Session() as db:
        await submit_attempt(
            att_id,
            AttemptSubmit(answers=[
                AttemptAnswerInput(question_id=q_id, answer_text="9"),   # superseded
                AttemptAnswerInput(question_id=q_id, answer_text="4"),   # last wins
            ]),
            db=db, current_user=await _user(db, ids["stu_user"]))
        await db.commit()

    async with Session() as db:
        rows = (await db.execute(select(CBTAnswer).where(CBTAnswer.attempt_id == att_id))).scalars().all()
    assert len(rows) == 1
    assert rows[0].answer_text == "4" and rows[0].is_correct is True


# ── Concurrent report-entry saves ─────────────────────────────────────────────

async def test_concurrent_first_saves_do_not_500(races):
    """Two teachers saving the same empty cell at once. The loser's INSERT hits
    uq_student_assessment_score; it must recover into an update, not surface as a
    500 with the marks unsaved."""
    from app.routers.modules.platform import save_report_entry
    from app.schemas.platform import ReportEntrySave, ScoreItem

    Session, Slow, ids = races

    async def save(score, slow):
        maker = Slow if slow else Session
        async with maker() as db:
            if slow:
                # Hold this request between reading "no row exists" and writing.
                db.pause_on, db.pause_secs = "student_assessment_scores", 0.6
            out = await save_report_entry(
                ReportEntrySave(subject_id=ids["subj"], class_id=ids["cls"],
                                items=[ScoreItem(student_id=ids["stu"],
                                                 assessment_id=ids["assessment"],
                                                 score=score)]),
                db=db, current_user=await _user(db, ids["admin"]))
            await db.commit()
            return out

    results = await asyncio.gather(save(40, True), save(90, False))
    assert all(r["saved"] == 1 for r in results), results

    async with Session() as db:
        rows = (await db.execute(select(StudentAssessmentScore))).scalars().all()
    assert len(rows) == 1, f"unique constraint should leave exactly one row, got {len(rows)}"
    assert float(rows[0].score) in (40.0, 90.0)   # last writer wins; either is valid


async def test_a_collision_does_not_lose_the_rest_of_the_batch(races):
    """The recovery is per row, inside a SAVEPOINT — one contended cell must not
    roll back the other marks saved in the same request."""
    from app.routers.modules.platform import save_report_entry
    from app.schemas.platform import ReportEntrySave, ScoreItem

    Session, Slow, ids = races
    async with Session() as db:
        other = Student(id=str(uuid.uuid4()), student_id="S-2", first_name="C", last_name="D",
                        class_id=ids["cls"], org_id=ids["org"])
        db.add(other)
        await db.commit()
        other_id = other.id

    async def contended():
        async with Session() as db:
            await save_report_entry(
                ReportEntrySave(subject_id=ids["subj"], class_id=ids["cls"],
                                items=[ScoreItem(student_id=ids["stu"],
                                                 assessment_id=ids["assessment"], score=90)]),
                db=db, current_user=await _user(db, ids["admin"]))
            await db.commit()

    async def batch():
        async with Slow() as db:
            db.pause_on, db.pause_secs = "student_assessment_scores", 0.6
            out = await save_report_entry(
                ReportEntrySave(subject_id=ids["subj"], class_id=ids["cls"], items=[
                    ScoreItem(student_id=ids["stu"], assessment_id=ids["assessment"], score=40),
                    ScoreItem(student_id=other_id, assessment_id=ids["assessment"], score=77),
                ]),
                db=db, current_user=await _user(db, ids["admin"]))
            await db.commit()
            return out

    batch_out, _ = await asyncio.gather(batch(), contended())
    assert batch_out["saved"] == 2

    async with Session() as db:
        rows = {r.student_id: float(r.score)
                for r in (await db.execute(select(StudentAssessmentScore))).scalars().all()}
    assert len(rows) == 2
    assert rows[other_id] == 77.0        # the uncontended mark survived


@pytest.mark.parametrize("n_writers", [3, 5])
async def test_many_simultaneous_first_saves_all_recover(races, n_writers):
    """The recovery has to hold for N contenders, not just two.

    With N requests all reading "no row exists", one INSERT wins and the other
    N-1 each take the IntegrityError path. Each recovers independently — the
    losers do not collide with EACH OTHER, because by the time any of them
    re-reads, the winning row is committed and they take the update branch.
    Staggered starts widen the pile-up rather than letting the scheduler
    serialise them by luck.
    """
    from app.routers.modules.platform import save_report_entry
    from app.schemas.platform import ReportEntrySave, ScoreItem

    Session, Slow, ids = races

    async def save(score, delay):
        await asyncio.sleep(delay)
        async with Slow() as db:
            # Every writer holds its stale read, so they all reach the write
            # phase believing the cell is empty.
            db.pause_on, db.pause_secs = "student_assessment_scores", 0.5
            out = await save_report_entry(
                ReportEntrySave(subject_id=ids["subj"], class_id=ids["cls"],
                                items=[ScoreItem(student_id=ids["stu"],
                                                 assessment_id=ids["assessment"],
                                                 score=score)]),
                db=db, current_user=await _user(db, ids["admin"]))
            await db.commit()
            return out

    scores = [10 * (i + 1) for i in range(n_writers)]
    results = await asyncio.gather(
        *[save(sc, i * 0.05) for i, sc in enumerate(scores)],
        return_exceptions=True,
    )
    failures = [r for r in results if isinstance(r, BaseException)]
    assert not failures, f"{len(failures)} of {n_writers} writers raised: {failures[:2]}"
    assert all(r["saved"] == 1 for r in results), results

    async with Session() as db:
        rows = (await db.execute(select(StudentAssessmentScore))).scalars().all()
    assert len(rows) == 1, f"expected one row after {n_writers} writers, got {len(rows)}"
    assert float(rows[0].score) in scores      # some writer's value, intact
