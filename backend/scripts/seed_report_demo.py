"""Seed the Secondary-Report pipeline on a SCRATCH database so it can be exercised
end-to-end AS EACH ROLE (super user / class teacher / subject teacher / non-PC).

SAFETY: runs ONLY against the database in $SEED_DATABASE_URL, and REFUSES any URL
that looks like production ('onyz', 'prod', 'render'). It never touches the
protected local SQLite fallback. Point it at a COPY of your dev/local DB.

What it does (all idempotent — safe to re-run):
  1. Ensures Terms (Autumn/Spring/Summer) + Sub-terms (Half-Term/Full-Term), marks
     Spring + Full-Term active.
  2. Bootstraps the Fairview Assessments (CBT/THEORY/PRJ/PBT/EXAM) + Cumulatives
     (HALF TERM TOTAL / % / CA 1 / TOTAL) for every term.
  3. Ensures a numeric grade scale (purpose=grade) with the 9-band A*..F scale.
  4. Picks a REAL class that has a class/form teacher + pupils; ensures a Timetable
     (class, subject, teacher) assignment exists (creates one from real rows if the
     data has none) so a subject teacher has something to enter.
  5. Enters sample EXAM scores for the class's pupils in that subject.
  6. Prints the accounts + IDs you need for the four-role click-through.

Usage (PowerShell):
    $env:SEED_DATABASE_URL = "sqlite+aiosqlite:///C:/path/to/scratch_copy.db"
    ./venv/Scripts/python.exe scripts/seed_report_demo.py
Run `alembic upgrade head` against the same scratch DB first.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Make `app...` importable when run from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

# Seed logins live on a DELIBERATELY FAKE domain so this script can only ever
# create/update its own accounts — never a real user (and thus never a real
# password). The four demo accounts share one password.
SEED_DOMAIN = "fairview.seed"
SEED_PASSWORD = "FairviewSeed#2026"

NINE_BAND = [("A*", 95, 100), ("A", 90, 94), ("B+", 85, 89), ("B", 80, 84),
             ("C", 70, 79), ("D", 60, 69), ("E", 50, 59), ("P", 40, 49), ("F", 0, 39)]
FORBIDDEN = ("onyz", "prod", "render.com", "amazonaws")


class _FakeAdmin:
    """A transient admin principal for the bootstrap helpers (org-scoped, full perms)."""
    def __init__(self, org_id):
        self.org_id = org_id
        self.id = "seed-script"
        self.is_superadmin = True

    def has_permission(self, _perm):    # bootstrap helpers only read org_id, but be safe
        return True


async def _ensure_terms(db, org_id):
    existing = {t.name.lower(): t for t in (await db.execute(select(AcademicTerm).where(AcademicTerm.org_id == org_id))).scalars().all()}
    terms = {}
    for i, name in enumerate(["Autumn", "Spring", "Summer"], start=1):
        t = existing.get(name.lower())
        if not t:
            t = AcademicTerm(id=str(uuid.uuid4()), name=name, position=i, is_active=(name == "Spring"), org_id=org_id)
            db.add(t)
        terms[name] = t
    subs = {s.name.lower(): s for s in (await db.execute(select(AcademicSubTerm).where(AcademicSubTerm.org_id == org_id))).scalars().all()}
    for i, name in enumerate(["Half-Term", "Full-Term"], start=1):
        if name.lower() not in subs:
            s = AcademicSubTerm(id=str(uuid.uuid4()), name=name, position=i, org_id=org_id)
            db.add(s); subs[name.lower()] = s
    await db.flush()
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


async def _pick_assignment(db, org_id):
    """Prefer a real Timetable (class, subject, teacher) whose class has pupils. Else
    build one from a real class-with-teacher + a real subject."""
    tts = (await db.execute(select(Timetable).where(Timetable.org_id == org_id, Timetable.teacher_id.is_not(None)))).scalars().all()
    for tt in tts:
        n = len((await db.execute(select(Student.id).where(Student.org_id == org_id, Student.class_id == tt.class_id, Student.is_deleted == False))).scalars().all())  # noqa: E712
        if n:
            return tt.class_id, tt.subject_id, tt.teacher_id, False
    # None usable — synthesise from real rows.
    cls = (await db.execute(select(SchoolClass).where(SchoolClass.org_id == org_id, SchoolClass.teacher_id.is_not(None)))).scalars().first()
    if not cls:
        cls = (await db.execute(select(SchoolClass).where(SchoolClass.org_id == org_id))).scalars().first()
    if not cls:
        raise SystemExit("No classes in this database — seed classes/students first.")
    subj = (await db.execute(select(Subject).where(Subject.org_id == org_id))).scalars().first()
    if not subj:
        raise SystemExit("No subjects in this database — seed subjects first.")
    teacher = cls.teacher_id or (await db.execute(select(User.id).where(User.org_id == org_id))).scalars().first()
    if not cls.teacher_id:
        cls.teacher_id = teacher
    db.add(Timetable(id=str(uuid.uuid4()), class_id=cls.id, subject_id=subj.id, teacher_id=teacher,
                     day_of_week=0, start_time="08:00", end_time="09:00", org_id=org_id))
    await db.commit()
    return cls.id, subj.id, teacher, True


async def _ensure_role(db, org_id, slug):
    """Reuse the org's role by slug, else create it with the industry preset perms."""
    r = (await db.execute(select(Role).where(Role.org_id == org_id, Role.slug == slug))).scalars().first()
    if r:
        return r
    perms = permission_presets_for_industry("school").get(slug, [])
    r = Role(id=str(uuid.uuid4()), name=slug.replace("_", " ").title(), slug=slug,
             permissions=list(perms), org_id=org_id, is_system=False)
    db.add(r)
    await db.flush()
    return r


async def _ensure_seed_user(db, org_id, email, name, role):
    """Create/refresh a SEED login (fake @fairview.seed domain only). Sets a known
    password; NEVER touches a real user or a real password."""
    if not email.endswith("@" + SEED_DOMAIN):
        raise SystemExit(f"Refusing to touch non-seed email {email!r}.")
    u = (await db.execute(select(User).where(User.org_id == org_id, User.email == email))).scalars().first()
    if not u:
        u = User(id=str(uuid.uuid4()), email=email, full_name=name, status=UserStatus.ACTIVE,
                 org_id=org_id, is_superadmin=False)
        db.add(u)
    u.full_name = name
    u.status = UserStatus.ACTIVE
    u.hashed_password = hash_password(SEED_PASSWORD)   # seed account only
    u.roles = [role]
    await db.flush()
    return u


async def main():
    url = os.environ.get("SEED_DATABASE_URL")
    if not url:
        raise SystemExit("Set SEED_DATABASE_URL to your SCRATCH database (never production).")
    if any(bad in url.lower() for bad in FORBIDDEN):
        raise SystemExit(f"Refusing to seed: '{url}' looks like production. Use a scratch copy.")

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

        class_id, subject_id, teacher_id, created = await _pick_assignment(db, org.id)
        term = terms["Spring"]
        A = {a.name: a for a in await list_assessments(term_id=term.id, db=db, current_user=admin)}
        students = (await db.execute(select(Student).where(
            Student.org_id == org.id, Student.class_id == class_id, Student.is_deleted == False))).scalars().all()  # noqa: E712
        exam = A.get("EXAM")
        for i, s in enumerate(students):
            score = Decimal(45 + (i * 7) % 50)     # spread 45..95 deterministically
            row = (await db.execute(select(StudentAssessmentScore).where(
                StudentAssessmentScore.org_id == org.id, StudentAssessmentScore.student_id == s.id,
                StudentAssessmentScore.subject_id == subject_id, StudentAssessmentScore.assessment_id == exam.id))).scalars().first()
            if row:
                row.score = score
            else:
                db.add(StudentAssessmentScore(id=str(uuid.uuid4()), org_id=org.id, student_id=s.id,
                                              subject_id=subject_id, assessment_id=exam.id, score=score))
        await db.commit()

        cls = (await db.execute(select(SchoolClass).where(SchoolClass.id == class_id))).scalar_one()
        subj = (await db.execute(select(Subject).where(Subject.id == subject_id))).scalar_one()

        # ── Four demo login accounts (fake @fairview.seed domain only) ──────────
        super_role = await _ensure_role(db, org.id, "super_user")
        teacher_role = await _ensure_role(db, org.id, "teacher")
        hr_role = await _ensure_role(db, org.id, "hr_manager")

        su = await _ensure_seed_user(db, org.id, f"superuser@{SEED_DOMAIN}", "Seed Super User", super_role)
        ct = await _ensure_seed_user(db, org.id, f"classteacher@{SEED_DOMAIN}", "Seed Class Teacher", teacher_role)
        st = await _ensure_seed_user(db, org.id, f"subjectteacher@{SEED_DOMAIN}", "Seed Subject Teacher", teacher_role)
        hr = await _ensure_seed_user(db, org.id, f"hr@{SEED_DOMAIN}", "Seed HR Manager", hr_role)

        # Wire the demo class so the four roles resolve deterministically:
        #  - class/form teacher (and PC teacher by fallback) = the class-teacher login
        #  - the subject-teacher login teaches the demo subject here (Timetable), but is
        #    NOT the class teacher and NOT the PC teacher.
        cls.teacher_id = ct.id
        has_tt = (await db.execute(select(Timetable.id).where(
            Timetable.org_id == org.id, Timetable.class_id == cls.id,
            Timetable.subject_id == subj.id, Timetable.teacher_id == st.id))).scalars().first()
        if not has_tt:
            db.add(Timetable(id=str(uuid.uuid4()), class_id=cls.id, subject_id=subj.id, teacher_id=st.id,
                             day_of_week=1, start_time="09:00", end_time="10:00", org_id=org.id))
        await db.commit()

        print("\n=== SEED COMPLETE ===")
        print(f"Org:              {org.name} ({org.id})")
        print(f"Active term:      {term.name} / Full-Term")
        print(f"Demo class:       {cls.name} ({cls.id}) — {len(students)} pupils, EXAM scores entered")
        print(f"Demo subject:     {subj.name} ({subj.id})")
        print(f"Timetable assignment {'CREATED' if created else 'reused'} for the base data")
        print("\n--- FOUR DEMO LOGINS (all share this password) ---")
        print(f"Password:         {SEED_PASSWORD}")
        print(f"Super User:       superuser@{SEED_DOMAIN}      -> full report nav; any class/subject")
        print(f"Class teacher:    classteacher@{SEED_DOMAIN}   -> Reports View works for {cls.name}; is PC teacher")
        print(f"Subject teacher:  subjectteacher@{SEED_DOMAIN} -> Make Report shows {subj.name} in {cls.name};")
        print(f"                  blocked from Reports View + PC comments for {cls.name} (not class/PC teacher)")
        print(f"HR manager:       hr@{SEED_DOMAIN}             -> HR nav only; NO Secondary-Report admin tools")
        print("\nThese are NEW accounts on a fake domain; no existing user or password was touched.\n")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
