"""Organization Structure (HR Admin) — the reporting hierarchy of org units.

A light self-referential tree: each unit has an optional parent, an optional head
(a staff User) and a type (division / department / unit / team). Distinct from the
flat HR Departments managed list (which just tags a staff member's department);
this is the arrangement of units into a hierarchy. Deliberately light — no
positions/headcount modelling — per the 'managed lists lighter' scope.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, Integer, ForeignKey, Index

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


class OrgUnit(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """One node in the organization tree."""
    __tablename__ = "org_units"

    name = Column(String(150), nullable=False)
    unit_type = Column(String(40), nullable=True)   # division | department | unit | team (free-ish)
    parent_id = Column(String(36), ForeignKey("org_units.id", ondelete="SET NULL"), nullable=True, index=True)
    head_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    description = Column(Text, nullable=True)
    position = Column(Integer, default=0, nullable=False)

    __table_args__ = (Index("ix_org_units_org_parent", "org_id", "parent_id"),)
