from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from app.models.user import UserStatus


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: Optional[str] = None  # if None, invite flow sends set-password email
    phone: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    role_ids: list[str] = []


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    preferences: Optional[dict] = None


class UserStatusUpdate(BaseModel):
    status: UserStatus
    reason: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    phone: Optional[str]
    department: Optional[str]
    job_title: Optional[str]
    avatar_url: Optional[str]
    status: UserStatus
    email_verified: bool
    mfa_enabled: bool
    last_login_at: Optional[datetime]
    last_login_ip: Optional[str]
    created_at: datetime
    org_id: str
    roles: list[dict] = []

    @classmethod
    def from_orm_with_roles(cls, user, loaded_roles=None) -> "UserResponse":
        """
        Build response without touching SQLAlchemy lazy attributes.
        Pass loaded_roles explicitly when roles aren't eager-loaded on user.
        """
        roles = loaded_roles if loaded_roles is not None else list(user.roles)
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            phone=user.phone,
            department=user.department,
            job_title=user.job_title,
            avatar_url=user.avatar_url,
            status=user.status,
            email_verified=user.email_verified,
            mfa_enabled=user.mfa_enabled,
            last_login_at=user.last_login_at,
            last_login_ip=user.last_login_ip,
            created_at=user.created_at,
            org_id=user.org_id,
            roles=[{"id": r.id, "name": r.name, "slug": r.slug, "color": r.color} for r in roles],
        )


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class InviteUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    role_ids: list[str]
    department: Optional[str] = None
    job_title: Optional[str] = None
    send_email: bool = True
