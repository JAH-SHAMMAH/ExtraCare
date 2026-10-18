"""Super-User-only school switches (Educare "General" settings parity).

Stored as one JSON blob on ``Organization.settings["super"]`` so adding a switch
needs no migration. Every field has a default, so an org that has never opened the
page behaves exactly as before.

Two kinds of consumer:
  * ``require_flag`` -- a FastAPI dependency that makes the routes behind a toggle
    answer 403 when the toggle is off (so a hidden menu item is also unreachable
    through the API).
  * ``GET /super-settings/flags`` -- the booleans, for the UI to hide menus/pages.

Nothing secret belongs here. The "default password" fields are the school's
default for NEW accounts, and are only ever returned to a Super User.
"""
from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db
from app.deps import get_current_active_user
from app.models.organization import Organization
from app.models.user import User

KEY = "super"

# (key, tab, section, label, kind, default, help)
#   kind: bool | text | number | select:<a>|<b> | password
FIELDS: list[dict[str, Any]] = []


def _f(key, tab, label, kind="bool", default=False, help="", section="School Settings"):
    FIELDS.append(dict(key=key, tab=tab, section=section, label=label, kind=kind, default=default, help=help))


# ── School Information ───────────────────────────────────────────────────────
_I = "School Information"
_f("school_name", _I, "School Name", "text", "", section=_I)
_f("school_email", _I, "School Email", "text", "", section=_I)
_f("respondent_email", _I, "Respondent Email", "text", "", section=_I)
_f("requisition_respondent_email", _I, "Requisition Respondent Email", "text", "",
   "Receives a notification for every new account requisition.", section=_I)
_f("school_phone", _I, "School Phone No", "text", "", section=_I)
_f("school_address", _I, "School Address", "text", "", section=_I)
_f("school_motto", _I, "School Motto", "text", "", section=_I)
_f("calendar_url", _I, "Calendar URL", "text", "", section=_I)
_f("play_store_url", _I, "Google Play Store URL", "text", "", section=_I)

# ── School Settings: profile defaults ────────────────────────────────────────
_P = "Profile Defaults"
_f("school_domain", "School Settings", "School Domain Name", "text", "",
   "Do not include http:// or www.", section=_P)
_f("parent_default_password", "School Settings", "Parents Default Password", "password", "",
   "Used for new parent accounts.", section=_P)
_f("staff_default_password", "School Settings", "Staff Default Password", "password", "",
   "Used for new staff accounts.", section=_P)
_f("student_default_password", "School Settings", "Student Default Password", "password", "",
   "Used for new student accounts.", section=_P)
_f("force_password_change_on_reset", "School Settings", "Enable Force Password Change On Reset", "bool", True,
   "When ON, a user whose password an admin resets must choose a new one at next sign-in.", section=_P)

# ── School Settings: switches ────────────────────────────────────────────────
_S = "Switches"
_f("subject_teacher_enrollment", "School Settings", "Enable Subject Teacher Student Enrollment", "bool", False, section=_S)
_f("student_program_list", "School Settings", "Enable Student Program List", "bool", False, section=_S)
_f("student_password_reset_email", "School Settings", "Enable Student Password Reset Email", "bool", False, section=_S)
_f("default_admission_date", "School Settings", "Default Admission Date", "bool", False, section=_S)
_f("admission_form_on_sale", "School Settings", "Admission Form on Sale", "bool", True,
   "OFF: new admission applications cannot be created.", section=_S)
_f("mark_previous_attendance", "School Settings", "Mark Previous Attendance", "bool", True,
   "OFF: attendance can only be marked for today.", section=_S)
_f("attendance_period", "School Settings", "Enable Attendance Period", "bool", False, section=_S)
_f("subject_attendance", "School Settings", "Enable Subject Attendance", "bool", False,
   "OFF: the Subject Attendance pages are hidden.", section=_S)
_f("staff_biometric", "School Settings", "Enable Staff Biometric Attendance", "bool", True, section=_S)
_f("student_biometric", "School Settings", "Enable Student Biometric Attendance", "bool", True,
   "OFF: device punches for pupils are refused.", section=_S)
_f("school_biometric", "School Settings", "Enable School Biometric Attendance", "bool", True,
   "OFF: Manage Biometric and every device route are switched off.", section=_S)
_f("teacher_contact_on_parent_dashboard", "School Settings", "Enable Subject Teacher's Contact On Parent Dashboard", "bool", False, section=_S)
_f("result_pay_lock", "School Settings", "Result Pay Lock", "bool", False, section=_S)
_f("one_time_admission_form", "School Settings", "One Time Admission Form", "bool", False, section=_S)
_f("duplicate_admission_message", "School Settings", "Duplicate One Time Admission Form Error Message", "text", "", section=_S)
_f("level_based_reg_pattern", "School Settings", "Level Based Reg. Number Pattern (Admission Form)", "bool", False, section=_S)
_f("venue_based_reg_pattern", "School Settings", "Venue Based Reg. Number Pattern (Admission Form)", "bool", False, section=_S)
_f("state_code", "School Settings", "State Code", "bool", True, section=_S)

# ── Payments / invoices ──────────────────────────────────────────────────────
_M = "Payments & Invoices"
_f("online_charge_bearer", "School Settings", "Online Transaction Charge Bearer", "select:customer|school", "customer",
   "Who pays the online transaction charge: the school or the customer (parents).", section=_M)
_f("invoice_phone_number", "School Settings", "Invoice Phone Number", "bool", False, section=_M)
_f("show_wallet_balance_on_invoice", "School Settings", "Show Wallet Balance on Invoice", "bool", False, section=_M)
_f("show_ebills_code", "School Settings", "Show Ebills Code", "bool", False, section=_M)
_f("invoice_auto_requery", "School Settings", "Toggle Invoice Auto Requery", "bool", False, section=_M)
_f("open_store_for_parents", "School Settings", "Open Store For Parents", "bool", True,
   "OFF: parents and pupils cannot open the Tuckshop / store.", section=_M)
_f("invoice_manual_confirmation", "School Settings", "Toggle Invoice Manual Confirmation", "bool", True, section=_M)
_f("wallet_manual_credit", "School Settings", "Toggle Wallet Manual Credit", "bool", True,
   "OFF: nobody can top a wallet up by hand.", section=_M)
_f("exam_practice_link", "School Settings", "Enable Dashboard Exam Practice Link", "bool", True, section=_M)
_f("auto_instalment", "School Settings", "Auto Instalment (maximum instalments)", "number", 0,
   "Maximum instalment for automatically converted invoices. 0 = off.", section=_M)
_f("max_imprest_top_up", "School Settings", "Maximum Imprest Top Up (NGN)", "number", 30000,
   "Maximum imprest amount per child.", section=_M)

# ── Patterns & formats ───────────────────────────────────────────────────────
_f("reg_number_pattern", "Reg. Number Pattern", "Registration number pattern", "text", "FSN-{SEQ:4}",
   "Tokens: {YEAR} {LEVEL} {SEQ:n}", section="Reg. Number Pattern")
_f("staff_id_pattern", "Staff ID Pattern", "Staff ID pattern", "text", "STF-{SEQ:4}",
   "Tokens: {YEAR} {SEQ:n}", section="Staff ID Pattern")
_f("email_pattern", "Email Pattern", "Staff email pattern", "text", "{first}.{last}@fairviewschoolng.com",
   "Tokens: {first} {last} {SEQ:n}", section="Email Pattern")
_f("student_email_pattern", "Student Email Pattern", "Student email pattern", "text", "{first}.{last}@students.fairviewschoolng.com",
   "Tokens: {first} {last} {SEQ:n}", section="Student Email Pattern")
_f("full_name_format", "Full Name Format and Order", "Full name order", "select:first_last|last_first|last_first_middle|first_middle_last",
   "first_last", "How a person's name is written everywhere.", section="Full Name Format and Order")
_f("student_documents", "Student Documents", "Required student documents (comma separated)", "text",
   "Birth certificate, Passport photograph, Previous report", section="Student Documents")
_f("entrance_exam_subjects", "Entrance Exam Subject", "Entrance exam subjects (comma separated)", "text",
   "English, Mathematics, General Paper", section="Entrance Exam Subject")
_f("student_dashboard_notice", "Student Dashboard Settings", "Notice shown on the student dashboard", "text", "",
   section="Student Dashboard Settings")
_f("teacher_dashboard_notice", "Teacher Dashboard Settings", "Notice shown on the teacher dashboard", "text", "",
   section="Teacher Dashboard Settings")
_f("password_reset_manager_note", "Password Reset Manager", "Password reset instruction shown to users", "text", "",
   section="Password Reset Manager")
_f("payment_security_note", "Payment Security", "Payment security notice shown at checkout", "text", "",
   section="Payment Security")
_f("module_order", "Module Re-order", "Module order (comma separated keys)", "text", "", section="Module Re-order")

BY_KEY = {f["key"]: f for f in FIELDS}
SECRET_KINDS = {"password"}


def is_super_user(user: User) -> bool:
    """The Super User: the platform superadmin or anyone holding the `*` wildcard."""
    return bool(getattr(user, "is_superadmin", False)) or "*" in user.permissions


def _coerce(field: dict, value: Any) -> Any:
    kind = field["kind"]
    if kind == "bool":
        if isinstance(value, bool):
            return value
        raise HTTPException(422, detail=f"'{field['label']}' must be on or off.")
    if kind == "number":
        try:
            n = int(value)
        except (TypeError, ValueError):
            raise HTTPException(422, detail=f"'{field['label']}' must be a whole number.")
        if n < 0:
            raise HTTPException(422, detail=f"'{field['label']}' cannot be negative.")
        return n
    if kind.startswith("select:"):
        opts = kind.split(":", 1)[1].split("|")
        if value not in opts:
            raise HTTPException(422, detail=f"'{field['label']}' must be one of: {', '.join(opts)}.")
        return value
    # text / password
    return str(value if value is not None else "").strip()[:500]


async def _org(db: AsyncSession, org_id: str) -> Organization:
    return (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one()


async def get_values(db: AsyncSession, org_id: str) -> dict[str, Any]:
    org = await _org(db, org_id)
    stored = (org.settings or {}).get(KEY, {}) or {}
    return {f["key"]: stored.get(f["key"], f["default"]) for f in FIELDS}


async def set_values(db: AsyncSession, org_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for k, v in updates.items():
        if k not in BY_KEY:
            raise HTTPException(422, detail=f"Unknown setting: {k}")
        clean[k] = _coerce(BY_KEY[k], v)
    org = await _org(db, org_id)
    settings = dict(org.settings or {})
    blob = dict(settings.get(KEY, {}) or {})
    blob.update(clean)
    settings[KEY] = blob
    org.settings = settings
    flag_modified(org, "settings")
    await db.flush()
    return await get_values(db, org_id)


async def flag(db: AsyncSession, org_id: str, key: str) -> bool:
    return bool((await get_values(db, org_id)).get(key))


def require_flag(key: str, *, owners_only: bool = False):
    """Dependency: 403 when the toggle is OFF.

    ``owners_only`` limits the block to pupils/parents (users without staff read
    access to students), so staff keep using the page while it is closed to families.
    """
    label = BY_KEY[key]["label"]

    async def _dep(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
        if owners_only and user.has_permission("school:students:read"):
            return
        if not await flag(db, user.org_id, key):
            raise HTTPException(status_code=403, detail=f"'{label}' has been switched off by the Super User.")
    return _dep
