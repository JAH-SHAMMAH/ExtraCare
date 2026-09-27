"""Preview (and optionally apply) migration 128's subject-enrolment backfill.

Calls the SAME planner the migration calls — app/services/subject_enrollment.
plan_backfill — so what this previews is exactly what the migration applies.

WHY A BACKFILL EXISTS AT ALL. Subject enrolment gates mark entry. Without
backfilling from marks that already exist, every mark in the system becomes
uneditable the day the gate ships: a teacher reopening one and re-saving it would
be refused. An existing mark is itself the evidence that the pupil takes the
subject.

WHY THE UNION OF BOTH MARK STORES. `student_assessment_scores` is the report
engine's store; `grades` is the older gradebook. They disagreed at Fairview —
1,799 pairs against 1,800 — and the pair only in `grades` was a real pupil whose
assessment-score row had been lost when a CBT re-sync dropped mid-run.

Normally the migration does this for you. Run this when you want to SEE the plan
first, or to apply the backfill on a database where 128 already ran (it is
idempotent, so that is safe).

DRY RUN BY DEFAULT.

    python -m scripts.backfill_subject_enrollment "<DSN>"
    python -m scripts.backfill_subject_enrollment "<DSN>" --write
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.modules.academics import StudentSubjectEnrollment
from app.models.modules.school import SchoolClass, Student, Subject
from app.models.organization import Organization
from app.services.subject_enrollment import (
    AcademicYearUnresolved, plan_backfill, resolve_academic_year,
)


def _dsn() -> str:
    for a in sys.argv[1:]:
        if not a.startswith("--"):
            return a.split("?")[0]
    env = os.environ.get("DATABASE_URL", "").strip()
    if env:
        return env.split("?")[0]
    sys.exit("Pass the DSN as the first argument, or set DATABASE_URL.")


async def main() -> int:
    write = "--write" in sys.argv
    engine = create_async_engine(_dsn(), echo=False, connect_args={"ssl": "require"})
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        print(f"{'WRITE' if write else 'DRY RUN'}\n")
        grand = 0

        orgs = (await db.execute(select(Organization))).scalars().all()
        for org in orgs:
            print(f"organisation: {org.name}")
            try:
                year = await resolve_academic_year(db, org.id)
            except AcademicYearUnresolved as e:
                print(f"  !  skipped — {e}")
                continue
            print(f"  academic year: {year}")

            pairs = await plan_backfill(db, org.id, year)
            if not pairs:
                already = (await db.execute(select(StudentSubjectEnrollment).where(
                    StudentSubjectEnrollment.org_id == org.id,
                    StudentSubjectEnrollment.academic_year == year))).scalars().all()
                print(f"  =  nothing to do ({len(already)} enrolment(s) already present)")
                continue

            subj_names = {s.id: s.name for s in (await db.execute(
                select(Subject).where(Subject.org_id == org.id))).scalars().all()}
            stu = {s.id: s for s in (await db.execute(select(Student).where(
                Student.org_id == org.id))).scalars().all()}
            cls_names = {c.id: c.name for c in (await db.execute(select(SchoolClass).where(
                SchoolClass.org_id == org.id))).scalars().all()}

            print(f"  +  {len(pairs)} enrolment(s) to create\n")
            by_subject = Counter(subj_names.get(sub, sub) for (_s, sub) in pairs)
            print("     by subject:")
            for name, n in sorted(by_subject.items()):
                print(f"       {name:<30} {n}")

            by_class = Counter(
                cls_names.get(getattr(stu.get(s), "class_id", None), "(no class)")
                for (s, _sub) in pairs)
            print("     by class:")
            for name, n in sorted(by_class.items()):
                print(f"       {name:<30} {n}")

            per_pupil = Counter(s for (s, _sub) in pairs)
            spread = Counter(per_pupil.values())
            print("     pupils by subject count:")
            for k in sorted(spread):
                print(f"       {spread[k]} pupil(s) -> {k} subject(s)")

            # The pairs that come ONLY from the old gradebook. These are the ones a
            # naive backfill would miss, so they are worth naming individually.
            from sqlalchemy import text as _t
            only_grades = (await db.execute(_t("""
                SELECT s.student_id, s.subject_id FROM
                  (SELECT DISTINCT student_id, subject_id FROM grades WHERE org_id = :o) s
                WHERE NOT EXISTS (SELECT 1 FROM student_assessment_scores x
                                  WHERE x.student_id = s.student_id
                                    AND x.subject_id = s.subject_id)"""),
                {"o": org.id})).all()
            if only_grades:
                print(f"\n     from `grades` ONLY (a scores-only backfill would miss these):")
                for sid, sub in only_grades:
                    st = stu.get(sid)
                    who = f"{st.student_id} {st.first_name} {st.last_name}" if st else sid
                    print(f"       {who} — {subj_names.get(sub, sub)}")

            grand += len(pairs)
            if write:
                now = datetime.now(timezone.utc)
                for s, sub in pairs:
                    db.add(StudentSubjectEnrollment(
                        id=str(uuid.uuid4()), org_id=org.id, student_id=s,
                        subject_id=sub, academic_year=year, enrolled_by=None,
                        enrolled_at=now, source="backfill"))
            print()

        if write:
            await db.commit()
            print(f"[OK] {grand} enrolment(s) created.")
        else:
            print(f"DRY RUN — nothing written. {grand} enrolment(s) would be created.")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
