"""
Seed three demo tenants — school, hospital, business — with realistic
modules_enabled and one admin user each. Idempotent: safe to re-run; each
sub-step checks what's already there before writing.

The Fairview School demo goes further: on top of the classroom (teacher +
class + subject + 6 students + timetable) it seeds the Phase 6.3 multi-role
layer — proper teacher/student/parent role assignments, Student.user_id
back-links, ParentGuardian rows, a dual-role user for the role-switcher
demo, plus attendance + grade data so the role-scoped homepages look
populated right away.

Usage:
    cd backend
    python -m scripts.seed_demo
"""

from __future__ import annotations

import asyncio
import random
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.database import AsyncSessionLocal, init_db
from app.core.security import hash_password
from app.models.live import LiveAttendance, LiveSession
from app.models.modules.school import (
    AttendanceRecord,
    AttendanceStatus,
    Grade,
    GradeStatus,
    LessonPlan,
    LessonPlanStatus,
    LibraryBook,
    LibraryLoan,
    LoanStatus,
    ParentGuardian,
    SchoolClass,
    Student,
    Subject,
    Timetable,
)
from app.models.sms import (
    SmsCampaign, SmsMessage,
    SmsTargetType, SmsCampaignStatus, SmsMessageStatus,
)
from app.models.modules.transport import (
    TransportVehicle, TransportDriver, TransportRoute, TransportStop,
    StudentRouteAssignment, TransportTrip, TripBoarding,
    VehicleStatus, TripDirection, TripStatus, BoardingStatus,
)
from app.models.organization import Organization, IndustryType, SubscriptionTier
from app.models.role import Role, PERMISSION_PRESETS
from app.models.user import User, UserStatus


DEMO_PASSWORD = "DemoPass123!"


@dataclass
class DemoOrg:
    slug: str
    name: str
    industry: str
    modules: list[str]
    admin_email: str
    admin_name: str
    tier: SubscriptionTier = SubscriptionTier.FREE
    # School-specific extras; ignored for other industries.
    seed_classroom: bool = False


DEMOS = [
    DemoOrg(
        slug="demo-school",
        name="Fairview School",
        industry="school",
        modules=["school", "attendance", "grades", "timetable"],
        admin_email="admin@demo-school.example.com",
        admin_name="Ada Nwosu",
        # ENTERPRISE — PRO capped modules at 2 (see app.core.plans.PLANS) and
        # the school demo legitimately needs school + attendance + grades +
        # timetable enabled at once. Enterprise also unlocks livestream + AI
        # which we want visible in the pitch anyway.
        tier=SubscriptionTier.ENTERPRISE,
        seed_classroom=True,
    ),
    DemoOrg(
        slug="demo-hospital",
        name="Demo Savanna Health",
        industry="hospital",
        modules=["hospital", "appointments", "emr", "billing"],
        admin_email="admin@demo-hospital.example.com",
        admin_name="Dr. Kwame Mensah",
    ),
    DemoOrg(
        slug="demo-business",
        name="Demo Baobab Holdings",
        industry="business",
        modules=["business", "payroll", "inventory", "finance"],
        admin_email="admin@demo-business.example.com",
        admin_name="Thandi Dlamini",
    ),
]


# Students for the demo school. Names span a few regions intentionally so
# the roster feels like a real pan-African school. Gender included so the
# executive dashboard's male/female split has real numbers.
DEMO_STUDENTS = [
    ("Amara",  "Okeke",   "female"),
    ("Biodun", "Adeleke", "male"),
    ("Chipo",  "Mutasa",  "female"),
    ("Daniel", "Mwangi",  "male"),
    ("Esi",    "Boateng", "female"),
    ("Fatima", "Bello",   "female"),
]


# Phase 6.3 parent/guardian link plan.
#
#   - Emeka Okeke       → Amara Okeke        (single-role parent)
#   - Chinyere Eze      → Biodun + Esi       (dual-role: teacher AND parent)
#
# The dual-role user is the hero of the role-switcher demo — she must log in
# to a visible switcher with both "Teacher" and "Parent" options populated.
PARENT_PLAN = [
    {
        "email": "emeka.okeke@demo-school.example.com",
        "full_name": "Emeka Okeke",
        "children": ["Amara Okeke"],
        "is_dual_role": False,
        "relationship": "parent",
    },
    {
        "email": "chinyere.eze@demo-school.example.com",
        "full_name": "Chinyere Eze",
        "children": ["Biodun Adeleke", "Esi Boateng"],
        "is_dual_role": True,  # also a teacher — English
        "relationship": "guardian",
    },
]

DUAL_ROLE_SUBJECT = {
    "name": "English Language",
    "code": "ENG10",
    "description": "Grade 10 English — comprehension, composition, literature.",
}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _fullname(first: str, last: str) -> str:
    return f"{first} {last}"


async def _ensure_roles(db, org: Organization) -> dict[str, Role]:
    """Return all org roles keyed by slug; create any that are missing per
    PERMISSION_PRESETS. Makes new role slugs (teacher/student/parent) light
    up on existing tenants without having to re-seed from scratch."""
    existing = (await db.execute(
        select(Role).where(Role.org_id == org.id)
    )).scalars().all()
    by_slug: dict[str, Role] = {r.slug: r for r in existing}
    created: list[str] = []
    for slug, perms in PERMISSION_PRESETS.items():
        if slug == "super_admin":
            continue
        if slug in by_slug:
            # Keep permissions in sync in case the preset evolves.
            if by_slug[slug].permissions != perms:
                by_slug[slug].permissions = perms
            continue
        role = Role(
            name=slug.replace("_", " ").title(),
            slug=slug,
            permissions=perms,
            org_id=org.id,
            is_system=True,
        )
        db.add(role)
        by_slug[slug] = role
        created.append(slug)
    if created:
        await db.flush()
    return by_slug


async def _ensure_user(
    db,
    org: Organization,
    *,
    email: str,
    full_name: str,
    roles: list[Role],
    extra_role_slug: str | None = None,
    phone: str | None = None,
) -> User:
    """Fetch-or-create a User; always sets/merges the given roles.

    `extra_role_slug` is a convenience for the dual-role case so we can add
    a second role without replacing the first.
    `phone` is set on create and top-up on update (idempotent — only fills
    a missing phone, never overwrites a user-edited one)."""
    user = (await db.execute(
        select(User).where(User.email == email, User.org_id == org.id)
    )).scalar_one_or_none()
    role_slugs = {r.slug for r in roles}
    if extra_role_slug:
        role_slugs.add(extra_role_slug)

    # Resolve the authoritative final role set once so both create and update
    # paths apply exactly the slugs we asked for. This is the only way to
    # migrate a pre-6.3 teacher user off `staff` onto `teacher` cleanly.
    needed_roles = (await db.execute(
        select(Role).where(
            Role.org_id == org.id,
            Role.slug.in_(role_slugs),
        )
    )).scalars().all()

    # E.164-normalise on the way in so the DB only ever contains canonical
    # numbers — saves the SMS sender from re-cleaning at fan-out time.
    from app.services.sms import normalise_phone_e164
    normalised_phone = normalise_phone_e164(phone) if phone else None

    if user is None:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(DEMO_PASSWORD),
            phone=normalised_phone,
            org_id=org.id,
            status=UserStatus.ACTIVE,
            email_verified=True,
            roles=list(needed_roles),
        )
        db.add(user)
        await db.flush()
    else:
        current = {r.slug for r in user.roles}
        if current != role_slugs:
            user.roles = list(needed_roles)
        # Back-fill phone only when currently unset so a user-edited number
        # doesn't get wiped by a re-seed.
        if normalised_phone and not user.phone:
            user.phone = normalised_phone
        await db.flush()
    return user


async def _link_student_to_user(db, student: Student, user: User) -> None:
    if student.user_id != user.id:
        student.user_id = user.id
        await db.flush()


async def _ensure_parent_guardian(
    db,
    org: Organization,
    user: User,
    student: Student,
    *,
    relationship_type: str,
    is_primary: bool,
) -> ParentGuardian:
    existing = (await db.execute(
        select(ParentGuardian).where(
            ParentGuardian.user_id == user.id,
            ParentGuardian.student_id == student.id,
        )
    )).scalar_one_or_none()
    if existing:
        return existing
    link = ParentGuardian(
        user_id=user.id,
        student_id=student.id,
        relationship_type=relationship_type,
        is_primary=is_primary,
        org_id=org.id,
    )
    db.add(link)
    await db.flush()
    return link


async def _seed_demo_attendance(db, org: Organization, students: list[Student]) -> int:
    """Seed ~10 school days of attendance per student so %-based stats read
    real numbers rather than null. Deterministic per-student so re-runs don't
    balloon the dataset (we bail if any row already exists for that student)."""
    created = 0
    today = date.today()
    # Build a stable set of weekday dates over the last 3 weeks.
    dates: list[date] = []
    d = today - timedelta(days=1)
    while len(dates) < 10:
        if d.weekday() < 5:  # Mon-Fri
            dates.append(d)
        d -= timedelta(days=1)

    for idx, student in enumerate(students):
        already = (await db.execute(
            select(AttendanceRecord.id).where(
                AttendanceRecord.student_id == student.id,
                AttendanceRecord.org_id == org.id,
            ).limit(1)
        )).scalar_one_or_none()
        if already:
            continue

        # Student-specific seed so Amara's pattern differs from Biodun's.
        rng = random.Random(f"att:{student.id}")
        for day in dates:
            roll = rng.random()
            if roll < 0.08:
                status = AttendanceStatus.ABSENT
            elif roll < 0.18:
                status = AttendanceStatus.LATE
            else:
                status = AttendanceStatus.PRESENT
            db.add(AttendanceRecord(
                student_id=student.id,
                class_id=student.class_id,
                date=day,
                status=status,
                notes=None,
                org_id=org.id,
            ))
            created += 1

    # Top-up: ensure every student has an attendance row for today as well,
    # so the executive dashboard's "Attendance today" reads a non-zero
    # number out of the box. Skip students who already have a today row
    # (idempotent on re-run within the same day).
    for idx, student in enumerate(students):
        already_today = (await db.execute(
            select(AttendanceRecord.id).where(
                AttendanceRecord.student_id == student.id,
                AttendanceRecord.org_id == org.id,
                AttendanceRecord.date == today,
            ).limit(1)
        )).scalar_one_or_none()
        if already_today:
            continue
        rng = random.Random(f"att-today:{student.id}")
        roll = rng.random()
        if roll < 0.1:
            status = AttendanceStatus.ABSENT
        elif roll < 0.2:
            status = AttendanceStatus.LATE
        else:
            status = AttendanceStatus.PRESENT
        db.add(AttendanceRecord(
            student_id=student.id,
            class_id=student.class_id,
            date=today,
            status=status,
            notes=None,
            org_id=org.id,
        ))
        created += 1

    if created:
        await db.flush()
    return created


async def _seed_demo_grades(
    db,
    org: Organization,
    students: list[Student],
    subjects: list[Subject],
    teacher_id: str,
) -> int:
    """Seed one published grade per student per subject so the parent home
    and student home have a 'latest grade' to show."""
    if not subjects:
        return 0
    letter_scale = [
        (90, "A+"), (80, "A"), (70, "B+"), (60, "B"),
        (50, "C"), (40, "D"), (0, "E"),
    ]
    created = 0
    for student in students:
        already = (await db.execute(
            select(Grade.id).where(
                Grade.student_id == student.id,
                Grade.org_id == org.id,
            ).limit(1)
        )).scalar_one_or_none()
        if already:
            continue

        rng = random.Random(f"grade:{student.id}")
        for subject in subjects:
            score = round(rng.uniform(55, 92), 1)
            letter = next(l for threshold, l in letter_scale if score >= threshold)
            db.add(Grade(
                student_id=student.id,
                subject_id=subject.id,
                term="Term 1",
                score=score,
                max_score=100.0,
                grade_letter=letter,
                status=GradeStatus.PUBLISHED,
                graded_by=teacher_id,
                org_id=org.id,
            ))
            created += 1

    if created:
        await db.flush()
    return created


async def _seed_demo_lesson_plans(
    db,
    org: Organization,
    *,
    school_class: SchoolClass,
    maths: Subject,
    english: Subject | None,
    form_teacher: User,
    dual_role_user: User | None,
) -> int:
    """Seed a week of lesson plans across Maths + English so the planner grid
    is populated for the demo. Dates span (today-2 .. today+4) to give the
    "this week" view five non-empty days. Idempotent per (subject, date)."""
    created = 0
    today = date.today()
    # Build 5 school days centred on today (Mon..Fri-ish — we don't shift for
    # weekends because the demo runs on any weekday and the grid view filters
    # weekdays on the frontend anyway).
    day_offsets = [-2, -1, 0, 1, 2]

    MATHS_CONTENT = [
        ("Quadratic equations — worked examples",
         "Students can factorise quadratic expressions and solve by the formula.",
         "Recap factoring → guided examples on the board → paired problem-solving → class review.",
         "Whiteboard, textbook pp. 82–88, worksheet handout.",
         "Textbook exercise 4C, questions 1–10. Submit Friday."),
        ("Graphing parabolas",
         "Students plot y = ax² + bx + c for given a, b, c; identify vertex and axis of symmetry.",
         "Demonstrate on projector → students plot one parabola each → peer-check tables of values.",
         "Graph paper, projector, notebooks.",
         "Plot three parabolas at home; label vertex and roots."),
        ("Word problems — applications",
         "Convert real-world scenarios into quadratic equations.",
         "Guided walkthrough of 2 problems → group work on 4 problems → present 1 per group.",
         "Scenario cards (packs of 4), calculators.",
         "One-page reflection: where did you see quadratics this week?"),
        ("Simultaneous equations — substitution",
         "Solve pairs of linear equations by substitution.",
         "Review last lesson → modelled example → timed pair practice → wrap-up.",
         "Textbook pp. 92–95, timer.",
         "Exercise 5A, odd-numbered questions."),
        ("Simultaneous equations — elimination",
         "Solve pairs of linear equations by elimination.",
         "Contrast with substitution → modelled example → independent practice.",
         "Textbook pp. 96–99.",
         "Exercise 5B, questions 1–6. Bring questions Friday."),
    ]
    ENGLISH_CONTENT = [
        ("Comprehension — 'A Man of the People' ch. 1",
         "Students summarise chapter 1 and identify the protagonist's motivations.",
         "Silent reading → paired discussion → guided questions on the board.",
         "Novel copies, whiteboard.",
         "Write a 150-word summary of chapter 1."),
        ("Descriptive writing — market scene",
         "Students use the five senses to write vivid descriptions.",
         "Model paragraph → brainstorm sensory words → 20-minute writing → peer-share.",
         "Sample texts, notebooks.",
         "Expand your paragraph into 250 words for homework."),
        ("Poetry — imagery and metaphor",
         "Identify and interpret imagery in a short poem.",
         "Read aloud → annotate together → discuss in groups → share findings.",
         "Poem handout ('Night Rain'), highlighters.",
         "Write your own 4-line poem using one metaphor."),
        ("Grammar — subject-verb agreement",
         "Apply SVA rules to tricky constructions (collective nouns, indefinite pronouns).",
         "Quick quiz → rules revision → sentence-correction drills.",
         "Grammar sheet, marker pens.",
         "Complete grammar worksheet B."),
        ("Oral composition — class presentation",
         "Students deliver a 2-minute talk on a chosen topic.",
         "Brief speaker intros → 2-min presentations → peer feedback.",
         "Stopwatch, feedback rubric.",
         "Reflect in journal on what you learned from peers."),
    ]

    async def _add_plan(subject: Subject | None, teacher: User | None, title: str, objectives: str, activities: str, materials: str, homework: str, lesson_date: date, period: int, status: LessonPlanStatus) -> None:
        nonlocal created
        if not subject or not teacher:
            return
        existing = (await db.execute(
            select(LessonPlan.id).where(
                LessonPlan.org_id == org.id,
                LessonPlan.class_id == school_class.id,
                LessonPlan.subject_id == subject.id,
                LessonPlan.lesson_date == lesson_date,
                LessonPlan.is_deleted == False,
            ).limit(1)
        )).scalar_one_or_none()
        if existing:
            return
        db.add(LessonPlan(
            title=title,
            class_id=school_class.id,
            subject_id=subject.id,
            teacher_id=teacher.id,
            lesson_date=lesson_date,
            period=period,
            duration_minutes=45,
            objectives=objectives,
            activities=activities,
            materials=materials,
            homework=homework,
            status=status,
            org_id=org.id,
        ))
        created += 1

    for idx, offset in enumerate(day_offsets):
        lesson_date = today + timedelta(days=offset)
        # Past lessons published, today + future stay draft (demo signal:
        # "this teacher keeps their planner up to date AND has upcoming lessons to polish").
        status = LessonPlanStatus.PUBLISHED if offset < 0 else LessonPlanStatus.DRAFT

        m = MATHS_CONTENT[idx % len(MATHS_CONTENT)]
        await _add_plan(maths, form_teacher, m[0], m[1], m[2], m[3], m[4], lesson_date, period=1, status=status)

        e = ENGLISH_CONTENT[idx % len(ENGLISH_CONTENT)]
        await _add_plan(english, dual_role_user, e[0], e[1], e[2], e[3], e[4], lesson_date, period=3, status=status)

    if created:
        await db.flush()
    return created


async def _seed_demo_library(
    db,
    org: Organization,
    *,
    students_by_name: dict[str, Student],
    teacher: User,
    admin: User,
) -> tuple[int, int]:
    """Seed a believable library: ~12 titles across categories, with a
    mix of popular African literature, science, maths texts and reference
    books. Then issue loans for ~5 students so the demo shows activity.
    Idempotent by (title, org)."""
    books_added = 0
    loans_added = 0

    # (title, author, category, total_copies, shelf, year)
    CATALOGUE = [
        ("Things Fall Apart", "Chinua Achebe", "Fiction", 4, "A1-12", 1958),
        ("Half of a Yellow Sun", "Chimamanda Ngozi Adichie", "Fiction", 3, "A1-14", 2006),
        ("Purple Hibiscus", "Chimamanda Ngozi Adichie", "Fiction", 3, "A1-15", 2003),
        ("The African Child", "Camara Laye", "Fiction", 2, "A1-18", 1953),
        ("New General Mathematics — SS1", "M. F. Macrae et al.", "Mathematics", 6, "C2-04", 2018),
        ("Essential Further Mathematics", "Tuttuh-Adegun et al.", "Mathematics", 4, "C2-06", 2017),
        ("Senior Secondary Physics", "Okeke P.N.", "Science", 5, "B3-08", 2020),
        ("Modern Chemistry for Senior Secondary", "Ababio O.Y.", "Science", 5, "B3-11", 2019),
        ("Comprehensive Biology", "Stone R.H., Cozens A.B.", "Science", 4, "B3-13", 2015),
        ("Oxford Advanced Learner's Dictionary", "Oxford University Press", "Reference", 3, "R1-02", 2020),
        ("Round-up English: A Complete Guide", "Virginia Evans", "Reference", 4, "R1-04", 2016),
        ("A Concise History of West Africa", "Eliphas G. Mukonoweshuro", "History", 2, "H2-01", 2008),
    ]

    for (title, author, category, total, shelf, year) in CATALOGUE:
        exists = (await db.execute(
            select(LibraryBook.id).where(
                LibraryBook.org_id == org.id,
                LibraryBook.title == title,
                LibraryBook.is_deleted == False,
            ).limit(1)
        )).scalar_one_or_none()
        if exists:
            continue
        db.add(LibraryBook(
            title=title,
            author=author,
            category=category,
            total_copies=total,
            available_copies=total,
            shelf_location=shelf,
            publication_year=year,
            publisher=None,
            description=None,
            org_id=org.id,
        ))
        books_added += 1
    if books_added:
        await db.flush()

    # Loans — fetch the books we just created (or skip if no students seeded).
    if not students_by_name:
        return (books_added, 0)

    books_by_title = {
        b.title: b
        for b in (await db.execute(
            select(LibraryBook).where(
                LibraryBook.org_id == org.id,
                LibraryBook.is_deleted == False,
            )
        )).scalars().all()
    }

    today = date.today()

    # Each tuple: (student display name, book title, days relative to today for due_date, returned?)
    # Mix: 1 overdue, 1 due-today, 3 healthy upcoming, 3 already returned.
    LOAN_PLAN = [
        # Active
        ("Amara Okeke",   "Half of a Yellow Sun",        +5,  False),
        ("Biodun Adeleke","New General Mathematics — SS1", +12, False),
        ("Chipo Mutasa",  "Senior Secondary Physics",    +3,  False),
        ("Daniel Mwangi", "Things Fall Apart",           -4,  False),  # OVERDUE
        ("Esi Boateng",   "Purple Hibiscus",              0,  False),  # due today
        # Returned history
        ("Fatima Bello",          "Modern Chemistry for Senior Secondary", -10, True),
        ("Amara Okeke",           "Oxford Advanced Learner's Dictionary",  -18, True),
        ("Biodun Adeleke",        "Comprehensive Biology",                 -22, True),
    ]

    for (student_name, book_title, due_offset_days, returned) in LOAN_PLAN:
        student = students_by_name.get(student_name)
        book = books_by_title.get(book_title)
        if not student or not book or not student.user_id:
            continue
        # Idempotency: one active loan per (student, book). Previous runs keep.
        existing_active = (await db.execute(
            select(LibraryLoan.id).where(
                LibraryLoan.org_id == org.id,
                LibraryLoan.book_id == book.id,
                LibraryLoan.borrower_user_id == student.user_id,
                LibraryLoan.status == (LoanStatus.RETURNED if returned else LoanStatus.BORROWED),
            ).limit(1)
        )).scalar_one_or_none()
        if existing_active:
            continue
        due = today + timedelta(days=due_offset_days)
        borrowed_at = datetime.now(timezone.utc) - timedelta(days=max(1, 14 - due_offset_days if not returned else 21))
        loan = LibraryLoan(
            book_id=book.id,
            borrower_user_id=student.user_id,
            issued_by=admin.id,
            due_date=due,
            borrowed_at=borrowed_at,
            status=LoanStatus.RETURNED if returned else LoanStatus.BORROWED,
            returned_at=(datetime.now(timezone.utc) - timedelta(days=2)) if returned else None,
            org_id=org.id,
        )
        db.add(loan)
        if not returned:
            # Respect the invariant. Clamp at 0 defensively.
            book.available_copies = max(0, book.available_copies - 1)
        loans_added += 1
    if loans_added:
        await db.flush()
    return (books_added, loans_added)


async def _seed_demo_transport(
    db,
    org: Organization,
    *,
    students_by_name: dict[str, Student],
    admin: User,
) -> tuple[int, int, int]:
    """Seed an operational transport setup for Fairview:
    2 vehicles, 2 drivers, 2 routes (Northside + Southside) with 3 stops each,
    6 students assigned across both routes, and today's morning trip already
    in-progress with a realistic mix of boarding states + an afternoon trip
    planned. Idempotent per (vehicle reg / driver name / route name).

    Returns (routes_added, students_assigned, trips_added)."""
    routes_added = 0
    assignments_added = 0
    trips_added = 0

    # ── Vehicles ────────────────────────────────────────────────────────────
    VEHICLES = [
        {"reg": "FV-BUS-01", "make": "Toyota", "model": "Coaster", "color": "White/Blue", "capacity": 18, "fuel": "diesel"},
        {"reg": "FV-BUS-02", "make": "Mercedes-Benz", "model": "Sprinter", "color": "White", "capacity": 14, "fuel": "diesel"},
    ]
    vehicles_by_reg: dict[str, TransportVehicle] = {}
    for v in VEHICLES:
        existing = (await db.execute(
            select(TransportVehicle).where(
                TransportVehicle.org_id == org.id,
                TransportVehicle.registration_number == v["reg"],
                TransportVehicle.is_deleted == False,
            )
        )).scalar_one_or_none()
        if existing:
            vehicles_by_reg[v["reg"]] = existing
            continue
        veh = TransportVehicle(
            registration_number=v["reg"],
            make=v["make"],
            model=v["model"],
            color=v["color"],
            capacity=v["capacity"],
            fuel_type=v["fuel"],
            status=VehicleStatus.ACTIVE,
            last_serviced_at=date.today() - timedelta(days=21),
            org_id=org.id,
        )
        db.add(veh)
        await db.flush()
        vehicles_by_reg[v["reg"]] = veh

    # ── Drivers ─────────────────────────────────────────────────────────────
    DRIVERS = [
        {"name": "Musa Garba", "phone": "+2348012345070", "license": "FCT-DR-002411", "expiry_days": 420},
        {"name": "Tunde Bakare", "phone": "+2348012345071", "license": "LAG-DR-009387", "expiry_days": 280},
    ]
    drivers_by_name: dict[str, TransportDriver] = {}
    for d in DRIVERS:
        existing = (await db.execute(
            select(TransportDriver).where(
                TransportDriver.org_id == org.id,
                TransportDriver.full_name == d["name"],
                TransportDriver.is_deleted == False,
            )
        )).scalar_one_or_none()
        if existing:
            drivers_by_name[d["name"]] = existing
            continue
        drv = TransportDriver(
            full_name=d["name"],
            phone=d["phone"],
            license_number=d["license"],
            license_expiry=date.today() + timedelta(days=d["expiry_days"]),
            is_active=True,
            org_id=org.id,
        )
        db.add(drv)
        await db.flush()
        drivers_by_name[d["name"]] = drv

    # ── Routes + stops ──────────────────────────────────────────────────────
    ROUTES = [
        {
            "name": "Northside Route",
            "code": "RT-N1",
            "vehicle_reg": "FV-BUS-01",
            "driver": "Musa Garba",
            "morning": "06:30",
            "afternoon": "15:15",
            "stops": [
                {"name": "Maitama Park",   "address": "Aguiyi Ironsi Way, Maitama", "am": "06:35", "pm": "15:55"},
                {"name": "Wuse II Plaza",  "address": "Aminu Kano Crescent, Wuse 2", "am": "06:50", "pm": "15:40"},
                {"name": "Garki Roundabout","address": "Ahmadu Bello Way, Garki",    "am": "07:05", "pm": "15:25"},
                {"name": "Fairview Gate",  "address": "School premises",             "am": "07:25", "pm": "15:15"},
            ],
            "students": ["Amara Okeke", "Biodun Adeleke", "Chipo Mutasa"],
        },
        {
            "name": "Southside Route",
            "code": "RT-S1",
            "vehicle_reg": "FV-BUS-02",
            "driver": "Tunde Bakare",
            "morning": "06:45",
            "afternoon": "15:20",
            "stops": [
                {"name": "Lugbe Phase 1",   "address": "Federal Housing, Lugbe", "am": "06:50", "pm": "16:10"},
                {"name": "Apo Quarters",    "address": "Apo Mechanic Village",    "am": "07:05", "pm": "15:55"},
                {"name": "Area 11 Junction","address": "Wadata Plaza, Area 11",   "am": "07:18", "pm": "15:35"},
                {"name": "Fairview Gate",   "address": "School premises",         "am": "07:30", "pm": "15:20"},
            ],
            "students": ["Daniel Mwangi", "Esi Boateng", "Fatima Bello"],
        },
    ]

    routes_by_code: dict[str, TransportRoute] = {}
    stop_lookup: dict[tuple[str, str], TransportStop] = {}  # (route_code, stop_name) → stop

    for plan in ROUTES:
        existing = (await db.execute(
            select(TransportRoute).where(
                TransportRoute.org_id == org.id,
                TransportRoute.code == plan["code"],
                TransportRoute.is_deleted == False,
            )
        )).scalar_one_or_none()
        if existing:
            routes_by_code[plan["code"]] = existing
            # Make sure existing stops are loaded into the lookup
            stops = (await db.execute(
                select(TransportStop).where(TransportStop.route_id == existing.id)
            )).scalars().all()
            for s in stops:
                stop_lookup[(plan["code"], s.name)] = s
            continue

        route = TransportRoute(
            name=plan["name"],
            code=plan["code"],
            vehicle_id=vehicles_by_reg[plan["vehicle_reg"]].id,
            driver_id=drivers_by_name[plan["driver"]].id,
            morning_start_time=plan["morning"],
            afternoon_start_time=plan["afternoon"],
            is_active=True,
            org_id=org.id,
        )
        db.add(route)
        await db.flush()
        routes_added += 1
        routes_by_code[plan["code"]] = route

        for idx, sp in enumerate(plan["stops"], start=1):
            stop = TransportStop(
                route_id=route.id,
                sequence=idx,
                name=sp["name"],
                address=sp["address"],
                morning_pickup_time=sp["am"],
                afternoon_dropoff_time=sp["pm"],
                org_id=org.id,
            )
            db.add(stop)
            await db.flush()
            stop_lookup[(plan["code"], sp["name"])] = stop

    # ── Student assignments ─────────────────────────────────────────────────
    for plan in ROUTES:
        route = routes_by_code[plan["code"]]
        # All students on a route board at the FIRST stop and disembark at
        # the LAST stop (Fairview Gate) for the demo.
        first_stop = stop_lookup[(plan["code"], plan["stops"][0]["name"])]
        last_stop = stop_lookup[(plan["code"], plan["stops"][-1]["name"])]
        for name in plan["students"]:
            student = students_by_name.get(name)
            if not student:
                continue
            existing = (await db.execute(
                select(StudentRouteAssignment).where(
                    StudentRouteAssignment.student_id == student.id,
                    StudentRouteAssignment.route_id == route.id,
                )
            )).scalar_one_or_none()
            if existing:
                continue
            db.add(StudentRouteAssignment(
                student_id=student.id,
                route_id=route.id,
                pickup_stop_id=first_stop.id,
                dropoff_stop_id=last_stop.id,
                is_active=True,
                org_id=org.id,
            ))
            assignments_added += 1
    if assignments_added:
        await db.flush()

    # ── Today's trips: morning IN_PROGRESS with realistic boarding states,
    #    afternoon PLANNED. Idempotent per (route, today, direction). ───────
    today = date.today()
    now = datetime.now(timezone.utc)

    for plan in ROUTES:
        route = routes_by_code[plan["code"]]

        # Morning trip — in-progress, started 30 min ago, mid-route.
        morning_existing = (await db.execute(
            select(TransportTrip).where(
                TransportTrip.route_id == route.id,
                TransportTrip.trip_date == today,
                TransportTrip.direction == TripDirection.MORNING,
            )
        )).scalar_one_or_none()
        if not morning_existing:
            morning_trip = TransportTrip(
                route_id=route.id,
                trip_date=today,
                direction=TripDirection.MORNING,
                status=TripStatus.IN_PROGRESS,
                vehicle_id=route.vehicle_id,
                driver_id=route.driver_id,
                started_at=now - timedelta(minutes=30),
                org_id=org.id,
            )
            db.add(morning_trip)
            await db.flush()
            trips_added += 1

            # Pre-spawn boardings from active assignments
            assignments = (await db.execute(
                select(StudentRouteAssignment).where(
                    StudentRouteAssignment.route_id == route.id,
                    StudentRouteAssignment.is_active == True,
                )
            )).scalars().all()

            # Realistic mix:
            # - First N-1 students BOARDED (already on the bus)
            # - 1 ABSENT (didn't show up at the stop)
            # The Northside trip will additionally have a SKIPPED status on
            # one student to drive the "delays/issues" panel on the dashboard.
            for idx, a in enumerate(assignments):
                rng = random.Random(f"{plan['code']}:{a.student_id}")
                roll = rng.random()
                if plan["code"] == "RT-N1" and idx == 0:
                    status = BoardingStatus.SKIPPED
                    notes = "Stop missed — driver re-routed for road closure"
                elif idx == len(assignments) - 1 and roll < 0.5:
                    status = BoardingStatus.ABSENT
                    notes = "Parent reported child absent today"
                else:
                    status = BoardingStatus.BOARDED
                    notes = None
                db.add(TripBoarding(
                    trip_id=morning_trip.id,
                    student_id=a.student_id,
                    pickup_stop_id=a.pickup_stop_id,
                    dropoff_stop_id=a.dropoff_stop_id,
                    status=status,
                    event_at=now - timedelta(minutes=15) if status != BoardingStatus.EXPECTED else None,
                    recorded_by=admin.id if status != BoardingStatus.EXPECTED else None,
                    notes=notes,
                    org_id=org.id,
                ))

        # Afternoon trip — planned (not yet started)
        afternoon_existing = (await db.execute(
            select(TransportTrip).where(
                TransportTrip.route_id == route.id,
                TransportTrip.trip_date == today,
                TransportTrip.direction == TripDirection.AFTERNOON,
            )
        )).scalar_one_or_none()
        if not afternoon_existing:
            afternoon_trip = TransportTrip(
                route_id=route.id,
                trip_date=today,
                direction=TripDirection.AFTERNOON,
                status=TripStatus.PLANNED,
                vehicle_id=route.vehicle_id,
                driver_id=route.driver_id,
                org_id=org.id,
            )
            db.add(afternoon_trip)
            await db.flush()
            trips_added += 1

            assignments = (await db.execute(
                select(StudentRouteAssignment).where(
                    StudentRouteAssignment.route_id == route.id,
                    StudentRouteAssignment.is_active == True,
                )
            )).scalars().all()
            for a in assignments:
                db.add(TripBoarding(
                    trip_id=afternoon_trip.id,
                    student_id=a.student_id,
                    pickup_stop_id=a.pickup_stop_id,
                    dropoff_stop_id=a.dropoff_stop_id,
                    status=BoardingStatus.EXPECTED,
                    org_id=org.id,
                ))

    if trips_added:
        await db.flush()

    return routes_added, assignments_added, trips_added


async def _seed_demo_sms(
    db,
    org: Organization,
    *,
    admin: User,
    teacher: User,
    school_class: SchoolClass,
) -> int:
    """Seed a handful of past SMS campaigns so the Logs tab has something
    real to show on demo day. Idempotent by campaign `subject` (our internal
    label) — rerunning the script won't duplicate."""

    # Precompute recipient pools. Each entry: (users, label, target_type, target_value)
    def _pool(slug_or_type: str) -> list[User]:
        return []

    # Materialise pools with actual users+phones.
    students = list((await db.execute(
        select(User).join(User.roles).where(
            User.org_id == org.id,
            User.phone.isnot(None),
            User.phone != "",
            Role.slug == "student",
        ).distinct()
    )).scalars().all())

    parents = list((await db.execute(
        select(User).join(User.roles).where(
            User.org_id == org.id,
            User.phone.isnot(None),
            User.phone != "",
            Role.slug == "parent",
        ).distinct()
    )).scalars().all())

    teachers = list((await db.execute(
        select(User).join(User.roles).where(
            User.org_id == org.id,
            User.phone.isnot(None),
            User.phone != "",
            Role.slug == "teacher",
        ).distinct()
    )).scalars().all())

    from app.services.sms import default_sender_id
    sender = default_sender_id(org.name)

    PLAN = [
        {
            "subject": "Early dismissal notice",
            "body": (
                "Dear parents, school closes early tomorrow for teacher "
                "training. Pickup from 11:30 AM. — Fairview School"
            ),
            "target_type": SmsTargetType.ALL_PARENTS,
            "target_value": None,
            "target_label": "All parents",
            "recipients": parents,
            "created_by": admin,
            "days_ago": 4,
            # Distribution: 100% delivered for this one — crisp demo moment.
            "failure_mode": "none",
        },
        {
            "subject": "Maths test reminder",
            "body": (
                "Reminder: Maths test next Monday. Cover chapters 3 to 5. "
                "Bring a calculator. — Mr. Adeyemi"
            ),
            "target_type": SmsTargetType.CLASS,
            "target_value": school_class.id,
            "target_label": f"Students in {school_class.name}",
            "recipients": students,  # Grade 10A = all seeded students
            "created_by": teacher,
            "days_ago": 2,
            "failure_mode": "none",
        },
        {
            "subject": "Staff meeting today",
            "body": (
                "Staff meeting today at 3 PM in the staff room. "
                "Please bring your term plans. — Admin"
            ),
            "target_type": SmsTargetType.ALL_TEACHERS,
            "target_value": None,
            "target_label": "All teachers",
            "recipients": teachers,
            "created_by": admin,
            "days_ago": 1,
            "failure_mode": "none",
        },
        {
            "subject": "Term 1 fees reminder",
            "body": (
                "Fairview School: Term 1 school fees installment is due "
                "Friday. Please pay at the accounts office. Thank you."
            ),
            "target_type": SmsTargetType.ALL_PARENTS,
            "target_value": None,
            "target_label": "All parents",
            "recipients": parents,
            "created_by": admin,
            "days_ago": 0,
            "failure_mode": "one",  # exactly one recipient fails
        },
    ]

    created = 0
    for plan in PLAN:
        if not plan["recipients"]:
            continue
        # Idempotency: skip if a campaign with same subject already exists.
        existing = (await db.execute(
            select(SmsCampaign.id).where(
                SmsCampaign.org_id == org.id,
                SmsCampaign.subject == plan["subject"],
            ).limit(1)
        )).scalar_one_or_none()
        if existing:
            continue

        sent_at = datetime.now(timezone.utc) - timedelta(days=plan["days_ago"], hours=2)
        recipients: list[User] = plan["recipients"]

        # Figure failures up front so counters are consistent.
        failures: set[str] = set()
        if plan["failure_mode"] == "one" and len(recipients) >= 2:
            failures = {recipients[-1].id}

        sent = len(recipients)
        delivered = sum(1 for u in recipients if u.id not in failures)
        failed = sum(1 for u in recipients if u.id in failures)

        campaign = SmsCampaign(
            subject=plan["subject"],
            body=plan["body"],
            sender_id=sender,
            provider="mock",
            created_by=plan["created_by"].id,
            target_type=plan["target_type"],
            target_value=plan["target_value"],
            target_label=plan["target_label"],
            total_recipients=len(recipients),
            sent_count=sent,
            delivered_count=delivered,
            failed_count=failed,
            status=SmsCampaignStatus.COMPLETED,
            completed_at=sent_at,
            org_id=org.id,
        )
        # Override created_at so it reads nicely in the logs list.
        campaign.created_at = sent_at
        db.add(campaign)
        await db.flush()

        for u in recipients:
            is_failed = u.id in failures
            db.add(SmsMessage(
                campaign_id=campaign.id,
                recipient_user_id=u.id,
                recipient_name=u.full_name,
                recipient_phone=u.phone or "",
                status=SmsMessageStatus.FAILED if is_failed else SmsMessageStatus.DELIVERED,
                provider_message_id=f"mock_seed_{campaign.id[:6]}_{u.id[:6]}",
                error_message="Handset unreachable" if is_failed else None,
                sent_at=sent_at,
                delivered_at=None if is_failed else sent_at,
                org_id=org.id,
            ))
        created += 1

    if created:
        await db.flush()
    return created


# ── Core classroom seed ─────────────────────────────────────────────────────


async def _seed_school_classroom(db, org: Organization, admin: User, roles_by_slug: dict[str, Role]) -> list[str]:
    """Seed (or top up) classroom content for the Fairview demo.

    Every sub-step is idempotent. Re-running picks up missing roles, links
    students to users, adds parent rows, etc. — no need to wipe the DB.
    """
    lines: list[str] = []

    teacher_role = roles_by_slug["teacher"]
    student_role = roles_by_slug["student"]
    parent_role = roles_by_slug["parent"]

    # ── Form teacher (Funke Adeyemi) ───────────────────────────────────────
    teacher = await _ensure_user(
        db, org,
        email="teacher@demo-school.example.com",
        full_name="Funke Adeyemi",
        roles=[teacher_role],
        phone="+2348012345001",
    )

    # ── Mathematics subject ────────────────────────────────────────────────
    maths = (await db.execute(
        select(Subject).where(
            Subject.org_id == org.id,
            Subject.code == "MATH10",
        )
    )).scalar_one_or_none()
    if not maths:
        maths = Subject(
            name="Mathematics",
            code="MATH10",
            description="Grade 10 Mathematics — algebra, geometry, introductory calculus.",
            teacher_id=teacher.id,
            org_id=org.id,
        )
        db.add(maths)
        await db.flush()
    elif maths.teacher_id != teacher.id:
        maths.teacher_id = teacher.id
        await db.flush()

    # ── Grade 10A class ────────────────────────────────────────────────────
    school_class = (await db.execute(
        select(SchoolClass).where(
            SchoolClass.org_id == org.id,
            SchoolClass.name == "Year 10A",
        )
    )).scalar_one_or_none()
    if not school_class:
        school_class = SchoolClass(
            name="Year 10A",
            level="Secondary",
            academic_year="2025/2026",
            teacher_id=teacher.id,
            room="Room 204",
            max_capacity=40,
            org_id=org.id,
        )
        db.add(school_class)
        await db.flush()
    elif school_class.teacher_id != teacher.id:
        school_class.teacher_id = teacher.id
        await db.flush()

    # ── Students — one User per student, plus Student row, all linked ──────
    student_rows: list[Student] = []
    for idx, (first, last, gender) in enumerate(DEMO_STUDENTS, start=1):
        slug_name = f"{first}.{last}".lower()
        email = f"{slug_name}@demo-school.example.com"

        stu_user = await _ensure_user(
            db, org,
            email=email,
            full_name=_fullname(first, last),
            roles=[student_role],
            phone=f"+23480123450{10 + idx:02d}",
        )

        student = (await db.execute(
            select(Student).where(
                Student.org_id == org.id,
                Student.first_name == first,
                Student.last_name == last,
            )
        )).scalar_one_or_none()
        if not student:
            student = Student(
                student_id=f"FV-{10_000 + idx}",
                first_name=first,
                last_name=last,
                email=email,
                gender=gender,
                class_id=school_class.id,
                admission_date=date.today() - timedelta(days=120),
                is_active=True,
                org_id=org.id,
            )
            db.add(student)
            await db.flush()
        elif not student.gender:
            # Back-fill gender on rows seeded before Phase 6.8 — idempotent.
            student.gender = gender
            await db.flush()
        if student.class_id != school_class.id:
            student.class_id = school_class.id
        await _link_student_to_user(db, student, stu_user)
        student_rows.append(student)

    students_by_name = {f"{s.first_name} {s.last_name}": s for s in student_rows}

    # ── Timetable slot for the current hour (Maths) ────────────────────────
    now = datetime.now()
    start_hour = now.hour
    end_hour = min(23, start_hour + 1)
    math_slot = (await db.execute(
        select(Timetable).where(
            Timetable.class_id == school_class.id,
            Timetable.subject_id == maths.id,
            Timetable.day_of_week == now.weekday(),
        )
    )).scalar_one_or_none()
    if not math_slot:
        math_slot = Timetable(
            class_id=school_class.id,
            subject_id=maths.id,
            day_of_week=now.weekday(),
            start_time=f"{start_hour:02d}:00",
            end_time=f"{end_hour:02d}:00",
            room="Room 204",
            teacher_id=teacher.id,
            org_id=org.id,
        )
        db.add(math_slot)
        await db.flush()

    # ── Parents + dual-role user (Phase 6.3 headline feature) ──────────────
    # Create each PARENT_PLAN user. Dual-role is resolved here too — we just
    # set an extra role slug on the User and, below, create their Subject.
    dual_role_user: User | None = None
    for p_idx, plan in enumerate(PARENT_PLAN, start=1):
        extra_slug = "teacher" if plan["is_dual_role"] else None
        parent_user = await _ensure_user(
            db, org,
            email=plan["email"],
            full_name=plan["full_name"],
            roles=[parent_role],
            extra_role_slug=extra_slug,
            phone=f"+23480123450{30 + p_idx:02d}",
        )
        if plan["is_dual_role"]:
            dual_role_user = parent_user

        for child_name in plan["children"]:
            child = students_by_name.get(child_name)
            if not child:
                continue
            await _ensure_parent_guardian(
                db, org, parent_user, child,
                relationship_type=plan["relationship"],
                # First child listed = primary contact for SMS/email.
                is_primary=(plan["children"][0] == child_name),
            )

    # ── English subject for the dual-role user + timetable slot ────────────
    english: Subject | None = None
    if dual_role_user:
        english = (await db.execute(
            select(Subject).where(
                Subject.org_id == org.id,
                Subject.code == DUAL_ROLE_SUBJECT["code"],
            )
        )).scalar_one_or_none()
        if not english:
            english = Subject(
                name=DUAL_ROLE_SUBJECT["name"],
                code=DUAL_ROLE_SUBJECT["code"],
                description=DUAL_ROLE_SUBJECT["description"],
                teacher_id=dual_role_user.id,
                org_id=org.id,
            )
            db.add(english)
            await db.flush()
        elif english.teacher_id != dual_role_user.id:
            english.teacher_id = dual_role_user.id
            await db.flush()

        # English timetable slot on today so the dual-role user's Teacher
        # home isn't empty during a live demo. 10:00 is early-morning-safe and
        # won't collide with the dynamic Maths slot that tracks the current hour.
        english_day = now.weekday()
        english_slot = (await db.execute(
            select(Timetable).where(
                Timetable.class_id == school_class.id,
                Timetable.subject_id == english.id,
                Timetable.day_of_week == english_day,
            )
        )).scalar_one_or_none()
        if english_slot and english_slot.day_of_week != english_day:
            # Older seeds parked this on "tomorrow" — correct it idempotently.
            english_slot.day_of_week = english_day
            await db.flush()
        elif not english_slot:
            db.add(Timetable(
                class_id=school_class.id,
                subject_id=english.id,
                day_of_week=english_day,
                start_time="10:00",
                end_time="11:00",
                room="Room 204",
                teacher_id=dual_role_user.id,
                org_id=org.id,
            ))
            await db.flush()

    # ── Attendance + grades — so role dashboards aren't empty ──────────────
    att_added = await _seed_demo_attendance(db, org, student_rows)
    grade_added = await _seed_demo_grades(
        db, org, student_rows,
        [s for s in [maths, english] if s is not None],
        teacher.id,
    )

    # ── Lesson plans (Phase 6.4) ───────────────────────────────────────────
    # Seed a believable week of lesson plans for both teachers so the planner
    # lands on a populated weekly grid, not a blank canvas. Idempotent — we
    # bail per (class, subject, date) if a plan already exists.
    lesson_plans_added = await _seed_demo_lesson_plans(
        db, org, school_class=school_class,
        maths=maths, english=english,
        form_teacher=teacher, dual_role_user=dual_role_user,
    )

    # Seed a handful of DRAFT grades on English so the dual-role teacher home
    # shows a non-zero "Pending Grades" stat. Draft = still to review/publish.
    pending_added = 0
    if english and dual_role_user:
        for student in student_rows[:3]:
            already_draft = (await db.execute(
                select(Grade.id).where(
                    Grade.student_id == student.id,
                    Grade.subject_id == english.id,
                    Grade.status == GradeStatus.DRAFT,
                ).limit(1)
            )).scalar_one_or_none()
            if already_draft:
                continue
            rng = random.Random(f"draft-eng:{student.id}")
            db.add(Grade(
                student_id=student.id,
                subject_id=english.id,
                term="Term 1",
                score=round(rng.uniform(55, 88), 1),
                max_score=100.0,
                grade_letter=None,
                status=GradeStatus.DRAFT,
                graded_by=dual_role_user.id,
                org_id=org.id,
            ))
            pending_added += 1
        if pending_added:
            await db.flush()

    # ── Past Live session (unchanged from pre-6.3 — demo-visible history) ──
    any_live = (await db.execute(
        select(LiveSession.id).where(LiveSession.org_id == org.id).limit(1)
    )).scalar_one_or_none()
    if not any_live:
        past_end = datetime.now(timezone.utc) - timedelta(days=2)
        past_start = past_end - timedelta(minutes=42)
        past_session = LiveSession(
            org_id=org.id,
            host_user_id=teacher.id,
            title="Quadratic equations — worked examples",
            description="Walkthrough of the Tuesday homework set.",
            class_id=school_class.id,
            subject_id=maths.id,
            timetable_id=math_slot.id,
            is_active=False,
            started_at=past_start,
            ended_at=past_end,
        )
        db.add(past_session)
        await db.flush()
        for i, student in enumerate(student_rows[:4]):
            # Look up each student's User row to attribute attendance correctly.
            if not student.user_id:
                continue
            joined = past_start + timedelta(seconds=30 * i)
            left = past_end - timedelta(seconds=45 * i)
            db.add(LiveAttendance(
                org_id=org.id,
                session_id=past_session.id,
                user_id=student.user_id,
                joined_at=joined,
                left_at=left,
                duration_seconds=max(0, int((left - joined).total_seconds())),
            ))
        await db.flush()

    lines.append(f"seeded classroom (idempotent): {org.slug}")
    lines.append(f"  teacher={teacher.email} / {DEMO_PASSWORD}")
    lines.append(f"  class=Grade 10A, subjects=[Mathematics" + (", English Language" if english else "") + "]")
    lines.append(f"  students={len(student_rows)}, all linked to User rows")
    parent_summary = ", ".join(p['email'].split('@')[0] for p in PARENT_PLAN)
    lines.append(f"  parents={parent_summary}")
    if dual_role_user:
        lines.append(f"  DUAL-ROLE demo user: {dual_role_user.email} (teacher + parent)")
    if att_added or grade_added or lesson_plans_added:
        lines.append(
            f"  attendance rows added={att_added}, grade rows added={grade_added}, lesson plans added={lesson_plans_added}"
        )

    # ── Library (Phase 6.5) ────────────────────────────────────────────────
    books_added, loans_added = await _seed_demo_library(
        db, org,
        students_by_name=students_by_name,
        teacher=teacher,
        admin=admin,
    )
    if books_added or loans_added:
        lines.append(f"  library books added={books_added}, loans added={loans_added}")

    # ── SMS campaigns (Phase 6.6) ──────────────────────────────────────────
    sms_added = await _seed_demo_sms(
        db, org,
        admin=admin,
        teacher=teacher,
        school_class=school_class,
    )
    if sms_added:
        lines.append(f"  SMS campaigns added={sms_added}")

    # ── Transport (Phase 6.7) ──────────────────────────────────────────────
    routes_added, assignments_added, trips_added = await _seed_demo_transport(
        db, org,
        students_by_name=students_by_name,
        admin=admin,
    )
    if routes_added or assignments_added or trips_added:
        lines.append(
            f"  transport: routes={routes_added}, assignments={assignments_added}, trips={trips_added}"
        )

    return lines


# ── Tenant seed ─────────────────────────────────────────────────────────────


async def seed_one(db, demo: DemoOrg) -> list[str]:
    existing = (await db.execute(select(Organization).where(Organization.slug == demo.slug))).scalar_one_or_none()
    if existing:
        lines = [f"skip org (exists): {demo.slug}"]
        if existing.subscription_tier != demo.tier:
            existing.subscription_tier = demo.tier
            lines.append(f"  upgraded tier -> {demo.tier.value}")
        if existing.name != demo.name:
            prev = existing.name
            existing.name = demo.name
            lines.append(f"  renamed: {prev!r} -> {demo.name!r}")
        if demo.seed_classroom:
            roles_by_slug = await _ensure_roles(db, existing)
            admin = (await db.execute(
                select(User).where(User.email == demo.admin_email, User.org_id == existing.id)
            )).scalar_one_or_none()
            if admin:
                lines += await _seed_school_classroom(db, existing, admin, roles_by_slug)
        return lines

    org = Organization(
        name=demo.name,
        slug=demo.slug,
        industry=IndustryType(demo.industry),
        subscription_tier=demo.tier,
        modules_enabled=demo.modules,
        max_users=25,
    )
    db.add(org)
    await db.flush()

    roles_by_slug = await _ensure_roles(db, org)
    admin_role = roles_by_slug["org_admin"]
    admin = User(
        email=demo.admin_email,
        full_name=demo.admin_name,
        hashed_password=hash_password(DEMO_PASSWORD),
        org_id=org.id,
        status=UserStatus.ACTIVE,
        email_verified=True,
        roles=[admin_role],
    )
    db.add(admin)
    await db.flush()

    lines = [f"seeded: {demo.slug} (admin={demo.admin_email} / {DEMO_PASSWORD}, tier={demo.tier.value})"]
    if demo.seed_classroom:
        lines += await _seed_school_classroom(db, org, admin, roles_by_slug)
    return lines


async def main() -> int:
    await init_db()
    async with AsyncSessionLocal() as db:
        try:
            for demo in DEMOS:
                for line in await seed_one(db, demo):
                    print(line)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
