"""
Simple test to understand the actual user creation issue without model FK issues.
"""
import asyncio
import sys
import os

# Set up async event loop for Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.chdir(r'c:\Users\SHAMMAH\OneDrive\Desktop\ExtraCare ERP\backend')
sys.path.insert(0, r'c:\Users\SHAMMAH\OneDrive\Desktop\ExtraCare ERP\backend')

async def main():
    from tests.conftest import engine as get_engine
    from app.schemas.user import UserCreate
    from app.services.user_service import create_user
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select
    from app.models.user import User
    
    print("Setting up test database...")
    # Use in-memory SQLite for simplicity
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.models.base import Base
    
    # Import all models so they're registered
    from app.models import user, organization, role, audit, import_job, hrm, leave, messenger, feed, live
    from app.models.modules import school, hospital, business
    
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Database tables created")
    
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    # Create test org and roles
    async with AsyncSessionLocal() as session:
        from app.models.organization import Organization, IndustryType
        from app.models.role import Role
        
        org = Organization(
            name="Test School",
            slug="test-school",
            industry=IndustryType.SCHOOL,
        )
        session.add(org)
        await session.flush()
        org_id = org.id
        
        # Create test roles
        teacher_role = Role(
            name="Teacher",
            slug="teacher",
            permissions=["users:read"],
            org_id=org_id,
            is_system=True,
        )
        admin_role = Role(
            name="Admin",
            slug="admin",
            permissions=["users:write"],
            org_id=org_id,
            is_system=True,
        )
        session.add(teacher_role)
        session.add(admin_role)
        await session.commit()
        print(f"✓ Organization and roles created (org_id={org_id})")
    
    # Test user creation
    async with AsyncSessionLocal() as session:
        print("\n--- Testing User Creation ---")
        
        user_data = UserCreate(
            email="teacher@example.com",
            full_name="Teacher One",
            password="TestPassword123",
            role_ids=[teacher_role.id, admin_role.id],
        )
        
        print(f"Creating user with role_ids: {user_data.role_ids}")
        
        try:
            # Step 1: Create user
            user = await create_user(session, org_id, user_data)
            print(f"✓ User created in service: id={user.id}, email={user.email}")
            print(f"  user.roles after create_user: {[r.slug for r in user.roles]}")
            print(f"  user._loaded_roles: {[r.slug for r in getattr(user, '_loaded_roles', [])]}")
            
            # Step 2: Check session state
            print(f"\n--- Session State Before Commit ---")
            from sqlalchemy import inspect
            insp = inspect(user)
            print(f"  User is pending: {insp.pending}")
            print(f"  User is persistent: {insp.persistent}")
            print(f"  User is transient: {insp.transient}")
            
            # Step 3: Flush (but don't commit yet)
            await session.flush()
            print(f"\n✓ Session flushed")
            print(f"  user.roles after flush: {[r.slug for r in user.roles]}")
            
            # Step 4: Refetch user (like the endpoint does)
            result = await session.execute(
                select(User).options(selectinload(User.roles)).where(User.id == user.id)
            )
            refetched_user = result.scalar_one()
            print(f"\n✓ User refetched from DB: {refetched_user.email}")
            print(f"  Refetched roles: {[r.slug for r in refetched_user.roles]}")
            
            # Step 5: Commit
            await session.commit()
            print(f"\n✓ Session committed")
            
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            await session.rollback()
    
    # Verify in new session
    async with AsyncSessionLocal() as session:
        print(f"\n--- Verification in New Session ---")
        result = await session.execute(
            select(User).options(selectinload(User.roles)).where(User.email == "teacher@example.com")
        )
        user = result.scalar_one_or_none()
        if user:
            print(f"✓ User found: {user.email}")
            print(f"  Roles: {[r.slug for r in user.roles]}")
        else:
            print(f"✗ User NOT found in database")
    
    await engine.dispose()
    print("\n✓ Test complete!")

if __name__ == "__main__":
    asyncio.run(main())
