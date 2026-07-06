"""
Role-Based Access Control (RBAC)
==================================
Fine-grained permission checks as FastAPI dependencies.

Usage in routes:
    @router.get("/users", dependencies=[Depends(require_permission("users:read"))])
    @router.delete("/users/{id}", dependencies=[Depends(require_permission("users:delete"))])
"""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.organization import Organization
from app.models.user import User
from app.core.workspace import permission_scope_allowed_for_org


class PermissionChecker:
    def __init__(self, permission: str):
        self.permission = permission

    async def __call__(
        self,
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        if not current_user.is_superadmin:
            org: Organization | None = getattr(request.state, "org", None)
            if org is None:
                org = (await db.execute(
                    select(Organization).where(Organization.id == current_user.org_id)
                )).scalar_one_or_none()
                if org is not None:
                    request.state.org = org
                    request.state.org_id = org.id

            if org is not None and not permission_scope_allowed_for_org(org, self.permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied for this workspace scope. Required: '{self.permission}'",
                )

        if not current_user.has_permission(self.permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required: '{self.permission}'",
            )
        return current_user


class AnyPermissionChecker:
    """Passes if the user holds ANY one of the listed permissions (and that
    permission is allowed for the org's workspace scope).

    Use for an action that more than one role legitimately performs — e.g. a
    store **cashier** (`store:sell`) OR a **finance clerk** (`payments:write`)
    marking a store pickup collected. It is deliberately additive: it widens who
    may act, never narrows it, so it can't lock an existing role out.
    """

    def __init__(self, *permissions: str):
        if not permissions:
            raise ValueError("AnyPermissionChecker needs at least one permission")
        self.permissions = permissions

    async def __call__(
        self,
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        org: Organization | None = None
        if not current_user.is_superadmin:
            org = getattr(request.state, "org", None)
            if org is None:
                org = (await db.execute(
                    select(Organization).where(Organization.id == current_user.org_id)
                )).scalar_one_or_none()
                if org is not None:
                    request.state.org = org
                    request.state.org_id = org.id

        for permission in self.permissions:
            # Skip a permission the workspace scope forbids, then check the grant.
            if org is not None and not permission_scope_allowed_for_org(org, permission):
                continue
            if current_user.has_permission(permission):
                return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied. Required one of: {', '.join(self.permissions)}",
        )


def require_permission(permission: str):
    """Dependency factory for permission checks."""
    return Depends(PermissionChecker(permission))


def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin access required.",
        )
    return current_user


def require_active_user(current_user: User = Depends(get_current_user)) -> User:
    from app.models.user import UserStatus
    if current_user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {current_user.status.value}. Contact your administrator.",
        )
    return current_user
