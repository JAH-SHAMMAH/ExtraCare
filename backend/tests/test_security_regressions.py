"""Attacks that must keep failing: forged sign-in tokens, other children's records, other schools' data."""
import base64
import json
import time

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.config import get_settings
from app.core.security import create_refresh_token
from app.database import get_db
from app.main import app
from tests.test_parent_report_access import _bearer, family  # noqa: F401

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def http(db):
    async def _g():
        yield db
    app.dependency_overrides[get_db] = _g
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


def _b64(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


async def test_forged_expired_and_wrong_type_tokens_are_refused(http, family):  # noqa: F811
    uid, key = family["parent"].id, get_settings().SECRET_KEY
    soon, past = int(time.time()) + 999, int(time.time()) - 5
    bad = [
        f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64({'sub': uid, 'type': 'access', 'exp': soon})}.",   # unsigned
        jwt.encode({"sub": uid, "type": "access", "exp": soon}, "a-guessed-key", algorithm="HS256"),       # wrong key
        jwt.encode({"sub": uid, "type": "access", "exp": past}, key, algorithm="HS256"),                   # expired
        create_refresh_token({"sub": uid}),                                                                  # refresh token used as access
        "abc.def.ghi",
    ]
    for t in bad:
        assert (await http.get("/api/v1/me/contexts", headers={"Authorization": f"Bearer {t}"})).status_code == 401
    assert (await http.get("/api/v1/me/contexts", headers=_bearer(family["parent"]))).status_code == 200


async def test_a_parent_cannot_read_another_childs_result_history(http, family):  # noqa: F811
    h = _bearer(family["parent"])
    assert (await http.get(f"/api/v1/report-extras/student-history/{family['theirs'].id}", headers=h)).status_code == 403
    assert (await http.get(f"/api/v1/report-extras/student-history/{family['mine'].id}", headers=h)).status_code == 200
    assert (await http.get(f"/api/v1/school/students/{family['theirs'].id}", headers=h)).status_code == 403


async def test_a_parent_cannot_use_staff_or_user_admin_routes(http, family):  # noqa: F811
    h = _bearer(family["parent"])
    uid = family["parent"].id
    assert (await http.get("/api/v1/users", headers=h)).status_code == 403
    assert (await http.patch(f"/api/v1/users/{uid}", headers=h, json={"is_superuser": True})).status_code == 403
    assert (await http.patch(f"/api/v1/users/{uid}/roles", headers=h, json=["x"])).status_code == 403
    assert (await http.get("/api/v1/users/deleted", headers=h)).status_code == 403


async def test_search_boxes_shrug_off_sql_injection(http, family):  # noqa: F811
    from tests.test_parent_report_access import _preset_user
    # parent-scoped list is enough: the injected text must not widen what comes back
    r = await http.get("/api/v1/school/students", headers=_bearer(family["parent"]), params={"search": "' OR 1=1--"})
    assert r.status_code == 200 and r.json()["items"] == []


async def test_login_does_not_reveal_which_accounts_exist_or_are_suspended(http, db, org, family):  # noqa: F811
    from app.core.security import hash_password
    from app.models.user import UserStatus
    p = family["parent"]
    p.hashed_password = hash_password("Correct-Horse-9!")
    await db.commit()
    body = lambda e, pw: {"email": e, "password": pw, "org_slug": org.slug}  # noqa: E731
    nobody = await http.post("/api/v1/auth/login", json=body("nobody@example.com", "x"))
    wrong = await http.post("/api/v1/auth/login", json=body(p.email, "x"))
    assert nobody.status_code == wrong.status_code == 401 and nobody.json() == wrong.json()
    p.status = UserStatus.SUSPENDED
    await db.commit()
    sus_wrong = await http.post("/api/v1/auth/login", json=body(p.email, "x"))
    assert sus_wrong.status_code == 401 and sus_wrong.json() == wrong.json()  # no hint without the password
    assert (await http.post("/api/v1/auth/login", json=body(p.email, "Correct-Horse-9!"))).status_code == 403
