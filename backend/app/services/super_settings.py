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

# ── School Images (uploaded on the School Images tab; the value is the image address) ──
IMAGE_SPECS = {  # key -> (min width, min height)
    "login_image": (1389, 920),
    "main_logo": (113, 112),
    "general_logo": (200, 40),
}
_IM = "School Images"
_f("login_image", _IM, "Login Page Image", "image", "", section=_IM)
_f("main_logo", _IM, "Main Logo", "image", "", section=_IM)
_f("general_logo", _IM, "General Logo", "image", "", section=_IM)

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

# ── Optional back-office modules: built, but closed until the Super User opens them ──
_M = "Optional Modules"
for _k, _l in [("restaurant", "Restaurant"), ("procurement", "Procurement"), ("livestock", "Livestock"), ("rentals", "Rentals"),
               ("funfair", "Fun Fair"), ("customers", "All Customers"), ("whatsapp", "WhatsApp"), ("clubattendance", "Club Attendance"), ("commbook", "Communication Book"), ("empowerment", "Empowerment"), ("suppliers", "Suppliers"), ("serviceinvoices", "Service Invoices"), ("offlineinvoices", "Offline Invoices"),
               ("spa", "Spa Services"), ("storeappointments", "Store Appointment Manager"), ("ledger", "General Ledger"), ("imprest", "Imprest"), ("debtmemo", "Debt Memo")]:
    _f(f"module_{_k}", "School Settings", f"Enable {_l} Module", "bool", False, f"OFF: {_l} is hidden and its API is closed.", section=_M)
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
   "The most a single Imprest top-up may be. 0 = no limit.", section=_M)

# ── Patterns & formats ───────────────────────────────────────────────────────
_f("full_name_format", "Full Name Format and Order", "Full name order", "select:first_last|last_first|last_first_middle|first_middle_last",
   "first_last", "How a person's name is written everywhere.", section="Full Name Format and Order")
_f("student_documents", "Student Documents", "Required student documents (comma separated)", "text",
   "Birth certificate, Passport photograph, Previous report", section="Student Documents")
_f("entrance_exam_subjects", "Entrance Exam Subject", "Entrance exam subjects (comma separated)", "text",
   "English, Mathematics, General Paper", section="Entrance Exam Subject")
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
    if kind == "image":
        v = str(value or "").strip()
        if v and not (v.startswith("/uploads/") or v.startswith("https://")):
            raise HTTPException(422, detail=f"'{field['label']}' must be an uploaded image.")
        return v[:500]
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


# ═════════════════════════════════════════════════════════════════════════════
# Structured settings (tables, matrices, per-role maps)
# ═════════════════════════════════════════════════════════════════════════════
STUDENT_DASHBOARD_ITEMS = [
    ("show_ctb_link", "Show CTB Link", True), ("show_eclassroom_link", "Show eClassroom Link", True),
    ("show_teacher_rating_tab", "Show Teacher Rating Tab", True), ("show_result_insight", "Show Result Insight", True),
    ("show_result_analysis", "Show Result Analysis", True), ("show_lesson_planner", "Show Lesson Planner", True),
    ("show_communication_book", "Show Communication Book", True), ("show_results", "Show Results", True),
    ("show_assignment", "Show Assignment", True), ("show_subjects", "Show Subjects", True),
    ("show_timetable", "Show Timetable", True), ("show_chat", "Show Chat", True),
    ("show_photo_journals", "Show Photo Journals", True), ("show_calendar", "Show Calendar", True),
    ("show_medical_reports", "Show Medical Reports", True), ("show_remarks", "Show Subject/Class Remarks", True),
    ("show_tuckshop_record", "Show Tuck Shop Record", True), ("show_attendance_history", "Show Attendance History", True),
    ("allow_document_update", "Allow Document Update", True), ("use_school_name_as_alias", "Use School Name as Alias", False),
]
TEACHER_DASHBOARD_ITEMS = [("show_house_point_entry_link", "Show House Point Entry Link", True)]

NOTIFICATION_EVENTS = [
    ("class_attendance", "Class Attendance", True, True), ("news_feed", "News Feed", True, True),
    ("new_chat_message", "New Chat Message", False, False), ("birthday", "Birthday Message", True, True),
    ("invoice_published", "Invoice Published", True, True), ("lesson_plan_approval", "Lesson Plan Approval", False, False),
    ("job_anniversary", "Job Anniversary Message", False, False), ("result_publish", "Result Publish Message", True, True),
    ("new_enquiry", "New Enquiry Message", True, True), ("weekly_remarks", "Weekly Remarks", False, True),
    ("eclassroom", "eClassroom", False, True), ("medicals", "Medicals", False, True),
    ("hostel_exeat", "Hostel Exeat", False, True), ("cbt_submit", "Cbt Submit", False, True),
    ("book_published", "Book Published Message", False, True),
]
NOTIFICATION_CHANNELS = ["email_push", "sms", "birthday", "work_anniversary", "whatsapp"]

ROLE_PERM_ITEMS = [
    ("message", "Message Permission", "May send direct messages (and to which roles)."),
    ("avatar", "Avatar Permission", "May change their own profile picture."),
    ("news_feed", "News Feed Permission", "May see and use the news feed."),
    ("direct_post", "Direct Post Permission", "May publish posts on the news feed."),
    ("direct_comment", "Direct Comment Permission", "May comment on posts."),
    ("birthday", "Birthday Permission", "Birthday messages are shown to / sent by this role."),
    ("contact_info", "Full Name, Email, Gender & Phone Number Permission", "May see other people's contact details."),
]

DOC_CATEGORY_DEFAULTS = [
    {"name": n, "admission_status": "not_required", "required": False, "active": True, "medical": False}
    for n in ("Birth Certificate", "International Passport Data Page", "Immunization Records",
              "Previous Class Result", "Acceptance Form", "Attestation of Good Conduct",
              "Medical Fitness Form", "Students Reference")
]

PATTERN_ITEM_TYPES = {
    "first_name", "surname", "other_name", "text", "year", "sequence", "level",
}
PATTERN_KEYS = ["reg_number", "staff_id", "email", "student_email"]
PATTERN_DEFAULTS = {
    "reg_number": {"items": [{"type": "text", "text": "FSN-"}, {"type": "sequence", "length": 4}], "separator": "", "suffix": ""},
    "staff_id": {"items": [{"type": "text", "text": "STF-"}, {"type": "sequence", "length": 4}], "separator": "", "suffix": ""},
    "email": {"items": [{"type": "first_name", "length": "full"}, {"type": "surname", "length": "full"}], "separator": ".", "suffix": "@fairviewschoolng.com"},
    "student_email": {"items": [{"type": "first_name", "length": "full"}, {"type": "surname", "length": "full"}], "separator": ".", "suffix": "@students.fairviewschoolng.com"},
}


def _struct_defaults() -> dict[str, Any]:
    return {
        "student_dashboard": {k: d for k, _l, d in STUDENT_DASHBOARD_ITEMS},
        "teacher_dashboard": {k: d for k, _l, d in TEACHER_DASHBOARD_ITEMS},
        "doc_categories": DOC_CATEGORY_DEFAULTS,
        "patterns": PATTERN_DEFAULTS,
        "notification_prefs": {k: {"email": e, "push": p} for k, _l, e, p in NOTIFICATION_EVENTS},
        "role_perms": {},
        "module_access": {},
    }


def struct_meta() -> dict[str, Any]:
    return {
        "student_dashboard_items": [{"key": k, "label": l} for k, l, _d in STUDENT_DASHBOARD_ITEMS],
        "teacher_dashboard_items": [{"key": k, "label": l} for k, l, _d in TEACHER_DASHBOARD_ITEMS],
        "notification_events": [{"key": k, "label": l} for k, l, _e, _p in NOTIFICATION_EVENTS],
        "role_perm_items": [{"key": k, "label": l, "help": h} for k, l, h in ROLE_PERM_ITEMS],
        "pattern_keys": PATTERN_KEYS, "pattern_item_types": sorted(PATTERN_ITEM_TYPES),
    }


def _bad(msg: str):
    raise HTTPException(422, detail=msg)


def _clean_struct(key: str, v: Any) -> Any:
    if key in ("student_dashboard", "teacher_dashboard"):
        items = STUDENT_DASHBOARD_ITEMS if key == "student_dashboard" else TEACHER_DASHBOARD_ITEMS
        allowed = {k for k, _l, _d in items}
        if not isinstance(v, dict) or set(v) - allowed or not all(isinstance(x, bool) for x in v.values()):
            _bad(f"{key}: expected on/off values for known items only.")
        return v
    if key == "doc_categories":
        if not isinstance(v, list) or len(v) > 100:
            _bad("doc_categories: expected a list.")
        out = []
        for r in v:
            name = str((r or {}).get("name", "")).strip()[:120]
            if not name:
                _bad("Every document category needs a name.")
            st = r.get("admission_status", "not_required")
            if st not in ("required", "not_required"):
                _bad("admission_status must be 'required' or 'not_required'.")
            out.append({"name": name, "admission_status": st, "required": bool(r.get("required")),
                        "active": bool(r.get("active", True)), "medical": bool(r.get("medical"))})
        return out
    if key == "patterns":
        if not isinstance(v, dict) or set(v) - set(PATTERN_KEYS):
            _bad("patterns: unknown pattern.")
        out = {}
        for pk, pat in v.items():
            items = (pat or {}).get("items", [])
            if not isinstance(items, list) or not items or len(items) > 12:
                _bad("A pattern needs 1 to 12 items.")
            clean = []
            for it in items:
                t = it.get("type")
                if t not in PATTERN_ITEM_TYPES:
                    _bad(f"Unknown pattern item: {t}")
                length = it.get("length", "full")
                if t in ("first_name", "surname", "other_name"):
                    if length != "full" and not (isinstance(length, int) and 1 <= length <= 20):
                        _bad("Name length must be 'full' or 1-20 letters.")
                elif t == "sequence":
                    if not (isinstance(length, int) and 1 <= length <= 10):
                        _bad("Sequence length must be 1-10 digits.")
                clean.append({"type": t, "length": length, "text": str(it.get("text", ""))[:40] if t == "text" else ""})
            out[pk] = {"items": clean, "separator": str(pat.get("separator", ""))[:3], "suffix": str(pat.get("suffix", ""))[:80]}
        return out
    if key == "notification_prefs":
        keys = {k for k, *_ in NOTIFICATION_EVENTS}
        if not isinstance(v, dict) or set(v) - keys:
            _bad("notification_prefs: unknown event.")
        return {k: {"email": bool(x.get("email")), "push": bool(x.get("push"))} for k, x in v.items()}
    if key == "role_perms":
        if not isinstance(v, dict):
            _bad("role_perms: expected a map of role -> permissions.")
        allowed = {k for k, _l, _h in ROLE_PERM_ITEMS}
        out = {}
        for role, perms in v.items():
            out[str(role)[:100]] = {
                **{k: bool(perms.get(k, True)) for k in allowed},
                "can_create_group": bool(perms.get("can_create_group", True)),
                "message_roles": [str(r)[:100] for r in (perms.get("message_roles") or [])][:60],
            }
        return out
    if key == "module_access":
        if not isinstance(v, dict):
            _bad("module_access: expected a map of role -> hidden pages.")
        return {str(r)[:100]: sorted({str(h)[:200] for h in (hs or [])})[:2000] for r, hs in v.items()}
    _bad(f"Unknown structured setting: {key}")


STRUCT_KEYS = list(_struct_defaults())


async def get_struct(db: AsyncSession, org_id: str) -> dict[str, Any]:
    org = await _org(db, org_id)
    stored = ((org.settings or {}).get(KEY, {}) or {}).get("_struct", {}) or {}
    out = _struct_defaults()
    for k in STRUCT_KEYS:
        if k in stored:
            out[k] = stored[k]
    return out


async def set_struct(db: AsyncSession, org_id: str, key: str, value: Any) -> Any:
    if key not in STRUCT_KEYS:
        raise HTTPException(404, detail="Unknown setting.")
    clean = _clean_struct(key, value)
    org = await _org(db, org_id)
    settings = dict(org.settings or {})
    blob = dict(settings.get(KEY, {}) or {})
    st = dict(blob.get("_struct", {}) or {})
    st[key] = clean
    blob["_struct"] = st
    settings[KEY] = blob
    org.settings = settings
    flag_modified(org, "settings")
    await db.flush()
    return clean


def _role_slugs(user: User) -> list[str]:
    return [r.slug for r in user._scoped_roles()]


def role_perm_allows(struct: dict, user: User, perm: str) -> bool:
    """True unless EVERY role the user holds has explicitly switched `perm` off.
    A role with no entry is unrestricted, and the Super User is never blocked."""
    if is_super_user(user):
        return True
    rp = struct.get("role_perms", {})
    slugs = _role_slugs(user) or [""]
    return any(rp.get(sl, {}).get(perm, True) for sl in slugs)


def hidden_hrefs_for(struct: dict, user: User) -> list[str]:
    """Pages hidden from this user: hidden in EVERY role they hold. Never for the Super User."""
    if is_super_user(user):
        return []
    ma = struct.get("module_access", {})
    slugs = _role_slugs(user)
    if not slugs:
        return []
    sets = [set(ma.get(sl, [])) for sl in slugs]
    return sorted(set.intersection(*sets)) if sets else []


def require_role_perm(perm: str, label: str):
    async def _dep(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
        if not role_perm_allows(await get_struct(db, user.org_id), user, perm):
            raise HTTPException(status_code=403, detail=f"{label} has been switched off for your role by the Super User.")
    return _dep
