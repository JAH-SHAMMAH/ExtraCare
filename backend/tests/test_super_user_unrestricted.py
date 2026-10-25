"""The Super User (permissions ['*']) must reach everything; the medical dashboard's
page_size=500 must not 422 for anyone."""
import uuid
import pytest
from app.core.security import create_access_token
from app.models.user import User, UserStatus
from app.models.role import Role
from tests.test_result_flow_e2e import API, http, world  # noqa: F401

pytestmark = pytest.mark.asyncio


async def test_super_user_reaches_medical_and_admin_areas(http, db, org, world):
    role = Role(id=str(uuid.uuid4()), name="Super User", slug="super_user", permissions=["*"], org_id=org.id, is_system=True)
    u = User(id=str(uuid.uuid4()), email=f"su-{uuid.uuid4().hex[:5]}@example.com", full_name="Director",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u]); await db.commit()
    h = {"Authorization": f"Bearer {create_access_token({'sub': u.id})}"}
    for path in ("/medical/records?page_size=500", "/school/students?page_size=500",
                 "/finance/broad-view/dashboard", "/finance/invoices", "/sms/templates"):
        r = await http.get(f"{API}{path}", headers=h)
        assert r.status_code not in (401, 403, 422), (path, r.status_code, r.text[:150])
