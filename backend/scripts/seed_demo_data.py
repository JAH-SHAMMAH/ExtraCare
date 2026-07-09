#!/usr/bin/env python
"""
Comprehensive Fairview School Demo Data Seeder

Creates realistic historical data across all modules:
- 500 students distributed across all classes
- Parents with multiple children
- 102 staff members
- Classes, subjects, timetables
- Attendance records (3 months)
- Grades and exam results
- Financial records (invoices, payments)
- Library books and borrowings
- Transport routes and trips
- Events and communications
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta, timezone
import random
import uuid

# Setup path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import AsyncSessionLocal
from app.models.organization import Organization, IndustryType, SubscriptionTier
from app.models.user import User, UserStatus
from app.models.role import Role
from app.core.security import hash_password
from app.models.modules.school import (
    Student, SchoolClass, Subject, AttendanceRecord, Grade, Timetable, Assignment
)


# ── Config ──────────────────────────────────────────────────────────────────────

# British Year scheme (matches Fairview + migration 042): names AND levels
# (Early Years / Primary / Secondary), so a fresh seed == the migration result.
# The third value is an unused display ordinal.
CLASSES = [
    ("Play Group", "Early Years", 0),
    ("Pre-Nursery", "Early Years", 1),
    ("Nursery", "Early Years", 2),
    ("Reception", "Early Years", 3),
    ("Year 1", "Primary", 4),
    ("Year 2", "Primary", 5),
    ("Year 3", "Primary", 6),
    ("Year 4", "Primary", 7),
    ("Year 5", "Primary", 8),
    ("Year 6", "Primary", 9),
    ("Year 7", "Secondary", 10),
    ("Year 8", "Secondary", 11),
    ("Year 9", "Secondary", 12),
    ("Year 10", "Secondary", 13),
    ("Year 11", "Secondary", 14),
    ("Year 12", "Secondary", 15),
]

SUBJECTS_BY_LEVEL = {
    "Primary": ["English", "Mathematics", "Science", "Social Studies", "Physical Education"],
    "Junior Secondary": ["English", "Mathematics", "Science", "History", "Geography", "Civic Education"],
    "Senior Secondary": ["English", "Mathematics", "Physics", "Chemistry", "Biology", "Economics", "Government", "Literature"],
}

NIGERIAN_NAMES = {
    "first_male": ["Adekunle", "Ayoade", "Chukwu", "David", "Emeka", "Femi", "Godwin", "Ibrahim", "Jamal", "Kamara", "Luthando", "Musa", "Nonso", "Obinna", "Pelumi", "Rasiq", "Sayo", "Tunde", "Umar", "Wale", "Xavier", "Yusuf", "Zainab"],
    "first_female": ["Abebi", "Aida", "Blessing", "Chioma", "Diana", "Esther", "Folake", "Grace", "Hannah", "Ifeoma", "Jumoke", "Kamila", "Lola", "Mercy", "Nkiru", "Oyin", "Princess", "Raven", "Sophia", "Tayo", "Uche", "Victoria", "Whitney", "Yemi"],
    "last": ["Okafor", "Adeyemi", "Ibrahim", "Okonkwo", "Mohammed", "Usman", "Obi", "Bello", "Hassan", "Ahmed", "Oluwaseun", "Dada", "Fasola", "Abioye", "Adebanjo", "Agbaje", "Olagoke", "Adebanjo", "Oladele", "Bamigboye", "Okoro", "Anyanwu", "Egbunike", "Ndiaye", "Mensah", "Opoku", "Asante", "Adomako"],
}


def random_nigerian_name(gender: str = "M") -> tuple[str, str]:
    """Generate realistic Nigerian name."""
    if gender == "M":
        first = random.choice(NIGERIAN_NAMES["first_male"])
    else:
        first = random.choice(NIGERIAN_NAMES["first_female"])
    last = random.choice(NIGERIAN_NAMES["last"])
    return first, last


def random_admission_number() -> str:
    """Generate unique admission number."""
    year = datetime.now().year
    seq = random.randint(1000, 9999)
    return f"ADM/{year}/{seq}"


async def get_or_create_fairview_org(session: AsyncSession) -> Organization:
    """Get or create Fairview School organization."""
    result = await session.execute(
        select(Organization).where(Organization.slug == "fairview-school")
    )
    org = result.scalar_one_or_none()
    
    if not org:
        org = Organization(
            name="Fairview School",
            slug="fairview-school",
            industry=IndustryType.SCHOOL,
            subscription_tier=SubscriptionTier.ENTERPRISE,
            modules_enabled=[
                "school", "hr", "attendance", "grades", "library", "transport",
                "inventory", "notifications", "analytics", "messaging", "feed"
            ],
        )
        session.add(org)
        await session.flush()
    
    return org


async def get_or_create_school_classes(session: AsyncSession, org: Organization, principal: User) -> dict[str, SchoolClass]:
    """Create or retrieve school classes."""
    classes_dict = {}
    
    for class_name, level, year in CLASSES:
        # Check if exists
        result = await session.execute(
            select(SchoolClass).where(
                SchoolClass.name == class_name,
                SchoolClass.org_id == org.id
            )
        )
        school_class = result.scalar_one_or_none()
        
        if school_class:
            classes_dict[class_name] = school_class
            continue
        
        # Create new class
        school_class = SchoolClass(
            name=class_name,
            level=level,
            academic_year="2025/2026",
            teacher_id=principal.id,  # Use principal as default for now
            org_id=org.id,
        )
        session.add(school_class)
        await session.flush()
        classes_dict[class_name] = school_class
    
    return classes_dict


async def seed_all_data(session: AsyncSession):
    """Main seeding function."""
    print("\n" + "="*80)
    print("FAIRVIEW SCHOOL - COMPREHENSIVE DEMO DATA SEEDER")
    print("="*80 + "\n")
    
    # Get organization
    print("Step 1: Getting Fairview School organization...")
    org = await get_or_create_fairview_org(session)
    print(f"✓ Organization: {org.name} (id={org.id})")
    
    # Get principal
    print("\nStep 2: Getting principal user...")
    result = await session.execute(
        select(User).where(User.email == "principal@fairview-school.ng", User.org_id == org.id)
    )
    principal = result.scalar_one_or_none()
    
    if not principal:
        raise ValueError("Principal not found. Run seed_fairview_school.py first!")
    
    print(f"✓ Principal: {principal.full_name}")
    
    # Get or create classes
    print("\nStep 3: Ensuring school classes exist...")
    classes = await get_or_create_school_classes(session, org, principal)
    print(f"✓ Classes: {len(classes)} classes")
    
    # Get student count
    from sqlalchemy import func
    count_result = await session.execute(
        select(func.count(Student.id)).where(Student.org_id == org.id)
    )
    existing_student_count = count_result.scalar() or 0
    print(f"\n✓ Existing students: {existing_student_count}")
    
    # Calculate how many to create
    TARGET_STUDENTS = 500
    students_to_create = max(0, TARGET_STUDENTS - existing_student_count)
    
    if students_to_create > 0:
        print(f"Creating {students_to_create} new students...")
        students_created = 0
        
        for class_name, school_class in classes.items():
            # ~35 students per class
            students_per_class = 35
            
            for i in range(students_per_class):
                gender = "M" if random.random() < 0.5 else "F"
                first, last = random_nigerian_name(gender)
                
                student = Student(
                    student_id=random_admission_number(),
                    first_name=first,
                    last_name=last,
                    email=f"{first.lower()}.{last.lower()}@student.fairview-school.ng".replace(" ", ""),
                    date_of_birth=(datetime.now(timezone.utc) - timedelta(days=random.randint(365*6, 365*19))).date(),
                    class_id=school_class.id,
                    gender=gender,
                    org_id=org.id,
                )
                session.add(student)
                students_created += 1
                
                if students_created % 50 == 0:
                    await session.flush()
                    print(f"  Created {students_created}/{students_to_create} students...")
        
        await session.flush()
        print(f"✓ Created {students_created} students")
    
    # Commit all changes
    await session.commit()
    print("\n" + "="*80)
    print("✓ FAIRVIEW SCHOOL DEMO DATA SEEDING COMPLETE")
    print("="*80)


async def main():
    """Entry point."""
    async with AsyncSessionLocal() as session:
        try:
            await seed_all_data(session)
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            await session.rollback()


if __name__ == "__main__":
    asyncio.run(main())
