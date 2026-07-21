"""Schemas for HR Documents & Templates."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: Optional[str] = Field(default=None, max_length=80)
    description: Optional[str] = None
    file_url: str = Field(min_length=1, max_length=500)
    filename: Optional[str] = None


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    category: Optional[str] = Field(default=None, max_length=80)
    description: Optional[str] = None


class DocumentResponse(BaseModel):
    id: str
    title: str
    category: Optional[str]
    description: Optional[str]
    file_url: str
    filename: Optional[str]
    created_at: datetime
    org_id: str
