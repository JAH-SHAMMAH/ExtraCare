from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from sqlalchemy.orm import selectinload
import secrets

from app.database import get_db
from app.deps import get_current_user, get_current_active_user
from app.core.permissions import PermissionChecker
from app.core.security import hash_password
from app.models.user import User, UserStatus
from app.models.role import Role
from app.schemas.user import (
    UserCreate, UserUpdate, UserStatusUpdate, UserResponse,
    UserListResponse, InviteUserRequest,
)
from app.services.user_service import create_user, invite_user, get_users_paginated
from app.services.audit_service import log_action
from app.models.audit import AuditAction

router = APIRouter(prefix="/users", tags=["Users"])

_can_read = Depends(PermissionChecker("users:read"))
_can_write = Depends(PermissionChecker("users:write"))
_can_delete = Depends(PermissionChecker("users:delete"))


@router.get("", response_model=UserListResponse, dependencies=[_can_read])
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None),
    status: UserStatus | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Non-admin callers (users:read for the Messenger contact picker, but no
    # users:write) get a minimal directory projection — name/email/avatar only,
    # no HR or security fields. Admins managing users see the full record.
    minimal = not current_user.has_permission("users:write")
    return await get_users_paginated(
        db=db,
        org_id=current_user.org_id,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        minimal=minimal,
    )


@router.get("/roles/available", dependencies=[_can_read])
async def list_available_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all available roles for the current organization."""
    result = await db.execute(
        select(Role).where(
            Role.org_id == current_user.org_id,
            Role.is_deleted == False
        ).order_by(Role.name)
    )
    roles = result.scalars().all()
    return {
        "items": [
            {
                "id": role.id,
                "name": role.name,
                "slug": role.slug,
                "color": role.color,
                "description": role.description,
                "is_system": role.is_system,
                # ENHANCED (Phase 4 Access Control): expose each role's permission
                # set so the access-control UI can show what a role can do.
                "permissions": role.permissions or [],
            }
            for role in roles
        ]
    }


# ┌─ FUTURE: custom-role CRUD (Access Control) ─────────────────────────────────────┐
# │ The Access Control UI is ASSIGN-ONLY today: it lists roles (+ permissions) and  │
# │ assigns existing roles to users (PATCH /{user_id}/roles below). To let admins    │
# │ CREATE / EDIT / DELETE custom roles, add the endpoints here, gated `roles:write`: │
# │   POST   /users/roles            — create a custom role (name, permissions[])     │
# │   PATCH  /users/roles/{role_id}  — rename / change permissions (block is_system)  │
# │   DELETE /users/roles/{role_id}  — soft-delete a custom role (block is_system)    │
# │ The Role model already supports custom roles + granular permissions; only these   │
# │ routes + matching frontend (role editor) are missing. Intentionally deferred.     │
# └───────────────────────────────────────────────────────────────────────────────────┘


@router.get("/staff", response_model=list[UserResponse], dependencies=[_can_read])
async def list_staff(
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """NEW: non-teaching staff + admin directory — ALL of them (no 100-row cap).
    Excludes teachers (``job_title == "Teacher"``, who have their own page) and
    students/parents (by role). Returned unpaginated; school staff counts are
    bounded. Filtering is server-side so directories over 100 accounts show fully."""
    q = (
        select(User)
        .options(selectinload(User.roles))
        .where(User.org_id == current_user.org_id, User.is_deleted == False)  # noqa: E712
    )
    if search:
        term = f"%{search.strip()}%"
        q = q.where((User.full_name.ilike(term)) | (User.email.ilike(term)))
    users = (await db.execute(q.order_by(User.full_name))).scalars().all()

    EXCLUDE = {"student", "parent"}
    staff = [
        u for u in users
        if (u.job_title or "").strip().lower() != "teacher"
        and not any((r.slug or "").lower() in EXCLUDE for r in (u.roles or []))
    ]
    return [UserResponse.from_orm_with_roles(u, u.roles) for u in staff]


@router.post("", response_model=UserResponse, status_code=201, dependencies=[_can_write])
async def create_new_user(
    data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    user = await create_user(db, current_user.org_id, data)
    await log_action(
        db, AuditAction.USER_CREATED, current_user.org_id, actor=current_user,
        resource_type="User", resource_id=user.id, resource_label=user.full_name,
        new_values={"email": user.email, "department": user.department},
        request=request,
    )
    # Re-fetch with selectin-loaded roles to avoid lazy-load in async context
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user.id)
    )
    user = result.scalar_one()
    return UserResponse.from_orm_with_roles(user, loaded_roles=list(user.roles))


@router.post("/invite", response_model=UserResponse, status_code=201, dependencies=[_can_write])
async def invite_new_user(
    data: InviteUserRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    user = await invite_user(db, current_user.org_id, data, invited_by=current_user)
    await log_action(
        db, AuditAction.USER_INVITED, current_user.org_id, actor=current_user,
        resource_type="User", resource_id=user.id, resource_label=user.full_name, request=request,
    )
    # Org-wide notification so any admin browsing the feed sees new joiners.
    from app.services import notifications as _notif
    from app.models.notification import TYPE_USER_INVITED
    await _notif.notify(
        org_id=current_user.org_id,
        user_id=None,
        type=TYPE_USER_INVITED,
        title="New user invited",
        message=f"{user.full_name} ({user.email}) was invited to join.",
        payload={"user_id": user.id, "email": user.email, "invited_by": current_user.id},
        session=db,
    )
    # Re-fetch with selectin-loaded roles to avoid lazy-load in async context
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user.id)
    )
    user = result.scalar_one()
    return UserResponse.from_orm_with_roles(user, loaded_roles=list(user.roles))


@router.get("/{user_id}", response_model=UserResponse, dependencies=[_can_read])
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id, User.org_id == current_user.org_id, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    # Same minimal projection as the list endpoint for non-admin callers.
    if not current_user.has_permission("users:write"):
        return UserResponse.minimal_from(user)
    return UserResponse.from_orm_with_roles(user, loaded_roles=list(user.roles))


@router.patch("/{user_id}", response_model=UserResponse, dependencies=[_can_write])
async def update_user(
    user_id: str,
    data: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id, User.org_id == current_user.org_id, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    old = {"full_name": user.full_name, "department": user.department}
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    await log_action(
        db, AuditAction.USER_UPDATED, current_user.org_id, actor=current_user,
        resource_type="User", resource_id=user.id, resource_label=user.full_name,
        old_values=old, new_values=data.model_dump(exclude_unset=True), request=request,
    )
    return UserResponse.from_orm_with_roles(user, loaded_roles=list(user.roles))


@router.patch("/{user_id}/status", response_model=UserResponse, dependencies=[_can_write])
async def update_user_status(
    user_id: str,
    data: UserStatusUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id, User.org_id == current_user.org_id, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own status.")

    old_status = user.status
    user.status = data.status

    action = AuditAction.USER_SUSPENDED if data.status == UserStatus.SUSPENDED else AuditAction.USER_UPDATED
    await log_action(
        db, action, current_user.org_id, actor=current_user,
        resource_type="User", resource_id=user.id, resource_label=user.full_name,
        old_values={"status": old_status.value}, new_values={"status": data.status.value},
        severity="warning" if data.status == UserStatus.SUSPENDED else "info",
        request=request,
    )
    return UserResponse.from_orm_with_roles(user, loaded_roles=list(user.roles))


@router.patch("/{user_id}/roles", response_model=UserResponse, dependencies=[_can_write])
async def assign_roles(
    user_id: str,
    role_ids: list[str],
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id, User.org_id == current_user.org_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    roles_result = await db.execute(
        select(Role).where(Role.id.in_(role_ids), Role.org_id == current_user.org_id)
    )
    roles = roles_result.scalars().all()
    old_roles = [r.slug for r in user.roles]
    user.roles = list(roles)

    await log_action(
        db, AuditAction.ROLE_CHANGED, current_user.org_id, actor=current_user,
        resource_type="User", resource_id=user.id, resource_label=user.full_name,
        old_values={"roles": old_roles}, new_values={"roles": [r.slug for r in roles]},
        severity="warning", request=request,
    )
    return UserResponse.from_orm_with_roles(user, loaded_roles=list(user.roles))


@router.post("/{user_id}/reset-password", dependencies=[_can_write])
async def reset_user_password(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Admin-initiated reset: set a one-time temp password the user MUST change
    before the account is usable again. Returns the temp password so the admin can
    hand it over out-of-band. Audited."""
    user = (await db.execute(
        select(User).where(User.id == user_id, User.org_id == current_user.org_id, User.is_deleted == False)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Use change-password for your own account.")
    temp = secrets.token_urlsafe(9)
    user.hashed_password = hash_password(temp)
    user.force_password_change = True
    user.password_reset_token = None
    user.password_reset_expires = None
    await db.flush()
    await log_action(
        db, AuditAction.PASSWORD_RESET, current_user.org_id, actor=current_user,
        resource_type="User", resource_id=user.id, resource_label=user.full_name,
        severity="warning", request=request,
    )
    return {"temporary_password": temp, "force_password_change": True}


@router.delete("/{user_id}", status_code=204, dependencies=[_can_delete])
async def delete_user(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id, User.org_id == current_user.org_id, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself.")

    from datetime import datetime, timezone
    user.is_deleted = True
    user.deleted_at = datetime.now(timezone.utc)

    await log_action(
        db, AuditAction.USER_DELETED, current_user.org_id, actor=current_user,
        resource_type="User", resource_id=user.id, resource_label=user.full_name,
        severity="warning", request=request,
    )
