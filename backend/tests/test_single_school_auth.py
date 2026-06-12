"""
Single-school authentication tests.

The historical suite runs in multi-tenant mode (see conftest). These tests
opt back into SINGLE_SCHOOL_MODE at runtime to verify the Fairview behaviour:
  • org_slug is not required — the one org is resolved server-side
  • only @fairviewschoolng.com emails may authenticate (domain gate)
  • the account must still exist, be active, and pass the password check
  • no auto-provisioning of unknown accounts
  • public organisation registration is disabled
"""

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.security import hash_password
from app.models.user import User, UserStatus
from app.routers.auth import login, register_organization
from app.schemas.auth import LoginRequest, RegisterOrgRequest


class _FakeHeaders(dict):
    def get(self, k, d=None):  # mimic Starlette Headers.get
        return super().get(k, d)


def _fake_request():
    return SimpleNamespace(headers=_FakeHeaders(), client=SimpleNamespace(host="127.0.0.1"))


@pytest.fixture
def single_school_mode(org):
    """Enable single-school mode and pin the resolver to the test org's slug.

    Patches the *module-bound* settings objects that the auth path actually
    holds (auth.py / single_school.py captured `settings = get_settings()` at
    import). We can't go through get_settings() here: another test
    (test_live) calls get_settings.cache_clear(), so a fresh get_settings()
    would return a different instance than the one the routers reference.
    Restored afterwards so the rest of the suite stays multi-tenant.
    """
    import app.routers.auth as auth_mod
    import app.core.single_school as ss_mod

    targets = {id(m.settings): m.settings for m in (auth_mod, ss_mod)}.values()
    prev = [(s, s.SINGLE_SCHOOL_MODE, s.SCHOOL_ORG_SLUG) for s in targets]
    for s in targets:
        s.SINGLE_SCHOOL_MODE = True
        s.SCHOOL_ORG_SLUG = org.slug
    yield
    for s, mode, slug in prev:
        s.SINGLE_SCHOOL_MODE = mode
        s.SCHOOL_ORG_SLUG = slug


@pytest.fixture
async def fairview_user(db, org):
    u = User(
        id=str(uuid.uuid4()),
        email="principal@fairviewschoolng.com",
        full_name="Dr Principal",
        hashed_password=hash_password("Str0ng-Pass!23"),
        status=UserStatus.ACTIVE,
        email_verified=True,
        org_id=org.id,
    )
    db.add(u)
    await db.commit()
    return u


@pytest.mark.asyncio
async def test_login_without_org_slug_succeeds(db, single_school_mode, fairview_user):
    resp = await login(
        LoginRequest(email="principal@fairviewschoolng.com", password="Str0ng-Pass!23"),
        _fake_request(),
        db,
    )
    assert resp.user.email == "principal@fairviewschoolng.com"
    assert resp.access_token


@pytest.mark.asyncio
async def test_login_blocks_non_fairview_domain(db, single_school_mode, fairview_user):
    with pytest.raises(HTTPException) as exc:
        await login(
            LoginRequest(email="intruder@gmail.com", password="whatever"),
            _fake_request(),
            db,
        )
    assert exc.value.status_code == 403
    assert "fairviewschoolng.com" in exc.value.detail


@pytest.mark.asyncio
async def test_login_valid_domain_unknown_user_is_401(db, single_school_mode):
    with pytest.raises(HTTPException) as exc:
        await login(
            LoginRequest(email="ghost@fairviewschoolng.com", password="whatever"),
            _fake_request(),
            db,
        )
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_password_is_401(db, single_school_mode, fairview_user):
    with pytest.raises(HTTPException) as exc:
        await login(
            LoginRequest(email="principal@fairviewschoolng.com", password="wrong"),
            _fake_request(),
            db,
        )
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_public_registration_disabled(db, single_school_mode):
    with pytest.raises(HTTPException) as exc:
        await register_organization(
            RegisterOrgRequest(
                org_name="Another School", org_slug="another-school", industry="school",
                admin_name="Admin", admin_email="admin@fairviewschoolng.com", password="Str0ng-Pass!23",
            ),
            _fake_request(),
            db,
        )
    assert exc.value.status_code == 403
