"""Remove EXACTLY the report-demo data created by seed_report_demo.py — the four
@fairview.seed logins and the marked demo class / subject / pupils / timetable /
scores. Touches nothing real.

Same safety guard as the seed: refuses a production-looking database unless BOTH
SEED_DATABASE_URL and SEED_ALLOW_PRODUCTION=yes-i-mean-it are set.

Usage (PowerShell):
    $env:SEED_DATABASE_URL     = "<the same url you seeded>"
    $env:SEED_ALLOW_PRODUCTION = "yes-i-mean-it"     # only if that url is production
    ./venv/Scripts/python.exe scripts/remove_report_demo.py

Leaves the org report CONFIG in place (Terms / Assessments / Cumulatives / grade
scale) — that is legitimate school setup, not demo data. Remove it via the UI if
you want it gone.
"""
from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select, delete, update, or_
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)

from _seed_common import (                                              # noqa: E402
    target_url_or_exit, SEED_DOMAIN, DEMO_CLASS_NAME, DEMO_SUBJECT_NAME, DEMO_STUDENT_PREFIX,
)
from app.models.organization import Organization                       # noqa: E402
from app.models.user import User                                       # noqa: E402
from app.models.modules.school import SchoolClass, Subject, Student, Timetable  # noqa: E402
from app.models.modules.platform import StudentAssessmentScore, StudentReportComment, ClassPcTeacher  # noqa: E402


async def main():
    url = target_url_or_exit()
    engine = create_async_engine(url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        org = (await db.execute(select(Organization).where(Organization.industry == "school"))).scalars().first()
        if not org:
            org = (await db.execute(select(Organization))).scalars().first()
        if not org:
            raise SystemExit("No organisation in this database.")

        # Locate ONLY the seed-marked rows.
        seed_users = [u for u in (await db.execute(select(User).where(
            User.org_id == org.id, User.email.like(f"%@{SEED_DOMAIN}")))).scalars().all()
            if u.email.endswith("@" + SEED_DOMAIN)]      # belt-and-suspenders guard
        seed_uids = [u.id for u in seed_users]
        demo_students = (await db.execute(select(Student).where(
            Student.org_id == org.id, Student.student_id.like(f"{DEMO_STUDENT_PREFIX}%")))).scalars().all()
        demo_sids = [s.id for s in demo_students]
        demo_class = (await db.execute(select(SchoolClass).where(SchoolClass.org_id == org.id, SchoolClass.name == DEMO_CLASS_NAME))).scalars().first()
        demo_subject = (await db.execute(select(Subject).where(Subject.org_id == org.id, Subject.name == DEMO_SUBJECT_NAME))).scalars().first()

        counts: dict[str, int] = {}

        async def _del(stmt, key):
            r = await db.execute(stmt)
            counts[key] = (r.rowcount or 0)

        if demo_sids:
            await _del(delete(StudentAssessmentScore).where(StudentAssessmentScore.org_id == org.id, StudentAssessmentScore.student_id.in_(demo_sids)), "scores")
            await _del(delete(StudentReportComment).where(StudentReportComment.org_id == org.id, StudentReportComment.student_id.in_(demo_sids)), "comments")
        tt_conds = []
        if demo_class:
            tt_conds.append(Timetable.class_id == demo_class.id)
        if seed_uids:
            tt_conds.append(Timetable.teacher_id.in_(seed_uids))
        if tt_conds:
            await _del(delete(Timetable).where(Timetable.org_id == org.id, or_(*tt_conds)), "timetable")
        pc_conds = []
        if demo_class:
            pc_conds.append(ClassPcTeacher.class_id == demo_class.id)
        if seed_uids:
            pc_conds.append(ClassPcTeacher.teacher_id.in_(seed_uids))
        if pc_conds:
            await _del(delete(ClassPcTeacher).where(ClassPcTeacher.org_id == org.id, or_(*pc_conds)), "pc_teacher")
        # Defensive: null any class whose class-teacher is a seed user (so the user
        # row can be removed even if it was wired to a non-demo class somehow).
        if seed_uids:
            await db.execute(update(SchoolClass).where(SchoolClass.org_id == org.id, SchoolClass.teacher_id.in_(seed_uids)).values(teacher_id=None))
        if demo_sids:
            await _del(delete(Student).where(Student.org_id == org.id, Student.id.in_(demo_sids)), "students")
        if demo_subject:
            await _del(delete(Subject).where(Subject.org_id == org.id, Subject.id == demo_subject.id), "subject")
        if demo_class:
            await _del(delete(SchoolClass).where(SchoolClass.org_id == org.id, SchoolClass.id == demo_class.id), "class")
        # Seed users last, via ORM so the role association is cleared too.
        removed_emails = []
        for u in seed_users:
            removed_emails.append(u.email)
            await db.delete(u)
        counts["users"] = len(removed_emails)

        await db.commit()

        print("\n=== TEARDOWN COMPLETE ===")
        print(f"Org:            {org.name} ({org.id})")
        for k in ("users", "class", "subject", "students", "timetable", "pc_teacher", "scores", "comments"):
            if k in counts:
                print(f"Removed {k:<11} {counts[k]}")
        print(f"Accounts removed: {', '.join(removed_emails) or '(none found)'}")
        print("Report config (Terms/Assessments/Cumulatives/grade scale) left in place.\n")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
