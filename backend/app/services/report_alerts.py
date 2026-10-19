"""Tell a class's parents when their child's report has been released."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.modules.platform import AcademicTerm
from app.models.modules.school import ParentGuardian, Student
from app.services import notifications as _notif

TYPE_REPORT = "report"
REPORT_URL = "/dashboard/my-children/report-card"


async def notify_report_released(db: AsyncSession, org_id: str, class_id: str | None, term_id: str | None = None) -> int:
    """In-app alert (and phone pop-up for those who allowed it) to each guardian of
    each pupil in the class. Returns how many alerts were sent. Never raises."""
    if not class_id:
        return 0
    try:
        term = None
        if term_id:
            term = (await db.execute(select(AcademicTerm.name).where(AcademicTerm.id == term_id, AcademicTerm.org_id == org_id))).scalar_one_or_none()
        pupils = (await db.execute(select(Student.id, Student.first_name).where(
            Student.org_id == org_id, Student.class_id == class_id, Student.is_deleted == False))).all()  # noqa: E712
        if not pupils:
            return 0
        first = {sid: name for sid, name in pupils}
        links = (await db.execute(select(ParentGuardian.user_id, ParentGuardian.student_id).where(
            ParentGuardian.org_id == org_id, ParentGuardian.student_id.in_(list(first))))).all()
        sent = 0
        for user_id, sid in links:
            what = f"{first[sid]}'s {term} report" if term else f"{first[sid]}'s report"
            await _notif.notify(org_id=org_id, user_id=user_id, type=TYPE_REPORT, title=f"{what} is ready",
                                message=f"{what} has been published. Tap to read it.",
                                payload={"student_id": sid, "term_id": term_id, "url": REPORT_URL}, session=db)
            sent += 1
        return sent
    except Exception:  # an alert must never undo a publish
        return 0
