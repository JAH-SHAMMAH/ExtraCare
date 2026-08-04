"""Seed the Secondary-Report pipeline + four demo logins so it can be exercised
end-to-end AS EACH ROLE (Super User / class teacher / subject teacher / HR).

SAFE BY DEFAULT: refuses a production-looking database unless you explicitly opt
in (see _seed_common.target_url_or_exit + SEED_ALLOW_PRODUCTION). It only ever
creates/updates its OWN demo rows — the four `seed-*` accounts (marked
is_seed_account, so they stay out of every staff roster) and a marked demo
class/subject/pupils. It NEVER modifies a real user, a real password, or any
real class/pupil/subject: it refuses an address that isn't a reserved seed
address, and refuses to touch one that already belongs to a non-seed account.

Idempotent: re-running updates the same demo accounts + rows in place.

What it does:
  1. Ensures Terms (Autumn/Spring/Summer) + Sub-terms (Half/Full); marks one active
     ONLY if none is active yet (no surprise change to a live 'current term').
  2. Bootstraps the Assessments + Cumulatives (CBT/THEORY/PRJ/PBT/EXAM ->
     HALF TERM TOTAL/%/CA 1/TOTAL) + a 9-band grade scale.
  3. Creates a MARKED demo class "[SEED] Report Demo Class" with three demo pupils
     and a "[SEED] Report Demo Subject" (nothing real touched).
  4. Creates the four `seed-*@<school domain>` logins (they must be on the real
     login domain to pass the auth domain gate) and wires them: the class-teacher login
     is the demo class's class/form (and PC-by-fallback) teacher; the subject-teacher
     login teaches the demo subject there via the Timetable (but is NOT class/PC
     teacher). Enters sample scores.
  5. Prints the four emails + shared password + expected per-role behaviour.

Usage (PowerShell) — scratch DB:
    $env:SEED_DATABASE_URL = "postgresql+asyncpg://USER:PW@HOST/scratch_db"
    ./venv/Scripts/python.exe scripts/seed_report_demo.py
Usage — production, DELIBERATELY (both vars required):
    $env:SEED_DATABASE_URL      = "<prod asyncpg url>"
    $env:SEED_ALLOW_PRODUCTION  = "yes-i-mean-it"
    ./venv/Scripts/python.exe scripts/seed_report_demo.py
Run `alembic upgrade head` against the same DB first (creates the report tables).
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))   # backend/ (for app...)
sys.path.insert(0, _HERE)                    # scripts/ (for _seed_common)

from _seed_common import (                                              # noqa: E402
    target_url_or_exit, is_seed_email, SEED_EMAIL_DOMAIN, SEED_PREFIX, SEED_PASSWORD,
    DEMO_CLASS_NAME, DEMO_SUBJECT_NAME, DEMO_STUDENT_PREFIX,
)
from app.models.organization import Organization                       # noqa: E402
from app.models.user import User, UserStatus                           # noqa: E402
from app.models.role import Role, permission_presets_for_industry      # noqa: E402
from app.core.security import hash_password                            # noqa: E402
from app.models.modules.school import SchoolClass, Subject, Student, Timetable  # noqa: E402
from app.models.modules.platform import (                             # noqa: E402
    AcademicTerm, AcademicSubTerm, GradingScale, GradingBand, StudentAssessmentScore,
)
from app.routers.modules.platform import (                            # noqa: E402
    bootstrap_assessments, bootstrap_cumulatives, list_assessments,
)

NINE_BAND = [("A*", 95, 100), ("A", 90, 94), ("B+", 85, 89), ("B", 80, 84),
             ("C", 70, 79), ("D", 60, 69), ("E", 50, 59), ("P", 40, 49), ("F", 0, 39)]
DEMO_STUDENTS = [("One", "SEED-001"), ("Two", "SEED-002"), ("Three", "SEED-003")]


class _FakeAdmin:
    """Transient admin principal for the bootstrap helpers (org-scoped, full perms)."""
    def __init__(self, org_id):
        self.org_id = org_id
        self.id = "seed-script"
        self.is_superadmin = True

    def has_permission(self, _perm):
        return True


async def _ensure_terms(db, org_id):
    existing = {t.name.lower(): t for t in (await db.execute(select(AcademicTerm).where(AcademicTerm.org_id == org_id))).scalars().all()}
    terms = {}
    for i, name in enumerate(["Autumn", "Spring", "Summer"], start=1):
        t = existing.get(name.lower())
        if not t:
            t = AcademicTerm(id=str(uuid.uuid4()), name=name, position=i, is_active=False, org_id=org_id)
            db.add(t)
        terms[name] = t
    subs = {s.name.lower(): s for s in (await db.execute(select(AcademicSubTerm).where(AcademicSubTerm.org_id == org_id))).scalars().all()}
    for i, name in enumerate(["Half-Term", "Full-Term"], start=1):
        if name.lower() not in subs:
            s = AcademicSubTerm(id=str(uuid.uuid4()), name=name, position=i, org_id=org_id)
            db.add(s); subs[name.lower()] = s
    await db.flush()
    # Only pick an active term if the org has none yet — don't disturb a live one.
    any_active = any(t.is_active for t in terms.values())
    if not any_active:
        terms["Spring"].is_active = True
        terms["Spring"].active_sub_term_id = subs["full-term"].id
    await db.commit()
    return terms, subs


async def _ensure_grade_scale(db, org_id):
    sc = (await db.execute(select(GradingScale).where(
        GradingScale.org_id == org_id, GradingScale.scale_type == "numeric", GradingScale.purpose == "grade"))).scalars().first()
    if sc:
        return sc
    sc = GradingScale(id=str(uuid.uuid4()), name="GRADING SCALE", scale_type="numeric",
                      is_provisional=False, purpose="grade", show_in_table=True, org_id=org_id)
    db.add(sc); await db.flush()
    for g, lo, hi in NINE_BAND:
        db.add(GradingBand(id=str(uuid.uuid4()), scale_id=sc.id, grade=g, remark=g,
                           min_score=Decimal(lo), max_score=Decimal(hi), org_id=org_id))
    await db.commit()
    return sc


async def _ensure_role(db, org_id, slug):
    r = (await db.execute(select(Role).where(Role.org_id == org_id, Role.slug == slug))).scalars().first()
    if r:
        return r
    perms = permission_presets_for_industry("school").get(slug, [])
    r = Role(id=str(uuid.uuid4()), name=slug.replace("_", " ").title(), slug=slug,
             permissions=list(perms), org_id=org_id, is_system=False)
    db.add(r); await db.flush()
    return r


async def _ensure_seed_user(db, org_id, email, name, role):
    # Secondary guard: refuse any address that isn't provably a seed email.
    if not is_seed_email(email):
        raise SystemExit(f"Refusing to touch non-seed email {email!r}.")
    u = (await db.execute(select(User).where(User.org_id == org_id, User.email == email))).scalars().first()
    if u and not u.is_seed_account:
        # An existing NON-seed account already owns this email — never touch it.
        raise SystemExit(f"Refusing: {email!r} exists and is not a seed account.")
    if not u:
        u = User(id=str(uuid.uuid4()), email=email, full_name=name, status=UserStatus.ACTIVE,
                 org_id=org_id, is_superadmin=False)
        db.add(u)
    u.full_name = name
    u.status = UserStatus.ACTIVE
    u.is_seed_account = True                            # the authoritative fake marker
    u.hashed_password = hash_password(SEED_PASSWORD)    # seed account only
    u.roles = [role]
    await db.flush()
    return u


async def _ensure_demo_data(db, org_id, class_teacher_id):
    cls = (await db.execute(select(SchoolClass).where(SchoolClass.org_id == org_id, SchoolClass.name == DEMO_CLASS_NAME))).scalars().first()
    if not cls:
        cls = SchoolClass(id=str(uuid.uuid4()), name=DEMO_CLASS_NAME, level="YEAR 11", org_id=org_id)
        db.add(cls)
    cls.teacher_id = class_teacher_id
    subj = (await db.execute(select(Subject).where(Subject.org_id == org_id, Subject.name == DEMO_SUBJECT_NAME))).scalars().first()
    if not subj:
        subj = Subject(id=str(uuid.uuid4()), name=DEMO_SUBJECT_NAME, org_id=org_id)
        db.add(subj)
    await db.flush()
    students = []
    for label, sid in DEMO_STUDENTS:
        s = (await db.execute(select(Student).where(Student.org_id == org_id, Student.student_id == sid))).scalars().first()
        if not s:
            s = Student(id=str(uuid.uuid4()), student_id=sid, first_name="Demo Pupil", last_name=label,
                        class_id=cls.id, org_id=org_id)
            db.add(s)
        else:
            s.class_id = cls.id
        students.append(s)
    await db.commit()
    return cls, subj, students


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
        admin = _FakeAdmin(org.id)

        terms, subs = await _ensure_terms(db, org.id)
        await _ensure_grade_scale(db, org.id)
        await bootstrap_assessments(db=db, current_user=admin)
        await bootstrap_cumulatives(db=db, current_user=admin)

        # Four demo logins (reserved seed- addresses only, marked is_seed_account).
        su = await _ensure_seed_user(db, org.id, f"{SEED_PREFIX}superuser@{SEED_EMAIL_DOMAIN}", "Seed Super User", await _ensure_role(db, org.id, "super_user"))
        ct = await _ensure_seed_user(db, org.id, f"{SEED_PREFIX}classteacher@{SEED_EMAIL_DOMAIN}", "Seed Class Teacher", await _ensure_role(db, org.id, "teacher"))
        st = await _ensure_seed_user(db, org.id, f"{SEED_PREFIX}subjectteacher@{SEED_EMAIL_DOMAIN}", "Seed Subject Teacher", await _ensure_role(db, org.id, "teacher"))
        hr = await _ensure_seed_user(db, org.id, f"{SEED_PREFIX}hr@{SEED_EMAIL_DOMAIN}", "Seed HR Manager", await _ensure_role(db, org.id, "hr_manager"))
        await db.commit()

        cls, subj, students = await _ensure_demo_data(db, org.id, ct.id)

        # Subject teacher teaches the demo subject in the demo class (Timetable) —
        # but is not the class teacher and not the PC teacher.
        has_tt = (await db.execute(select(Timetable.id).where(
            Timetable.org_id == org.id, Timetable.class_id == cls.id,
            Timetable.subject_id == subj.id, Timetable.teacher_id == st.id))).scalars().first()
        if not has_tt:
            db.add(Timetable(id=str(uuid.uuid4()), class_id=cls.id, subject_id=subj.id, teacher_id=st.id,
                             day_of_week=1, start_time="09:00", end_time="10:00", org_id=org.id))

        term = terms["Spring"]
        A = {a.name: a for a in await list_assessments(term_id=term.id, db=db, current_user=admin)}
        exam = A.get("EXAM")
        for i, s in enumerate(students):
            score = Decimal(55 + i * 15)     # 55, 70, 85
            row = (await db.execute(select(StudentAssessmentScore).where(
                StudentAssessmentScore.org_id == org.id, StudentAssessmentScore.student_id == s.id,
                StudentAssessmentScore.subject_id == subj.id, StudentAssessmentScore.assessment_id == exam.id))).scalars().first()
            if row:
                row.score = score
            else:
                db.add(StudentAssessmentScore(id=str(uuid.uuid4()), org_id=org.id, student_id=s.id,
                                              subject_id=subj.id, assessment_id=exam.id, score=score))
        await db.commit()

        print("\n=== SEED COMPLETE ===")
        print(f"Org:              {org.name} ({org.id})")
        print(f"Active term:      {term.name} / Full-Term")
        print(f"Demo class:       {cls.name} — {len(students)} demo pupils, EXAM scores entered")
        print(f"Demo subject:     {subj.name}")
        print("\n--- FOUR DEMO LOGINS (all share this password) ---")
        print(f"Password:         {SEED_PASSWORD}")
        print(f"Super User:       {su.email}      -> full report nav; any class/subject")
        print(f"Class teacher:    {ct.email}   -> Reports View works for the demo class; is PC teacher")
        print(f"Subject teacher:  {st.email} -> Make Report shows the demo subject;")
        print(f"                  blocked from Reports View + PC comments for the demo class")
        print(f"HR manager:       {hr.email}             -> HR nav only; NO Secondary-Report admin tools")
        print("\nMarked is_seed_account=True (hidden from the Users list). No real user,")
        print("password, class, pupil or subject was modified. Remove later with:")
        print("    ./venv/Scripts/python.exe scripts/remove_report_demo.py\n")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
