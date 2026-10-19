from app.models.role import SCHOOL_PERMISSION_PRESETS as P


def _has(perms, need):
    if "*" in perms or need in perms:
        return True
    parts = need.split(":")
    if f"{parts[0]}:*" in perms:
        return True
    return len(parts) == 3 and f"{parts[0]}:{parts[2]}" in perms


def test_teacher_lacks_pastoral_admin_scope_but_keeps_discipline():
    t = set(P["teacher"])
    assert not _has(t, "school:hostel:read")  # gate for pastoral dashboard/students/report
    assert _has(t, "school:behaviour:read")  # Pastoral Discipline stays


def test_admin_keeps_pastoral():
    assert _has(set(P["org_admin"]), "school:hostel:read")


def test_bank_extras_columns_exist():
    from app.models.modules.school import QuestionBankItem as Q
    assert {"tags", "explanation", "is_examination"} <= set(Q.__table__.c.keys())
