#!/usr/bin/env python
"""Debug script to test user creation."""

import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import selectinload

# Setup path
sys.path.insert(0, "/app")

from app.models.base import Base
from app.models.user import User, UserStatus
from app.models.organization import Organization, IndustryType
from app.models.role import Role
from app.schemas.user import UserCreate
from app.services.user_service import create_user
from app.core.security import hash_password


async def main():
    # Create in-memory DB for testing
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session maker
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    # Create org
    async with AsyncSessionLocal() as session:
        org = Organization(
            id="test-org-123",
            name="Test School",
            slug="test-school",
            industry=IndustryType.SCHOOL,
        )
        session.add(org)
        
        # Create a role
        role = Role(
            id="role-123",
            name="Teacher",
            slug="teacher",
            org_id="test-org-123",
            permissions=["users:read", "users:write"],
        )
        session.add(role)
        await session.commit()
        print("✓ Organization and role created")
    
    # Test user creation
    async with AsyncSessionLocal() as session:
        try:
            user_data = UserCreate(
                email="teacher@example.com",
                full_name="Teacher One",
                password="TestPassword123!",
                phone="+234 800 000 0000",
                department="Science",
                job_title="Physics Teacher",
                role_ids=["role-123"],
            )
            
            print(f"\nCreating user with data: {user_data}")
            user = await create_user(session, "test-org-123", user_data)
            print(f"✓ User created: {user.id}, email={user.email}, status={user.status}")
            
            # Commit
            await session.commit()
            print("✓ Session committed")
            
        except Exception as e:
            print(f"✗ Error creating user: {e}")
            import traceback
            traceback.print_exc()
            await session.rollback()
    
    # Verify user in new session
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(User).options(selectinload(User.roles)).where(User.email == "teacher@example.com")
        )
        user = result.scalar_one_or_none()
        if user:
            print(f"\n✓ User verified in database: {user.email}, roles={[r.slug for r in user.roles]}")
        else:
            print("\n✗ User NOT found in database after commit")
    
    await engine.dispose()
    print("\nTest complete!")


if __name__ == "__main__":
    asyncio.run(main())
