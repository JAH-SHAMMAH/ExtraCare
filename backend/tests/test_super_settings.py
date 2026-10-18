"""Super Settings: only the Super User writes; toggles really close their routes."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.database import get_db
from app.models.organization import SubscriptionTier
from app.models.role import SCHOOL_PERMISSION_PRESETS
from tests.test_parent_report_access import _preset_user, _bearer

pytestmark = pytest.mark.asyncio
B = "/api/v1/super-settings"


@pytest_asyncio.fixture
async def http(db):
    async def _get_db():
        yield db
    app.dependency_overrides[get_db] = _get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def people(db, org):
    org.subscription_tier = SubscriptionTier.ENTERPRISE
    db.add(org)
    await db.flush()
    return {"super": await _preset_user(db, org, "super_user"),
            "admin": await _preset_user(db, org, "org_admin"),
            "parent": await _preset_user(db, org, "parent")}


async def test_only_super_user_can_read_or_write(http, people):
    assert (await http.get(B, headers=_bearer(people["admin"]))).status_code == 403
    assert (await http.put(B, json={"values": {"wallet_manual_credit": False}},
                           headers=_bearer(people["admin"]))).status_code == 403
    assert (await http.get(B, headers=_bearer(people["super"]))).status_code == 200


async def test_super_user_toggle_persists_and_shows_in_flags(http, people):
    h = _bearer(people["super"])
    r = await http.put(B, json={"values": {"subject_attendance": True, "school_motto": "Soaring High"}}, headers=h)
    assert r.status_code == 200 and r.json()["values"]["subject_attendance"] is True
    # any signed-in user can read the booleans (to hide menus), but never text/passwords
    f = (await http.get(f"{B}/flags", headers=_bearer(people["parent"]))).json()
    assert f["subject_attendance"] is True and "school_motto" not in f and "parent_default_password" not in f


async def test_bad_values_are_rejected(http, people):
    h = _bearer(people["super"])
    assert (await http.put(B, json={"values": {"nope": True}}, headers=h)).status_code == 422
    assert (await http.put(B, json={"values": {"subject_attendance": "yes"}}, headers=h)).status_code == 422
    assert (await http.put(B, json={"values": {"online_charge_bearer": "bank"}}, headers=h)).status_code == 422


async def test_switching_biometric_off_closes_its_routes(http, people):
    h = _bearer(people["super"])
    assert (await http.get("/api/v1/biometric/devices", headers=h)).status_code != 403
    await http.put(B, json={"values": {"school_biometric": False}}, headers=h)
    r = await http.get("/api/v1/biometric/devices", headers=h)
    assert r.status_code == 403 and "Super User" in r.text
    await http.put(B, json={"values": {"school_biometric": True}}, headers=h)
    assert (await http.get("/api/v1/biometric/devices", headers=h)).status_code != 403


async def test_admission_form_toggle_closes_new_applications(http, people):
    h = _bearer(people["super"])
    await http.put(B, json={"values": {"admission_form_on_sale": False}}, headers=h)
    r = await http.post("/api/v1/enrollment/applications", json={"applicant_name": "X"}, headers=h)
    assert r.status_code == 403 and "Super User" in r.text


async def test_wallet_manual_credit_toggle(http, people):
    h = _bearer(people["super"])
    await http.put(B, json={"values": {"wallet_manual_credit": False}}, headers=h)
    r = await http.post("/api/v1/finance/wallets/x/topup", json={"amount": 100}, headers=h)
    assert r.status_code == 403 and "Super User" in r.text


async def test_password_reset_follows_force_change_toggle(http, db, org, people):
    h = _bearer(people["super"])
    target = await _preset_user(db, org, "teacher")
    await http.put(B, json={"values": {"force_password_change_on_reset": False}}, headers=h)
    r = await http.post(f"/api/v1/users/{target.id}/reset-password", headers=h)
    assert r.status_code == 200 and r.json()["force_password_change"] is False
