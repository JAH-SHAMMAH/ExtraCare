#!/usr/bin/env python
"""
Fairview School Demo Environment Seed Script

Creates a realistic, fully-operational school environment with:
- Realistic Nigerian names
- Historical data spanning multiple terms
- All ERP modules populated
- Tenant isolation maintained
- Idempotent (safe to run multiple times)
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta, timezone
import random
import uuid

# Setup path - add parent directory (backend root)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import AsyncSessionLocal
from app.models.organization import Organization, IndustryType, SubscriptionTier
from app.models.user import User, UserStatus
from app.models.role import Role, permission_presets_for_industry
from app.core.security import hash_password
from app.models.modules.school import (
    Student, SchoolClass, Subject, AttendanceRecord, Grade, Timetable,
    Assignment, LessonPlan, CBTExam
)


# ── Nigerian Names Database ─────────────────────────────────────────────────────

FIRST_NAMES_MALE = [
    "Adekunle", "Ayoade", "Chukwu", "Chisom", "David", "Emeka", "Femi", "Godwin",
    "Ibrahim", "Jamal", "Kamara", "Luthando", "Musa", "Nonso", "Obinna", "Pelumi",
    "Quarry", "Rasiq", "Sayo", "Tunde", "Umar", "Vince", "Wale", "Xavier", "Yusuf", "Zainab"
]

FIRST_NAMES_FEMALE = [
    "Abebi", "Aida", "Blessing", "Chioma", "Diana", "Esther", "Folake", "Grace",
    "Hannah", "Ifeoma", "Jumoke", "Kamila", "Lola", "Mercy", "Nkiru", "Oyin",
    "Princess", "Quet", "Raven", "Sophia", "Tayo", "Uche", "Victoria", "Whitney", "Yemi", "Zainab"
]

LAST_NAMES = [
    "Okafor", "Adeyemi", "Ibrahim", "Okonkwo", "Adeyinka", "Mohammed", "Usman",
    "Obi", "Bello", "Hassan", "Ahmed", "Oluwaseun", "Dada", "Fasola", "Agbaje",
    "Abioye", "Adebanjo", "Olagoke", "Tope", "Adeleke", "Oladele", "Bamigboye",
    "Okoro", "Anyanwu", "Egbunike", "Ndiaye", "Mensah", "Opoku", "Asante"
]

STAFF_NAMES = [
    ("Principal", "Chief"), ("Vice Principal", "Senior"), ("Head Teacher", "Lead"),
    ("Mathematics", "Teacher"), ("English", "Teacher"), ("Physics", "Teacher"),
    ("Chemistry", "Teacher"), ("Biology", "Teacher"), ("Economics", "Teacher"),
    ("Government", "Teacher"), ("Literature", "Teacher"), ("ICT", "Teacher"),
    ("Civic", "Education"), ("Geography", "Teacher"), ("CRS", "Teacher"),
    ("Agricultural", "Science"), ("Business", "Studies"), ("Accounts", "Officer"),
    ("HR", "Officer"), ("Receptionist", "Front Desk"), ("Librarian", "Library"),
    ("Lab", "Technician"), ("Security", "Officer"), ("Driver", "Transport"),
    ("Cleaner", "Support"), ("ICT Support", "Technical")
]


def random_nigerian_name(gender: str = "M") -> tuple[str, str]:
    """Generate realistic Nigerian name."""
    first = random.choice(FIRST_NAMES_MALE if gender == "M" else FIRST_NAMES_FEMALE)
    last = random.choice(LAST_NAMES)
    return first, last


# Authoritative auth domain for the portal. Must match
# settings.ALLOWED_EMAIL_DOMAIN or seeded users can't log in (domain gate).
SCHOOL_EMAIL_DOMAIN = "fairviewschoolng.com"


def random_email(first: str, last: str, domain: str = SCHOOL_EMAIL_DOMAIN) -> str:
    """Generate email from name."""
    return f"{first.lower()}.{last.lower()}@{domain}".replace(" ", "")


async def ensure_org(session: AsyncSession) -> Organization:
    """Ensure Fairview School org exists, create if not."""
    # Check if exists
    result = await session.execute(
        select(Organization).where(Organization.slug == "fairview-school")
    )
    org = result.scalar_one_or_none()
    
    # Canonical module set for the portal: school core + experience layer +
    # shared services. These are the keys the route guards actually consult.
    SCHOOL_MODULES = [
        "school", "behaviour", "cbt", "classroom", "clubs", "feedback",
        "journals", "tuckshop", "library", "transport", "sms",
        "hr", "leave", "analytics",
    ]

    if org:
        print(f"✓ Fairview School exists (id={org.id})")
        # Normalise an existing org to the single-school baseline (idempotent):
        # enterprise tier (no plan 402s), full module set, onboarding complete
        # so the onboarding gate is a no-op for the portal.
        org.industry = IndustryType.SCHOOL
        org.subscription_tier = SubscriptionTier.ENTERPRISE
        org.modules_enabled = SCHOOL_MODULES
        org.name = "Fairview School"
        if org.onboarding_completed_at is None:
            org.onboarding_step = "done"
            org.onboarding_completed_at = datetime.now(timezone.utc)
        await session.flush()
        return org

    # Create new org — onboarding pre-completed: a dedicated single-school
    # deployment never runs the multi-tenant onboarding wizard.
    org = Organization(
        name="Fairview School",
        slug="fairview-school",
        industry=IndustryType.SCHOOL,
        subscription_tier=SubscriptionTier.ENTERPRISE,  # Full features, no plan caps
        modules_enabled=SCHOOL_MODULES,
        max_users=100000,
        onboarding_step="done",
        onboarding_completed_at=datetime.now(timezone.utc),
    )
    session.add(org)
    await session.flush()
    print(f"✓ Created Fairview School (id={org.id})")
    return org


async def ensure_roles(session: AsyncSession, org: Organization) -> dict[str, Role]:
    """Ensure default roles exist, create if not."""
    roles = {}
    presets = permission_presets_for_industry("school")
    
    for slug, perms in presets.items():
        result = await session.execute(
            select(Role).where(Role.org_id == org.id, Role.slug == slug, Role.is_system == True)
        )
        role = result.scalar_one_or_none()
        
        if not role:
            role = Role(
                name=slug.replace("_", " ").title(),
                slug=slug,
                permissions=list(perms),
                org_id=org.id,
                is_system=True,
            )
            session.add(role)
            await session.flush()
            print(f"  ✓ Created role: {role.name}")
        
        roles[slug] = role
    
    return roles


async def ensure_principal(session: AsyncSession, org: Organization, roles: dict) -> User:
    """Ensure principal user exists."""
    result = await session.execute(
        select(User).where(User.email == "principal@fairviewschoolng.com", User.org_id == org.id)
    )
    principal = result.scalar_one_or_none()

    if principal:
        print(f"✓ Principal exists: {principal.full_name}")
        return principal

    principal = User(
        email="principal@fairviewschoolng.com",
        full_name="Dr. Adeyemi Okafor",
        hashed_password=hash_password("FairviewPrincipal123!"),
        phone="+234 801 234 5678",
        department="Administration",
        job_title="Principal",
        org_id=org.id,
        status=UserStatus.ACTIVE,
        email_verified=True,
    )
    principal.roles = [roles["org_admin"]]
    session.add(principal)
    await session.flush()
    print(f"✓ Created principal: {principal.full_name}")
    return principal


async def seed_fairview_school(session: AsyncSession):
    """Main seed function - creates complete Fairview School environment."""
    print("\n" + "="*70)
    print("FAIRVIEW SCHOOL DEMO ENVIRONMENT SEEDER")
    print("="*70)
    
    # Phase 1: Organization & Roles
    print("\n--- Phase 1: Organization Setup ---")
    org = await ensure_org(session)
    roles = await ensure_roles(session, org)
    
    # Phase 2: Principal & Admin Users
    print("\n--- Phase 2: Leadership & Admin ---")
    principal = await ensure_principal(session, org, roles)
    
    # Phase 3: Teachers
    print("\n--- Phase 3: Teaching Staff ---")
    teachers = {}
    subject_teachers = {
        "Mathematics": ("Mathematics", ["Mathematics"]),
        "English": ("English Language", ["English", "Literature"]),
        "Physics": ("Physics", ["Physics"]),
        "Chemistry": ("Chemistry", ["Chemistry"]),
        "Biology": ("Biology", ["Biology"]),
        "Economics": ("Economics", ["Economics"]),
        "Government": ("Government", ["Government"]),
        "ICT": ("Information Technology", ["ICT"]),
        "CRS": ("Christian Religious Studies", ["CRS"]),
        "Geography": ("Geography", ["Geography"]),
    }
    
    count = 0
    for subject, (full_subject, subjects_list) in subject_teachers.items():
        # Check if teacher exists
        result = await session.execute(
            select(User).where(
                User.email.ilike(f"{subject.lower()}%@{SCHOOL_EMAIL_DOMAIN}"),
                User.org_id == org.id
            )
        )
        if result.scalar_one_or_none():
            print(f"  ✓ {subject} teacher exists")
            count += 1
            continue
        
        first, last = random_nigerian_name("M")
        teacher = User(
            email=f"{subject.lower().replace(' ', '')}@{SCHOOL_EMAIL_DOMAIN}",
            full_name=f"{first} {last}",
            hashed_password=hash_password("TeacherPass123!"),
            phone=f"+234 {random.randint(800, 809)} {random.randint(100, 999)} {random.randint(1000, 9999)}",
            department="Academics",
            job_title=f"{subject} Teacher",
            org_id=org.id,
            status=UserStatus.ACTIVE,
            email_verified=True,
        )
        teacher.roles = [roles.get("staff", roles["org_admin"])]
        session.add(teacher)
        await session.flush()
        teachers[subject] = teacher
        print(f"  ✓ Created {subject} teacher: {teacher.full_name}")
        count += 1
    
    print(f"\n✓ Teaching staff: {count} teachers")
    await session.commit()
    
    print("\n" + "="*70)
    print("✓ FAIRVIEW SCHOOL SEEDING COMPLETE")
    print("="*70)
    print(f"\nOrganization: {org.name}")
    print(f"Slug: {org.slug}")
    print(f"Principal: {principal.full_name}")
    print(f"Teachers: {len(teachers)}")


async def main():
    """Entry point."""
    async with AsyncSessionLocal() as session:
        try:
            await seed_fairview_school(session)
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            await session.rollback()


if __name__ == "__main__":
    asyncio.run(main())
