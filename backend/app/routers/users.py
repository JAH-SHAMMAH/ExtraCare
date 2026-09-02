from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from sqlalchemy.orm import selectinload
import secrets

from app.database import get_db
from app.deps import get_current_user, get_current_active_user
from app.core.permissions import PermissionChecker, assert_can_grant_roles, assert_can_manage_user
from app.core.security import hash_password
from app.models.user import User, UserStatus
from app.models.role import Role, user_roles
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
    async def _fetch():
        # NB: Role has no soft-delete column (custom-role CRUD is deferred), so we
        # must NOT filter on Role.is_deleted here — doing so 500s the endpoint.
        return (await db.execute(
            select(Role).where(Role.org_id == current_user.org_id).order_by(Role.name)
        )).scalars().all()

    roles = await _fetch()
    # Self-heal: seed any newly-added system-role presets for this org (idempotent).
    # Runs only while presets are missing, so it's a one-time cost after a release
    # that adds roles — admins then see the full catalogue with no manual sync step.
    from app.models.role import permission_presets_for_industry
    from app.models.organization import Organization
    org = (await db.execute(select(Organization).where(Organization.id == current_user.org_id))).scalar_one_or_none()
    if org is not None:
        expected = len(permission_presets_for_industry(org.industry.value if org.industry else None))
        if sum(1 for r in roles if r.is_system) < expected:
            from app.routers.organizations import _sync_system_roles_for_org
            await _sync_system_roles_for_org(db, org)
            await db.commit()
            roles = await _fetch()
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


@router.get("/by-role/{role_slug}", dependencies=[_can_read])
async def list_users_by_role(
    role_slug: str,
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Minimal {id, full_name, avatar_url} list of users holding a role — powers
    the News Feed 'Select Users' (Publish-To → more) modal. Org-scoped, gated
    users:read (the same scope the role list + contact picker use)."""
    q = (
        select(User.id, User.full_name, User.avatar_url)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(User.org_id == current_user.org_id, User.is_deleted == False, Role.slug == role_slug)  # noqa: E712
    )
    if search:
        term = f"%{search.strip()}%"
        q = q.where((User.full_name.ilike(term)) | (User.email.ilike(term)))
    rows = (await db.execute(q.order_by(User.full_name).limit(100))).all()
    return {"items": [{"id": r.id, "full_name": r.full_name, "avatar_url": r.avatar_url} for r in rows]}


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
        .where(User.org_id == current_user.org_id, User.is_deleted == False,  # noqa: E712
               User.is_seed_account == False)  # seed/demo logins aren't real staff  # noqa: E712
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
    # Guard: can't create an account seeded with roles beyond your own permissions.
    if data.role_ids:
        grant = (await db.execute(select(Role).where(Role.id.in_(data.role_ids), Role.org_id == current_user.org_id))).scalars().all()
        assert_can_grant_roles(current_user, grant)
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
    # Guard: can't invite an account seeded with roles beyond your own permissions.
    if data.role_ids:
        grant = (await db.execute(select(Role).where(Role.id.in_(data.role_ids), Role.org_id == current_user.org_id))).scalars().all()
        assert_can_grant_roles(current_user, grant)
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
    # Same bar as reset-password and role assignment: suspending an account is a
    # denial of service against it, so a lower tier must not be able to switch off
    # the Super User (or any account carrying scopes it doesn't hold).
    assert_can_manage_user(current_user, user)

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
    # Privilege-escalation guards: can't touch a more-privileged account, and can't
    # grant roles carrying permissions you don't hold (e.g. an Admin assigning
    # Super User / Accountant / Head of Administration → finance_admin).
    assert_can_manage_user(current_user, user)
    assert_can_grant_roles(current_user, roles)
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
    hand it over out-of-band. Audited.

    Privilege-guarded like role assignment. Handing back a working credential for
    another account is a full takeover of it, so it needs the same bar as changing
    that account's roles — without it, any `users:write` holder could reset the
    Super User's password and log in as them. Roles are eager-loaded because the
    guard reads them.
    """
    user = (await db.execute(
        select(User).options(selectinload(User.roles)).where(
            User.id == user_id, User.org_id == current_user.org_id, User.is_deleted == False
        )
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Use change-password for your own account.")
    assert_can_manage_user(current_user, user)
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
