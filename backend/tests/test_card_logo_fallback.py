import pytest
from tests.test_not_configured_sub_term import _world
from app.routers.modules.platform import report_card

pytestmark = pytest.mark.asyncio


async def test_card_prints_the_school_logo_when_no_letterhead_logo_is_saved(db, org):
    w = await _world(db, org)
    org.logo_url = "https://cdn.example/school.png"
    await db.commit()
    card = await report_card(student_id=w.pupil.id, term_id=w.term.id, sub_term_id=w.full.id, db=db, current_user=w.admin)
    assert card.branding.logo_url == "https://cdn.example/school.png"
