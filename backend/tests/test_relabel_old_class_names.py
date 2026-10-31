import importlib.util
from pathlib import Path

_p = Path(__file__).resolve().parents[1] / "alembic/versions/162_old_class_labels_in_staff.py"
_spec = importlib.util.spec_from_file_location("m162", _p)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


def test_relabel_maps_old_names():
    assert m.relabel("SS2 Class Teacher") == "Year 11 Class Teacher"
    assert m.relabel("jss 1 teacher") == "Year 7 teacher"
    assert m.relabel("Primary 4") == "Year 4"
    assert m.relabel("Nursery 2") == "Reception"


def test_relabel_leaves_other_text_and_is_idempotent():
    for t in ["Year 11 Class Teacher", "Mr Moss2", "Mathematics", None]:
        assert m.relabel(t) == t
    once = m.relabel("SS3 A")
    assert m.relabel(once) == once
