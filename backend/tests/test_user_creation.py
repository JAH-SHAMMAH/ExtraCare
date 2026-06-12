"""
Test user creation fix.
"""
import pytest
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role
from app.schemas.user import UserCreate
from app.services.user_service import create_user


@pytest.mark.asyncio
async def test_create_user_with_roles(db, org):
    """Test that users can be created with roles assigned."""
    # Create test roles
    teacher_role = Role(
        name="Teacher",
        slug="teacher",
        permissions=["users:read"],
        org_id=org.id,
        is_system=True,
    )
    admin_role = Role(
        name="Admin",
        slug="admin",
        permissions=["users:write"],
        org_id=org.id,
        is_system=True,
    )
    db.add(teacher_role)
    db.add(admin_role)
    await db.commit()
    
    # Create user with roles
    user_data = UserCreate(
        email="teacher1@example.com",
        full_name="Teacher One",
        password="TestPassword123",
        role_ids=[teacher_role.id, admin_role.id],
    )
    
    user = await create_user(db, org.id, user_data)
    assert user.id is not None
    assert user.email == "teacher1@example.com"
    assert user.status == UserStatus.ACTIVE
    assert len(user.roles) == 2
    assert {r.slug for r in user.roles} == {"teacher", "admin"}
    
    # Commit and verify in new session
    await db.commit()
    
    # New session verification
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.email == "teacher1@example.com")
    )
    verified_user = result.scalar_one()
    assert verified_user.email == "teacher1@example.com"
    assert len(verified_user.roles) == 2
    assert {r.slug for r in verified_user.roles} == {"teacher", "admin"}


@pytest.mark.asyncio
async def test_create_user_without_roles(db, org):
    """Test that users can be created without roles."""
    user_data = UserCreate(
        email="admin@example.com",
        full_name="Admin User",
        password="AdminPassword123",
        role_ids=[],
    )
    
    user = await create_user(db, org.id, user_data)
    assert user.id is not None
    assert user.email == "admin@example.com"
    assert user.status == UserStatus.ACTIVE
    assert len(user.roles) == 0


@pytest.mark.asyncio
async def test_create_user_without_password(db, org):
    """Test that invited users can be created without password."""
    teacher_role = Role(
        name="Teacher",
        slug="teacher",
        permissions=["users:read"],
        org_id=org.id,
        is_system=True,
    )
    db.add(teacher_role)
    await db.commit()
    
    user_data = UserCreate(
        email="invited@example.com",
        full_name="Invited User",
        password=None,
        role_ids=[teacher_role.id],
    )
    
    user = await create_user(db, org.id, user_data)
    assert user.id is not None
    assert user.email == "invited@example.com"
    assert user.status == UserStatus.PENDING
    assert user.hashed_password is None
    assert not user.email_verified
    assert len(user.roles) == 1
    assert user.roles[0].slug == "teacher"
