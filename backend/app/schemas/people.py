"""Schemas for the Parents Directory (People & HR, Batch 1).

The directory is a staff-side view over ``ParentGuardian`` link rows — it joins
a parent-role ``User`` to the ``Student``(s) they guard. *Create schemas omit
org_id (pinned server-side from the caller). *Response schemas embed compact
parent + student summaries so the table renders without extra round-trips.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ParentSummary(BaseModel):
    id: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None


class GuardedStudentSummary(BaseModel):
    id: str
    student_id: str
    full_name: str
    class_name: Optional[str] = None


class ParentLinkCreate(BaseModel):
    user_id: str
    student_id: str
    relationship_type: str = "parent"  # parent | guardian | other
    is_primary: bool = False


class ParentLinkUpdate(BaseModel):
    relationship_type: Optional[str] = None
    is_primary: Optional[bool] = None


class ParentLinkResponse(_OrmBase):
    id: str
    relationship_type: str
    is_primary: bool
    parent: ParentSummary
    student: GuardedStudentSummary
    created_at: datetime
    org_id: str


class ParentLinkListResponse(BaseModel):
    items: list[ParentLinkResponse]
    total: int
    page: int
    page_size: int
