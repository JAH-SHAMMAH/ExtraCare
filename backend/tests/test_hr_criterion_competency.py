"""Batch 4 — appraisal criteria can carry a competency (Competency Mappings).

The competency field is additive on the existing assessment-criteria endpoints.
Recruitment config list types are auto-covered by test_hr_admin_lists (which
iterates HR_LIST_TYPES).
"""
from __future__ import annotations

import uuid

import pytest

from app.models.user import User, UserStatus
from app.routers.hr_development import create_criterion, update_criterion, list_criteria
from app.schemas.hr_development import CriterionCreate, CriterionUpdate
from app.models.hr_admin import HR_LIST_TYPES

pytestmark = pytest.mark.asyncio


async def test_criterion_competency_roundtrip(db, org, teacher):
    c = await create_criterion(CriterionCreate(name="Communication", category="Soft Skills", competency="Interpersonal"),
                               request=None, db=db, current_user=teacher)
    assert c.competency == "Interpersonal"

    updated = await update_criterion(c.id, CriterionUpdate(competency="Leadership"), request=None, db=db, current_user=teacher)
    assert updated.competency == "Leadership"

    # Clearing it back to none works too.
    cleared = await update_criterion(c.id, CriterionUpdate(competency=None), request=None, db=db, current_user=teacher)
    assert cleared.competency is None


async def test_recruitment_list_types_registered():
    assert "recruitment_source" in HR_LIST_TYPES and HR_LIST_TYPES["recruitment_source"] == "Application Sources"
    assert "recruitment_stage" in HR_LIST_TYPES
