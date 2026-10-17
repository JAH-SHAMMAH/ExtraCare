import importlib.util, pathlib, pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from app.database import Base
from app.models import user as _u, organization as _o, role as _r, audit as _a, import_job as _i  # noqa
from app.models.modules import school as _s, hospital as _h, business as _b  # noqa
from app.models.modules.platform import AcademicSession, AcademicTerm, AcademicSubTerm, TermPeriod
from app.models.modules.school import Student, Club, ClubMembership

spec = importlib.util.spec_from_file_location("m144", pathlib.Path(__file__).parent.parent / "alembic/versions/144_seed_term_days_and_clubs.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def test_seed_is_idempotent_and_fills_gaps():
    eng = sa.create_engine("sqlite://")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(AcademicSession(id="s1", org_id="o", name="2026/2027", is_current=True))
        s.add(AcademicSubTerm(id="h", org_id="o", name="Half-Term", position=0, is_active=True))
        s.add(AcademicSubTerm(id="f", org_id="o", name="Full-Term", position=1, is_active=True))
        s.add(AcademicTerm(id="t1", org_id="o", name="Autumn", position=0, is_active=True))
        s.flush()
        s.add(TermPeriod(org_id="o", session_id="s1", term_id="t1", sub_term_id="f", total_days=55))  # admin value kept
        for i in range(5):
            s.add(Student(id=f"st{i}", org_id="o", first_name="A", last_name=str(i), student_id=f"FSN-{i}"))
        s.commit()
    with eng.begin() as c:
        m.seed(c); m.seed(c)
    with Session(eng) as s:
        days = {p.sub_term_id: p.total_days for p in s.query(TermPeriod)}
        assert days == {"f": 55, "h": 30}
        assert s.query(Club).count() == len(m.CLUBS)
        mems = s.query(ClubMembership).all()
        assert all(1 <= sum(1 for x in mems if x.student_id == f"st{i}") <= 2 for i in range(5))
        assert {x.term for x in mems} == {"AUTUMN"}
