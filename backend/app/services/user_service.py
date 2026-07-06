import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from app.models.user import User, UserStatus
from app.models.role import Role
from app.models.organization import Organization
from app.core.security import hash_password, generate_secure_token
from app.core.plans import plan_for, users_within_cap, plan_limit_detail
from app.core.tenant import bump_denial as _bump_denial_counter
from app.services.usage import track as track_usage
from app.schemas.user import UserCreate, UserUpdate, UserListResponse, UserResponse, InviteUserRequest


async def _assert_user_cap(db: AsyncSession, org_id: str) -> None:
    """Raises 402 if adding one more user would exceed the plan's cap.
    We read org + count inside the same session so concurrent invites don't
    slip past the cap — last writer still races, but this is a soft limit,
    not a security boundary."""
    from fastapi import HTTPException, status

    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not org:
        return  # org-missing is handled elsewhere; don't mask that error here

    plan = plan_for(org.subscription_tier)
    count = (await db.execute(
        select(func.count(User.id)).where(User.org_id == org_id, User.is_deleted == False)
    )).scalar_one() or 0
    if not users_within_cap(plan, count):
        _bump_denial_counter("plan_user_denied", org_id, plan.tier.value)
        # Org-wide nudge — any admin with the inbox open should see that
        # they're at the user cap. Uses its own session (the caller is
        # about to raise 402, which would rollback the request tx).
        from app.services import notifications as _notif
        from app.models.notification import TYPE_PLAN_LIMIT
        await _notif.notify_fire_and_forget(
            org_id=org_id,
            user_id=None,
            type=TYPE_PLAN_LIMIT,
            title="User limit reached",
            message=f"Your plan allows {plan.max_users} users. Upgrade to add more.",
            payload={
                "reason": "user_limit_exceeded",
                "current_plan": plan.tier.value,
                "max_users": plan.max_users,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=plan_limit_detail(
                reason="user_limit_exceeded",
                current_plan=plan.tier,
            ),
        )


async def create_user(db: AsyncSession, org_id: str, data: UserCreate) -> User:
    # Check duplicate email within org
    existing = await db.execute(
        select(User).where(User.email == data.email, User.org_id == org_id, User.is_deleted == False)
    )
    if existing.scalar_one_or_none():
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="A user with this email already exists.")

    await _assert_user_cap(db, org_id)

    user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password) if data.password else None,
        phone=data.phone,
        department=data.department,
        job_title=data.job_title,
        org_id=org_id,
        status=UserStatus.ACTIVE if data.password else UserStatus.PENDING,
        email_verified=bool(data.password),
    )
    
    # Load and assign roles BEFORE adding to session to avoid async greenlet issues
    # When assigning to a relationship on a persistent object, SQLAlchemy tries to
    # lazy-load the current value, which fails in async context
    loaded_roles = []
    if data.role_ids:
        result = await db.execute(
            select(Role).where(Role.id.in_(data.role_ids), Role.org_id == org_id)
        )
        loaded_roles = list(result.scalars().all())
    
    # Always assign roles (even if empty list) to avoid lazy-loading on access
    user.roles = loaded_roles
    
    db.add(user)
    await db.flush()  # get user.id without committing

    user._loaded_roles = loaded_roles  # stash for the caller to use without lazy load
    track_usage(org_id, "platform", "user_created")
    return user


async def invite_user(db: AsyncSession, org_id: str, data: InviteUserRequest, invited_by: User) -> User:
    token = generate_secure_token()
    expires = datetime.now(timezone.utc) + timedelta(days=7)

    user = await create_user(db, org_id, UserCreate(
        email=data.email,
        full_name=data.full_name,
        role_ids=data.role_ids,
        department=data.department,
        job_title=data.job_title,
    ))
    user.invite_token = token
    user.invite_expires = expires
    user.invited_by = invited_by.id
    await db.flush()

    # Reload all columns and the roles relationship so callers can safely access all attributes
    from sqlalchemy.orm import selectinload
    await db.refresh(user, attribute_names=["invite_token", "invite_expires", "invited_by"])
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user.id)
    )
    user = result.scalar_one()
    user._loaded_roles = list(user.roles)
    # TODO: send invitation email via notification_service
    return user


async def get_users_paginated(
    db: AsyncSession,
    org_id: str,
    page: int = 1,
    page_size: int = 25,
    search: str | None = None,
    status: UserStatus | None = None,
    role_slug: str | None = None,
    minimal: bool = False,
) -> UserListResponse:
    query = select(User).options(selectinload(User.roles)).where(User.org_id == org_id, User.is_deleted == False)

    if search:
        term = f"%{search}%"
        query = query.where(
            or_(User.full_name.ilike(term), User.email.ilike(term), User.department.ilike(term))
        )

    if status:
        query = query.where(User.status == status)

    # Count total before pagination
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    # Apply pagination
    offset = (page - 1) * page_size
    result = await db.execute(query.order_by(User.created_at.desc()).offset(offset).limit(page_size))
    users = result.scalars().all()

    import math
    project = UserResponse.minimal_from if minimal else (
        lambda u: UserResponse.from_orm_with_roles(u, loaded_roles=list(u.roles))
    )
    return UserListResponse(
        items=[project(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size),
    )
