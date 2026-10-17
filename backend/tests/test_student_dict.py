from datetime import date
from app.models.modules.school import Student
from app.routers.modules.school import _student_dict


def test_student_dict_has_full_profile_and_class_name():
    s = Student(id="s", org_id="o", student_id="FSN-1", first_name="A", last_name="B", gender="female",
                phone="080", address="Abuja", date_of_birth=date(2015, 3, 2), photo_url="/uploads/p.png",
                guardian_name="Mum", guardian_phone="081", class_id="c1")
    d = _student_dict(s, "Year 7 A")
    assert d["class_name"] == "Year 7 A"
    assert d["gender"] == "female" and d["phone"] == "080" and d["address"] == "Abuja"
    assert d["avatar_url"] == "/uploads/p.png" and d["date_of_birth"] == "2015-03-02"
    assert d["guardian_name"] == "Mum"
