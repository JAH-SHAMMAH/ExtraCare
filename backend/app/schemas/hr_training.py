"""Schemas for Training (programs + sessions)."""

from datetime import date, time, datetime
from typing import Optional
from pydantic import BaseModel, Field


class TrainingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    status: str = "planned"


class TrainingUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None


class TrainingResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    category: Optional[str]
    status: str
    session_count: int = 0
    created_at: datetime
    org_id: str


class SessionCreate(BaseModel):
    training_id: str
    title: Optional[str] = None
    session_date: Optional[date] = None
    start_time: Optional[time] = None
    location: Optional[str] = None
    facilitator: Optional[str] = None


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    session_date: Optional[date] = None
    start_time: Optional[time] = None
    location: Optional[str] = None
    facilitator: Optional[str] = None


class SessionResponse(BaseModel):
    id: str
    training_id: str
    training_title: Optional[str] = None
    title: Optional[str]
    session_date: Optional[date]
    start_time: Optional[time]
    location: Optional[str]
    facilitator: Optional[str]
    created_at: datetime
    org_id: str
