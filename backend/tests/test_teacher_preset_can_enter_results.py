"""The REAL teacher role preset (not a stand-in) must be able to enter scores and
the other data that appears on the Nursery / Junior / Secondary reports."""
import uuid
import pytest

from app.models.role import SCHOOL_PERMISSION_PRESETS, Role
from app.models.user import User, UserStatus

pytestmark = pytest.mark.asyncio


async def test_real_teacher_preset_holds_every_result_entry_scope(db, org):
    perms = SCHOOL_PERMISSION_PRESETS["teacher"]
    r = Role(id=str(uuid.uuid4()), name="Teacher", slug="teacher", permissions=perms, org_id=org.id, is_system=True)
    u = User(id=str(uuid.uuid4()), email="t@x.com", full_name="T", status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [r]
    db.add_all([r, u])
    await db.commit()
    for scope in [
        "school:reports:read", "school:reports:write",   # Report Entry (CA1/CA2/Exam), comments, nursery ratings + sample pictures
        "school:grades:write", "school:exams:write",
        "school:students:read", "school:classes:read", "school:subjects:read",
    ]:
        assert u.has_permission(scope), scope
    # …but not the admin-only surfaces.
    assert not u.has_permission("school:students:write")
    assert not u.has_permission("school_admin:write")
