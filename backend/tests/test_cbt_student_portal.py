"""Student exam portal: practice papers, progress, integrity events."""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.modules.school import (
    CBTAnswer, CBTAttempt, CBTExam, ExamStatus, QuestionBankItem, QuestionType,
    SchoolClass, Student, Subject,
)
from app.models.modules.platform import SchoolSection
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules import cbt as cbt_mod
from app.routers.modules import cbt_student as cs
from app.schemas.school_experience import AttemptSubmit, AttemptAnswerInput

pytestmark = pytest.mark.asyncio


async def _setup(db, org, n_bank=12):
    sec = SchoolSection(id=str(uuid.uuid4()), name=f"Sec-{uuid.uuid4().hex[:6]}", org_id=org.id)
    cls = SchoolClass(id=str(uuid.uuid4()), name="SS1", level="SS1", section_id=sec.id, org_id=org.id)
    subj = Subject(id=str(uuid.uuid4()), name="Biology", section_id=sec.id, org_id=org.id)
    email = f"p-{uuid.uuid4().hex[:6]}@x.com"
    role = Role(id=str(uuid.uuid4()), name="student", slug=f"s-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["student"]), org_id=org.id, is_system=False)
    u = User(id=str(uuid.uuid4()), email=email, full_name="Pupil", status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    st = Student(id=str(uuid.uuid4()), student_id=f"S{uuid.uuid4().hex[:4]}", first_name="P", last_name="Q",
                 email=email, user_id=u.id, class_id=cls.id, org_id=org.id)
    db.add_all([sec, cls, subj, role, u, st])
    await db.flush()
    for i in range(n_bank):
        db.add(QuestionBankItem(
            id=str(uuid.uuid4()), subject_id=subj.id, question_text=f"Q{i}?", question_type=QuestionType.MCQ,
            options=[{"key": "a", "text": "A"}, {"key": "b", "text": "B"}], correct_answer="a",
            points=1.0, org_id=org.id))
    await db.commit()
    return u, st, subj


async def test_subjects_lists_only_subjects_with_questions(db, org):
    u, st, subj = await _setup(db, org)
    db.add(Subject(id=str(uuid.uuid4()), name="Empty", section_id=subj.section_id, org_id=org.id))
    await db.commit()
    res = await cs.practice_subjects(db=db, current_user=u)
    assert [i["name"] for i in res["items"]] == ["Biology"]
    assert res["items"][0]["question_count"] == 12


async def test_practice_flow_scores_and_reviews_and_shows_in_progress(db, org):
    u, st, subj = await _setup(db, org)
    out = await cs.start_practice(cs.PracticeStart(subject_id=subj.id, count=5), db=db, current_user=u)
    exam = await cbt_mod.get_exam(out["exam_id"], db=db, current_user=u)
    assert exam["exam_type"] == "practice" and out["question_count"] == 5
    att = await cbt_mod.start_attempt(out["exam_id"], db=db, current_user=u)
    qs = (await cbt_mod.list_questions(out["exam_id"], db=db, current_user=u))["items"]
    assert "correct_answer" not in qs[0]
    answers = [AttemptAnswerInput(question_id=q["id"], answer_text="a" if i < 3 else "b") for i, q in enumerate(qs)]
    done = await cbt_mod.submit_attempt(att["id"], AttemptSubmit(answers=answers), db=db, current_user=u)
    assert done["score"] == 3.0
    rev = await cs.review_practice(att["id"], db=db, current_user=u)
    assert sum(1 for i in rev["items"] if i["is_correct"]) == 3
    assert rev["items"][0]["correct_answer"] == "a"
    prog = await cs.my_progress(db=db, current_user=u)
    assert prog["overall"]["taken"] == 1 and prog["overall"]["average"] == 60.0
    assert prog["by_type"]["practice"]["taken"] == 1
    assert prog["subjects"][0]["name"] == "Biology"


async def test_practice_is_private_and_hidden_from_lists(db, org):
    u, st, subj = await _setup(db, org)
    out = await cs.start_practice(cs.PracticeStart(subject_id=subj.id, count=5), db=db, current_user=u)
    # a classmate cannot open it
    other_email = f"o-{uuid.uuid4().hex[:6]}@x.com"
    role = Role(id=str(uuid.uuid4()), name="student", slug=f"s-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["student"]), org_id=org.id, is_system=False)
    o = User(id=str(uuid.uuid4()), email=other_email, full_name="Other", status=UserStatus.ACTIVE, org_id=org.id)
    o.roles = [role]
    db.add_all([role, o, Student(id=str(uuid.uuid4()), student_id="S9", first_name="O", last_name="O",
                                 email=other_email, user_id=o.id, class_id=st.class_id, org_id=org.id)])
    await db.commit()
    with pytest.raises(HTTPException) as e:
        await cbt_mod.get_exam(out["exam_id"], db=db, current_user=o)
    assert e.value.status_code == 404
    # and it never appears in the class's exam list
    lst = await cbt_mod.list_exams(class_id=None, status_filter=None, for_me=True, exam_type=None, page=1, page_size=25, db=db, current_user=o)
    assert lst["items"] == []


async def test_practice_needs_questions_and_respects_daily_cap(db, org, monkeypatch):
    u, st, subj = await _setup(db, org, n_bank=0)
    with pytest.raises(HTTPException) as e:
        await cs.start_practice(cs.PracticeStart(subject_id=subj.id, count=5), db=db, current_user=u)
    assert e.value.status_code == 404
    u2, _, subj2 = await _setup(db, org)
    monkeypatch.setattr(cs, "PRACTICE_DAILY_CAP", 2)
    for _ in range(2):
        await cs.start_practice(cs.PracticeStart(subject_id=subj2.id, count=5), db=db, current_user=u2)
    with pytest.raises(HTTPException) as e:
        await cs.start_practice(cs.PracticeStart(subject_id=subj2.id, count=5), db=db, current_user=u2)
    assert e.value.status_code == 429


async def test_held_school_result_is_pending_in_progress(db, org):
    u, st, subj = await _setup(db, org)
    ex = CBTExam(id=str(uuid.uuid4()), title="Mock 1", exam_type="mock", status=ExamStatus.PUBLISHED,
                 class_id=st.class_id, subject_id=subj.id, created_by=u.id, hold_results=True,
                 total_points=10, org_id=org.id)
    db.add(ex)
    await db.flush()
    db.add(CBTAttempt(id=str(uuid.uuid4()), exam_id=ex.id, student_id=st.id, score=8, max_score=10,
                      status="graded", org_id=org.id))
    await db.commit()
    prog = await cs.my_progress(db=db, current_user=u)
    assert prog["overall"]["pending_results"] == 1
    assert prog["recent"][0]["pending"] is True and prog["recent"][0]["score"] is None
    assert prog["overall"]["average"] is None


async def test_events_count_only_own_in_progress_attempt(db, org):
    u, st, subj = await _setup(db, org)
    out = await cs.start_practice(cs.PracticeStart(subject_id=subj.id, count=5), db=db, current_user=u)
    att = await cbt_mod.start_attempt(out["exam_id"], db=db, current_user=u)
    await cs.record_attempt_event(att["id"], cs.AttemptEvent(type="idle"), db=db, current_user=u)
    await cs.record_attempt_event(att["id"], cs.AttemptEvent(type="idle"), db=db, current_user=u)
    await cs.record_attempt_event(att["id"], cs.AttemptEvent(type="blur"), db=db, current_user=u)
    row = (await db.execute(__import__("sqlalchemy").select(CBTAttempt).where(CBTAttempt.id == att["id"]))).scalar_one()
    await db.refresh(row)
    assert (row.idle_count, row.blur_count, row.paste_count) == (2, 1, 0)


async def test_exam_types_validated_on_create():
    from app.schemas.school_experience import ExamCreate
    assert ExamCreate(title="t", exam_type="mock").exam_type == "mock"
    with pytest.raises(Exception):
        ExamCreate(title="t", exam_type="practice")
