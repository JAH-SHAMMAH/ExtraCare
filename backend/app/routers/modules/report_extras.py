"""Report extras: Student Result History and the Result Backup Helper.

Both delegate to ``platform.report_card`` for every figure, so a number here can
never disagree with the report card itself, and every access gate (own record,
parent, class teacher, published-only) is enforced by that same function.
"""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import AnyPermissionChecker, PermissionChecker
from app.database import get_db
from app.deps import get_current_active_user
from app.models.modules.platform import AcademicSession, AcademicSubTerm, AcademicTerm, Cumulative
from app.models.modules.school import SchoolClass, Student
from app.models.user import User
from app.routers.modules.platform import report_card

router = APIRouter(prefix="/report-extras", tags=["Report extras"])


@router.get("/student-history/{student_id}",
            dependencies=[Depends(AnyPermissionChecker("school:reports:read", "school:reports:own:read"))])
async def student_history(student_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    """One pupil's results across every session, term and sub-term that has a report set up."""
    org = user.org_id
    combos = {(c.session_id, c.term_id, c.sub_term_id) for c in
              (await db.execute(select(Cumulative).where(Cumulative.org_id == org))).scalars().all()}
    sessions = {s.id: s for s in (await db.execute(select(AcademicSession).where(AcademicSession.org_id == org))).scalars().all()}
    terms = {t.id: t for t in (await db.execute(select(AcademicTerm).where(AcademicTerm.org_id == org))).scalars().all()}
    subs = {t.id: t for t in (await db.execute(select(AcademicSubTerm).where(AcademicSubTerm.org_id == org))).scalars().all()}
    order = sorted(combos, key=lambda c: (sessions[c[0]].start_date is None, sessions[c[0]].start_date, sessions[c[0]].name or "",
                                          getattr(terms.get(c[1]), "position", 0) or 0, getattr(subs.get(c[2]), "position", 0) or 0)
                   if c[0] in sessions else (True, None, "", 0, 0))
    rows, denied = [], 0
    for sid, tid, stid in order:
        try:
            card = await report_card(student_id=student_id, term_id=tid, sub_term_id=stid, session_id=sid, db=db, current_user=user)
        except HTTPException as e:
            if e.status_code == 404 and not rows and not denied:
                raise
            denied += 1  # not published yet, or not this pupil's level: leave the row out
            continue
        if card.not_configured or not any(any(v is not None for v in s.values.values()) for s in card.subjects):
            continue
        rows.append({"session": card.session_name or getattr(sessions.get(sid), "name", None), "term": card.term_name,
                     "sub_term": card.sub_term_name, "class_name": card.class_name, "average": float(card.average), "total": float(card.total),
                     "grade": card.grade, "position": card.position, "class_size": card.class_size,
                     "subjects": [{"name": s.subject_name, "grade": s.grade} for s in card.subjects]})
    student = (await db.execute(select(Student).where(Student.id == student_id, Student.org_id == org))).scalar_one_or_none()
    return {"student": {"id": student_id, "name": f"{student.first_name} {student.last_name}".strip() if student else None,
                        "admission_no": student.student_id if student else None},
            "items": rows, "hidden": denied}


@router.get("/backup", dependencies=[Depends(PermissionChecker("school:reports:read"))])
async def results_backup(class_id: str, term_id: str, sub_term_id: str, session_id: str | None = None,
                         db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    """A spreadsheet (CSV) copy of one class's results for a term, to keep offline."""
    org = user.org_id
    cls = (await db.execute(select(SchoolClass).where(SchoolClass.id == class_id, SchoolClass.org_id == org))).scalar_one_or_none()
    if not cls:
        raise HTTPException(404, "Class not found.")
    students = (await db.execute(select(Student).where(Student.org_id == org, Student.class_id == class_id, Student.is_deleted == False)  # noqa: E712
                                 .order_by(Student.first_name, Student.last_name))).scalars().all()
    cards = [await report_card(student_id=s.id, term_id=term_id, sub_term_id=sub_term_id, session_id=session_id, db=db, current_user=user) for s in students]
    cols: list[tuple[str, str, str]] = []  # (subject_id, column key, header)
    seen = set()
    for c in cards:
        names = {col.key: col.name for col in c.columns}
        for s in c.subjects:
            for k in s.values:
                if (s.subject_id, k) not in seen:
                    seen.add((s.subject_id, k))
                    cols.append((s.subject_id, k, f"{s.subject_name} - {names.get(k, k)}"))
    buf = io.StringIO()
    w = csv.writer(buf)
    head = cards[0] if cards else None
    w.writerow(["Admission No", "Name", "Class", "Session", "Term", "Sub-term"] + [h for _a, _b, h in cols] + ["Total", "Average", "Grade", "Position"])
    for c in cards:
        by = {(s.subject_id, k): v for s in c.subjects for k, v in s.values.items()}
        w.writerow([c.admission_no, c.student_name, c.class_name, c.session_name, c.term_name, c.sub_term_name]
                   + ["" if by.get((a, b)) is None else by[(a, b)] for a, b, _h in cols] + [c.total, c.average, c.grade, c.position])
    name = f"results-{(head.class_name if head else 'class')}-{(head.term_name if head else '')}.csv".replace(" ", "_")
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})
