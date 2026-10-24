import importlib.util
import uuid
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_backfill_applies_paid_invoices_once():
    e = sa.create_engine("sqlite://")
    with e.begin() as c:
        c.execute(sa.text("CREATE TABLE invoices (id text, org_id text, student_id text, status text, total numeric, is_deleted boolean)"))
        c.execute(sa.text("CREATE TABLE student_fee_records (id text, org_id text, student_id text, total_fee numeric, paid_amount numeric, "
                          "discount_amount numeric, outstanding_balance numeric, is_paid boolean, payment_status text, is_deleted boolean, created_at text)"))
        c.execute(sa.text("INSERT INTO invoices VALUES ('i1','o','s1','paid',170000,0),('i2','o','s2','posted',50,0)"))
        c.execute(sa.text("INSERT INTO student_fee_records VALUES ('f1','o','s1',170000,0,0,170000,0,'unpaid',0,'1'),"
                          "('f2','o','s2',50,0,0,50,0,'unpaid',0,'1')"))
    p = Path(__file__).parent.parent / "alembic/versions/159_backfill_fee_record_payments.py"
    spec = importlib.util.spec_from_file_location("m159", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    for _ in range(2):  # second run must change nothing
        with e.begin() as c:
            with Operations.context(MigrationContext.configure(c)):
                m.upgrade()
    with e.connect() as c:
        rows = {r[0]: r[1:] for r in c.execute(sa.text("SELECT id, paid_amount, outstanding_balance, payment_status FROM student_fee_records"))}
    assert rows["f1"] == (170000, 0, "paid")
    assert rows["f2"] == (0, 50, "unpaid")   # posted (unpaid) invoice is not counted
