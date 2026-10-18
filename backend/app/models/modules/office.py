"""Back-office modules: Restaurant, Procurement, Livestock, Rentals, Fun Fair,
General Ledger, Imprest and Debt Memo.

Each resource is declared once in ``MODULES``; the tables are generated from it
and the same table drives the generic API in ``routers/modules/office.py``.
Column kinds: str, text, float, int, bool, date, json, ref:<resource> (a parent
row in the same module and school), or "choice:a|b|c".
"""
from sqlalchemy import Boolean, Column, Date, Float, Integer, JSON, String, Text

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin, UUIDMixin

# module -> permission namespace guarding it
NAMESPACE = {
    "restaurant": "school_admin", "livestock": "school_admin", "rentals": "school_admin", "funfair": "school_admin",
    "suppliers": "finance_admin", "empowerment": "school_admin", "customers": "school_admin", "whatsapp": "school_admin",
    "clubattendance": "school_admin", "commbook": "school_admin", "serviceinvoices": "finance_admin", "offlineinvoices": "finance_admin",
    "spa": "school_admin", "storeappointments": "school_admin",
    "procurement": "finance_admin", "ledger": "finance_admin", "imprest": "finance_admin", "debtmemo": "finance_admin",
}
# modules whose staff need different permissions from their namespace (read, write)
PERMS = {"commbook": ("school:students:read", "school:reports:write"), "clubattendance": ("school:students:read", "school:clubs:write")}
LABELS = {
    "restaurant": "Restaurant", "procurement": "Procurement", "livestock": "Livestock", "rentals": "Rentals",
    "funfair": "Fun Fair", "ledger": "General Ledger", "imprest": "Imprest", "debtmemo": "Debt Memo",
    "suppliers": "Suppliers", "serviceinvoices": "Service Invoices", "offlineinvoices": "Offline Invoices",
    "spa": "Spa Services", "customers": "All Customers", "whatsapp": "WhatsApp", "clubattendance": "Club Attendance", "commbook": "Communication Book", "empowerment": "Empowerment", "storeappointments": "Store Appointment Manager",
}

# resource -> {col: (kind, required)}; first-listed order is the display order.
MODULES: dict[str, dict[str, dict[str, tuple[str, bool]]]] = {
    "restaurant": {
        "menu": {"name": ("str", True), "category": ("str", False), "price": ("float", True), "available": ("bool", False), "description": ("text", False)},
        "orders": {"customer": ("str", True), "items": ("json", False), "total": ("float", False),
                   "status": ("choice:open|served|paid|cancelled", False), "note": ("text", False)},
    },
    "procurement": {
        "suppliers": {"name": ("str", True), "category": ("str", False), "phone": ("str", False), "email": ("str", False), "address": ("text", False)},
        "requests": {"title": ("str", True), "supplier_id": ("ref:suppliers", False), "items": ("json", False), "total": ("float", False),
                     "status": ("choice:draft|submitted|approved|rejected|ordered|received", False), "requested_by": ("str", False), "approved_by": ("str", False), "approvals": ("json", False), "awaiting": ("str", False), "note": ("text", False)},
        "limits": {"role": ("str", True), "max_amount": ("float", True)},
        "rfqs": {"request_id": ("ref:requests", False), "title": ("str", True), "issued_date": ("date", True), "closing_date": ("date", False),
                 "status": ("choice:open|closed|awarded", False), "note": ("text", False)},
        "quotes": {"rfq_id": ("ref:rfqs", True), "supplier_id": ("ref:suppliers", True), "amount": ("float", True), "delivery_days": ("int", False),
                   "valid_until": ("date", False), "status": ("choice:submitted|selected|rejected", False), "note": ("text", False)},
        "orders": {"po_number": ("str", False), "request_id": ("ref:requests", False), "supplier_id": ("ref:suppliers", True), "quote_id": ("ref:quotes", False),
                   "order_date": ("date", True), "expected_date": ("date", False), "items": ("json", True), "total": ("float", False),
                   "status": ("choice:draft|pending_approval|approved|sent|part_received|received|cancelled", False),
                   "created_by": ("str", False), "approved_by": ("str", False), "approvals": ("json", False), "awaiting": ("str", False), "note": ("text", False)},
        "grns": {"order_id": ("ref:orders", True), "received_date": ("date", True), "items": ("json", True),
                 "status": ("choice:draft|pending_approval|approved|rejected", False), "received_by": ("str", False), "approved_by": ("str", False), "note": ("text", False)},
        "settings": {"po_prefix": ("str", False), "rfq_threshold": ("float", False), "min_quotes": ("int", False)},
    },
    "livestock": {
        "animals": {"tag": ("str", True), "species": ("str", True), "breed": ("str", False), "sex": ("choice:male|female", False),
                    "birth_date": ("date", False), "status": ("choice:active|sold|deceased", False), "notes": ("text", False)},
        "events": {"animal_id": ("ref:animals", True), "kind": ("choice:feeding|vaccination|treatment|weighing|sale|death|other", True),
                   "event_date": ("date", True), "cost": ("float", False), "note": ("text", False)},
    },
    "rentals": {
        "assets": {"name": ("str", True), "rate": ("float", True), "unit": ("choice:hour|day|event", False), "available": ("bool", False), "description": ("text", False)},
        "bookings": {"asset_id": ("ref:assets", True), "renter": ("str", True), "contact": ("str", False), "start_date": ("date", True), "end_date": ("date", True),
                     "amount": ("float", False), "paid": ("bool", False), "status": ("choice:booked|out|returned|cancelled", False)},
    },
    "funfair": {
        "events": {"name": ("str", True), "event_date": ("date", True), "venue": ("str", False), "notes": ("text", False)},
        "entries": {"event_id": ("ref:events", True), "kind": ("choice:stall|ticket|game|food|donation", True), "label": ("str", True),
                    "quantity": ("int", False), "amount": ("float", False)},
    },
    "ledger": {
        "accounts": {"code": ("str", True), "name": ("str", True), "type": ("choice:asset|liability|equity|income|expense", True)},
        "journals": {"entry_date": ("date", True), "memo": ("str", True), "reference": ("str", False), "lines": ("json", True)},
    },
    "imprest": {
        "funds": {"holder": ("str", True), "purpose": ("str", False), "float_amount": ("float", True), "status": ("choice:open|closed", False)},
        "entries": {"fund_id": ("ref:funds", True), "kind": ("choice:expense|replenish", True), "entry_date": ("date", True),
                    "description": ("str", True), "amount": ("float", True)},
    },
    "empowerment": {
        "programmes": {"name": ("str", True), "category": ("choice:skills|business|education|health|agriculture|other", False), "start_date": ("date", False),
                       "end_date": ("date", False), "budget": ("float", False), "status": ("choice:planned|active|completed|cancelled", False), "description": ("text", False)},
        "beneficiaries": {"name": ("str", True), "programme_id": ("ref:programmes", True), "phone": ("str", False), "enrolled_on": ("date", False),
                          "status": ("choice:active|graduated|dropped", False), "note": ("text", False)},
        "trainings": {"programme_id": ("ref:programmes", True), "topic": ("str", True), "training_date": ("date", True), "trainer": ("str", False),
                      "attendees": ("int", False), "note": ("text", False)},
        "support": {"beneficiary_id": ("ref:beneficiaries", True), "kind": ("choice:stipend|equipment|grant|materials|other", True), "support_date": ("date", True),
                    "amount": ("float", True), "note": ("text", False)},
    },
    "customers": {
        "directory": {"name": ("str", True), "type": ("choice:parent|staff|walk_in|company|other", False), "phone": ("str", False), "email": ("str", False),
                      "address": ("text", False), "status": ("choice:active|inactive", False), "notes": ("text", False)},
    },
    "whatsapp": {
        "templates": {"name": ("str", True), "body": ("text", True)},
        "messages": {"recipient": ("str", True), "phone": ("str", True), "message": ("text", True),
                     "status": ("choice:queued|opened|sent|failed", False), "sent_by": ("str", False)},
    },
    "clubattendance": {
        "sessions": {"club_id": ("ext:club", True), "session_date": ("date", True), "topic": ("str", False), "note": ("text", False)},
        "marks": {"session_id": ("ref:sessions", True), "student_id": ("ext:student", True), "present": ("bool", False), "note": ("str", False)},
    },
    "commbook": {
        "entries": {"student_id": ("ext:student", True), "entry_date": ("date", True),
                    "category": ("choice:general|homework|behaviour|health|achievement|reminder", False), "message": ("text", True),
                    "direction": ("choice:school_to_home|home_to_school", False), "author": ("str", False),
                    "acknowledged": ("bool", False), "reply": ("text", False)},
    },
    "debtmemo": {
        "memos": {"debtor": ("str", True), "debtor_type": ("choice:parent|staff|supplier|other", False), "amount": ("float", True), "reason": ("str", True),
                  "memo_date": ("date", True), "due_date": ("date", False), "status": ("choice:open|partly_paid|settled|written_off", False)},
        "payments": {"memo_id": ("ref:memos", True), "amount": ("float", True), "paid_on": ("date", True), "note": ("text", False)},
    },
    "suppliers": {
        "directory": {"name": ("str", True), "category": ("str", False), "contact_person": ("str", False), "phone": ("str", False),
                      "email": ("str", False), "address": ("text", False), "status": ("choice:active|inactive", False)},
        "bills": {"supplier_id": ("ref:directory", True), "reference": ("str", False), "bill_date": ("date", True), "due_date": ("date", False),
                  "amount": ("float", True), "paid": ("float", False), "description": ("text", False)},
    },
    "serviceinvoices": {
        "clients": {"name": ("str", True), "phone": ("str", False), "email": ("str", False), "address": ("text", False)},
        "invoices": {"client_id": ("ref:clients", True), "invoice_date": ("date", True), "due_date": ("date", False), "items": ("json", True),
                     "total": ("float", False), "paid": ("float", False), "status": ("choice:sent|draft|part_paid|paid|cancelled", False), "note": ("text", False)},
    },
    "offlineinvoices": {
        "invoices": {"payer": ("str", True), "student_ref": ("str", False), "invoice_date": ("date", True), "items": ("json", True), "total": ("float", False),
                     "method": ("choice:cash|bank_transfer|pos|cheque", False), "receipt_no": ("str", False), "paid": ("float", False),
                     "status": ("choice:unpaid|part_paid|paid|cancelled", False), "note": ("text", False)},
    },
    "spa": {
        "services": {"name": ("str", True), "price": ("float", True), "duration_minutes": ("int", False), "available": ("bool", False), "description": ("text", False)},
        "appointments": {"service_id": ("ref:services", True), "client": ("str", True), "phone": ("str", False), "appt_date": ("date", True),
                         "appt_time": ("str", True), "amount": ("float", False), "paid": ("bool", False),
                         "status": ("choice:booked|done|cancelled|no_show", False)},
    },
    "storeappointments": {
        "appointments": {"visitor": ("str", True), "phone": ("str", False), "purpose": ("str", False), "appt_date": ("date", True), "appt_time": ("str", True),
                         "staff_member": ("str", False), "status": ("choice:booked|attended|cancelled|no_show", False), "note": ("text", False),
                         "requested_by": ("str", False)},
    },
}

_COL = {"str": lambda: Column(String(255)), "text": lambda: Column(Text), "float": lambda: Column(Float, default=0.0),
        "int": lambda: Column(Integer, default=0), "bool": lambda: Column(Boolean),
        "date": lambda: Column(Date), "json": lambda: Column(JSON)}

MODELS: dict[tuple[str, str], type] = {}
for _m, _res in MODULES.items():
    for _r, _cols in _res.items():
        attrs = {"__tablename__": f"off_{_m}_{_r}", "org_id": Column(String(36), nullable=False, index=True)}
        for _c, (_k, _req) in _cols.items():
            if _k.startswith(("ref:", "ext:")):
                attrs[_c] = Column(String(36), index=True)
            elif _k.startswith("choice:"):
                attrs[_c] = Column(String(30))
            else:
                attrs[_c] = _COL[_k]()
        MODELS[(_m, _r)] = type(f"Off{_m.title()}{_r.title()}", (Base, UUIDMixin, TimestampMixin, SoftDeleteMixin), attrs)
