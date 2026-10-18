"""Back-office modules (Restaurant, Procurement, Livestock, Rentals, Fun Fair,
General Ledger, Imprest, Debt Memo) behind one generic, tenant-scoped API.

Every module is closed until the Super User switches it on in Super Settings
(``module_<name>``). Reading needs ``<namespace>:read``, changing needs
``<namespace>:write``. Module-specific rules (balanced journals, imprest balance,
debt settlement, booking clashes) live in the hooks below.
"""
import csv
import io
import json
from datetime import date as date_type
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.modules.office import LABELS, MODELS, MODULES, NAMESPACE
from app.models.user import User
from app.services.super_settings import _role_slugs, flag, is_super_user

router = APIRouter(prefix="/office", tags=["Back office"])

BOOL_DEFAULT_FALSE = {"paid"}


def _bad(msg: str):
    raise HTTPException(422, detail=msg)


async def _gate(module: str, write: bool, db: AsyncSession, user: User):
    if module not in MODULES:
        raise HTTPException(404, "Unknown module.")
    if not await flag(db, user.org_id, f"module_{module}"):
        raise HTTPException(403, f"'{LABELS[module]}' has not been switched on by the Super User.")
    perm = f"{NAMESPACE[module]}:{'write' if write else 'read'}"
    if not user.has_permission(perm):
        raise HTTPException(403, f"Permission required: {perm}")


def _model(module: str, resource: str):
    m = MODELS.get((module, resource))
    if m is None:
        raise HTTPException(404, "Unknown resource.")
    return m


def _out(module: str, resource: str, row) -> dict:
    d = {"id": row.id, "created_at": row.created_at.isoformat() if row.created_at else None}
    for c, (k, _r) in MODULES[module][resource].items():
        v = getattr(row, c)
        d[c] = v.isoformat() if isinstance(v, date_type) else v
    return d


async def _all(db, module, resource, org_id):
    M = _model(module, resource)
    rows = (await db.execute(select(M).where(M.org_id == org_id, M.is_deleted == False))).scalars().all()  # noqa: E712
    return rows


async def _get(db, module, resource, org_id, rid):
    M = _model(module, resource)
    row = (await db.execute(select(M).where(M.id == rid, M.org_id == org_id, M.is_deleted == False))).scalar_one_or_none()  # noqa: E712
    if row is None:
        raise HTTPException(404, "Not found.")
    return row


async def _coerce(db, module, resource, body: dict, org_id: str, partial: bool) -> dict:
    out: dict = {}
    for c, (k, req) in MODULES[module][resource].items():
        if c not in body:
            if req and not partial:
                _bad(f"'{c.replace('_', ' ')}' is required.")
            continue
        v = body[c]
        if v in (None, "") and k != "bool":
            if req:
                _bad(f"'{c.replace('_', ' ')}' is required.")
            out[c] = None
            continue
        if k in ("str", "text"):
            v = str(v).strip()
            if req and not v:
                _bad(f"'{c.replace('_', ' ')}' is required.")
            v = v[:255] if k == "str" else v[:4000]
        elif k == "float":
            try:
                v = round(float(v), 2)
            except (TypeError, ValueError):
                _bad(f"'{c}' must be a number.")
            if v < 0:
                _bad(f"'{c}' cannot be negative.")
        elif k == "int":
            try:
                v = int(v)
            except (TypeError, ValueError):
                _bad(f"'{c}' must be a whole number.")
            if v < 0:
                _bad(f"'{c}' cannot be negative.")
        elif k == "bool":
            v = bool(v)
        elif k == "date":
            try:
                v = date_type.fromisoformat(str(v)[:10])
            except ValueError:
                _bad(f"'{c}' must be a date (YYYY-MM-DD).")
        elif k == "json":
            if not isinstance(v, (list, dict)):
                _bad(f"'{c}' must be a list.")
        elif k.startswith("choice:"):
            if v not in k.split(":", 1)[1].split("|"):
                _bad(f"'{c}' must be one of: {', '.join(k.split(':', 1)[1].split('|'))}.")
        elif k.startswith("ref:"):
            parent = k.split(":", 1)[1]
            await _get(db, module, parent, org_id, str(v))  # 404 if not this school's row
        out[c] = v
    return out


def _lines_total(items) -> float:
    total = 0.0
    for it in items or []:
        try:
            total += float(it.get("qty", 1)) * float(it.get("price", 0))
        except (TypeError, ValueError, AttributeError):
            _bad("Each line needs a numeric qty and price.")
    return round(total, 2)


# ── balances ────────────────────────────────────────────────────────────────
async def imprest_balance(db, org_id, fund) -> float:
    bal = float(fund.float_amount or 0)
    for e in await _all(db, "imprest", "entries", org_id):
        if e.fund_id == fund.id:
            bal += -float(e.amount) if e.kind == "expense" else float(e.amount)
    return round(bal, 2)


async def debt_paid(db, org_id, memo_id) -> float:
    return round(sum(float(p.amount) for p in await _all(db, "debtmemo", "payments", org_id) if p.memo_id == memo_id), 2)


# ── module hooks ────────────────────────────────────────────────────────────
async def _before_save(db, module, resource, data: dict, org_id: str, existing=None, user=None):
    if (module, resource) in (("restaurant", "orders"), ("procurement", "requests"), ("serviceinvoices", "invoices"), ("offlineinvoices", "invoices")) and "items" in data:
        data["total"] = _lines_total(data["items"])
    if (module, resource) in (("serviceinvoices", "invoices"), ("offlineinvoices", "invoices")):
        total = float(data.get("total", getattr(existing, "total", 0)) or 0)
        paid = float(data.get("paid", getattr(existing, "paid", 0)) or 0)
        if paid > total + 0.001:
            _bad(f"Amount paid ({paid:,.2f}) is more than the invoice total ({total:,.2f}).")
        status = data.get("status", getattr(existing, "status", None))
        if status not in ("cancelled", "draft"):
            data["status"] = ("paid" if paid >= total - 0.001 and total > 0 else "part_paid" if paid > 0
                              else ("unpaid" if module == "offlineinvoices" else "sent"))
    if (module, resource) == ("suppliers", "bills"):
        if float(data.get("paid", getattr(existing, "paid", 0)) or 0) > float(data.get("amount", getattr(existing, "amount", 0)) or 0) + 0.001:
            _bad("Amount paid is more than the bill.")
    if (module, resource) in (("spa", "appointments"), ("storeappointments", "appointments")):
        get = lambda k: data.get(k, getattr(existing, k, None))  # noqa: E731
        if (get("status") or "booked") == "booked":
            for b in await _all(db, module, resource, org_id):
                if (existing is None or b.id != existing.id) and (b.status or "booked") == "booked" and b.appt_date == get("appt_date") \
                        and b.appt_time == get("appt_time") and (module == "storeappointments" and (b.staff_member or "") == (get("staff_member") or "")
                                                                 or module == "spa" and b.service_id == get("service_id")):
                    _bad("That time slot is already booked.")
    if (module, resource) == ("restaurant", "orders") and "items" not in data and existing is None:
        data["total"] = 0.0
    if (module, resource) == ("rentals", "bookings"):
        get = lambda k: data.get(k, getattr(existing, k, None))  # noqa: E731
        s, e = get("start_date"), get("end_date")
        if s and e and e < s:
            _bad("End date cannot be before the start date.")
        status = get("status") or "booked"
        asset_id = get("asset_id")
        if asset_id:
            asset = await _get(db, "rentals", "assets", org_id, asset_id)
            if existing is None and asset.available is False:
                _bad("This item is marked as not available for hire.")
        if status in ("booked", "out") and s and e:
            for b in await _all(db, "rentals", "bookings", org_id):
                if b.asset_id == asset_id and (existing is None or b.id != existing.id) and (b.status or "booked") in ("booked", "out") \
                        and b.start_date <= e and s <= b.end_date:
                    _bad("That item is already booked for some of those dates.")
    if (module, resource) == ("imprest", "entries") and data.get("kind", getattr(existing, "kind", None)) == "expense":
        fund = await _get(db, "imprest", "funds", org_id, data.get("fund_id", getattr(existing, "fund_id", None)))
        if fund.status == "closed":
            _bad("This imprest fund is closed.")
        bal = await imprest_balance(db, org_id, fund)
        if existing is not None and existing.kind == "expense":
            bal += float(existing.amount)
        if float(data.get("amount", getattr(existing, "amount", 0))) > bal:
            _bad(f"Not enough in the fund. Balance is {bal:,.2f}.")
    if (module, resource) == ("debtmemo", "payments"):
        memo = await _get(db, "debtmemo", "memos", org_id, data.get("memo_id", getattr(existing, "memo_id", None)))
        if memo.status in ("settled", "written_off"):
            _bad("This debt memo is already closed.")
        outstanding = float(memo.amount) - await debt_paid(db, org_id, memo.id) + (float(existing.amount) if existing is not None else 0)
        if float(data.get("amount", 0)) > outstanding + 0.001:
            _bad(f"That is more than the outstanding {outstanding:,.2f}.")
    if (module, resource) == ("procurement", "limits") and not is_super_user(user):
        _bad("Only the Super User sets approval limits.")
    if (module, resource) == ("procurement", "requests"):
        data.pop("approved_by", None)  # stamped by the server, never typed
        new = data.get("status")
        if new in ("approved", "ordered", "received") and (existing is None or existing.status != new):
            total = float(data.get("total", getattr(existing, "total", 0)) or 0)
            if existing is not None and existing.status in ("draft", "submitted", "rejected") and new != "approved":
                _bad("A request must be approved before it is ordered.")
            if new == "approved" and not is_super_user(user):
                if existing is not None and (existing.requested_by or "") == (user.email or "") :
                    _bad("You can't approve your own request.")
                limits = {l.role: float(l.max_amount) for l in await _all(db, "procurement", "limits", org_id)}
                if limits:
                    mine = [limits[sl] for sl in _role_slugs(user) if sl in limits]
                    if not mine or max(mine) < total:
                        _bad(f"This request ({total:,.2f}) is above your approval limit"
                             + (f" of {max(mine):,.2f}." if mine else ". You have no approval limit set."))
            if new == "approved":
                data["approved_by"] = user.email
    if (module, resource) == ("ledger", "accounts"):
        code = data.get("code")
        if code and any(a.code == code and (existing is None or a.id != existing.id) for a in await _all(db, "ledger", "accounts", org_id)):
            _bad(f"Account code {code} already exists.")
    if (module, resource) == ("ledger", "journals"):
        accounts = {a.id for a in await _all(db, "ledger", "accounts", org_id)}
        lines = data["lines"]
        if not isinstance(lines, list) or len(lines) < 2:
            _bad("A journal needs at least two lines.")
        dr = cr = 0.0
        for ln in lines:
            if not isinstance(ln, dict) or ln.get("account_id") not in accounts:
                _bad("Every line needs one of your accounts.")
            try:
                d, c = float(ln.get("debit") or 0), float(ln.get("credit") or 0)
            except (TypeError, ValueError):
                _bad("Debit and credit must be numbers.")
            if d < 0 or c < 0 or (d and c) or not (d or c):
                _bad("Each line must have either a debit or a credit amount.")
            dr, cr = dr + d, cr + c
        if round(dr, 2) != round(cr, 2):
            _bad(f"Journal does not balance: debits {dr:,.2f}, credits {cr:,.2f}.")
        data["lines"] = [{"account_id": l["account_id"], "debit": round(float(l.get("debit") or 0), 2),
                          "credit": round(float(l.get("credit") or 0), 2)} for l in lines]


async def _after_save(db, module, resource, row, org_id: str):
    if (module, resource) == ("livestock", "events") and row.kind in ("sale", "death"):
        animal = await _get(db, "livestock", "animals", org_id, row.animal_id)
        animal.status = "sold" if row.kind == "sale" else "deceased"
    if (module, resource) == ("debtmemo", "payments"):
        memo = await _get(db, "debtmemo", "memos", org_id, row.memo_id)
        await db.flush()
        paid = await debt_paid(db, org_id, memo.id)
        memo.status = "settled" if paid >= float(memo.amount) - 0.001 else ("partly_paid" if paid > 0 else "open")


def _defaults(module, resource, data: dict):
    for c, (k, _r) in MODULES[module][resource].items():
        if c not in data:
            if k == "bool":
                data[c] = c not in BOOL_DEFAULT_FALSE
            elif k.startswith("choice:"):
                data[c] = k.split(":", 1)[1].split("|")[0]
            elif k in ("float", "int"):
                data[c] = 0
    return data


# ── routes ──────────────────────────────────────────────────────────────────
@router.get("/{module}/schema")
async def schema(module: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    await _gate(module, False, db, user)
    return {"module": module, "label": LABELS[module], "can_write": user.has_permission(f"{NAMESPACE[module]}:write"),
            "resources": {r: {c: {"kind": k, "required": req} for c, (k, req) in cols.items()} for r, cols in MODULES[module].items()}}


@router.get("/{module}/summary")
async def summary(module: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    await _gate(module, False, db, user)
    org = user.org_id
    A = lambda r: _all(db, module, r, org)  # noqa: E731
    if module == "restaurant":
        orders = await A("orders")
        return {"orders": len(orders), "open": sum(o.status == "open" for o in orders),
                "revenue": round(sum(o.total or 0 for o in orders if o.status == "paid"), 2)}
    if module == "procurement":
        reqs = await A("requests")
        return {"awaiting_approval": sum(r.status == "submitted" for r in reqs),
                "approved_value": round(sum(r.total or 0 for r in reqs if r.status in ("approved", "ordered", "received")), 2),
                "suppliers": len(await A("suppliers"))}
    if module == "livestock":
        animals = await A("animals")
        events = await A("events")
        return {"active": sum(a.status == "active" for a in animals), "total": len(animals), "spend": round(sum(e.cost or 0 for e in events), 2)}
    if module == "rentals":
        bookings = await A("bookings")
        live = [b for b in bookings if b.status != "cancelled"]
        return {"active_bookings": sum(b.status in ("booked", "out") for b in bookings),
                "unpaid": round(sum(b.amount or 0 for b in live if not b.paid), 2), "income": round(sum(b.amount or 0 for b in live if b.paid), 2)}
    if module == "funfair":
        entries = await A("entries")
        events = {e.id: e.name for e in await A("events")}
        per: dict = {}
        for e in entries:
            per[e.event_id] = per.get(e.event_id, 0) + float(e.amount or 0)
        return {"raised": round(sum(per.values()), 2), "per_event": [{"event": events.get(k, "?"), "raised": round(v, 2)} for k, v in per.items()]}
    if module == "ledger":
        accts = await A("accounts")
        tot = {a.id: [0.0, 0.0] for a in accts}
        for j in await A("journals"):
            for ln in j.lines or []:
                if ln["account_id"] in tot:
                    tot[ln["account_id"]][0] += ln["debit"]
                    tot[ln["account_id"]][1] += ln["credit"]
        rows = [{"id": a.id, "code": a.code, "name": a.name, "type": a.type, "debit": round(tot[a.id][0], 2), "credit": round(tot[a.id][1], 2),
                 "balance": round(tot[a.id][0] - tot[a.id][1], 2)} for a in sorted(accts, key=lambda x: x.code)]
        return {"trial_balance": rows, "total_debit": round(sum(r["debit"] for r in rows), 2), "total_credit": round(sum(r["credit"] for r in rows), 2)}
    if module == "imprest":
        funds = await A("funds")
        return {"funds": [{"id": f.id, "holder": f.holder, "status": f.status, "float_amount": f.float_amount,
                           "balance": await imprest_balance(db, org, f)} for f in funds]}
    if module == "debtmemo":
        memos = await A("memos")
        rows = []
        for m in memos:
            paid = await debt_paid(db, org, m.id)
            rows.append({"id": m.id, "debtor": m.debtor, "amount": m.amount, "paid": paid, "outstanding": 0 if m.status == "written_off" else round(m.amount - paid, 2), "status": m.status})
        return {"outstanding": round(sum(r["outstanding"] for r in rows), 2), "memos": rows}
    if module == "suppliers":
        bills = await A("bills")
        return {"suppliers": len(await A("directory")), "billed": round(sum(b.amount or 0 for b in bills), 2),
                "owing": round(sum((b.amount or 0) - (b.paid or 0) for b in bills), 2)}
    if module in ("serviceinvoices", "offlineinvoices"):
        inv = [i for i in await A("invoices") if i.status != "cancelled"]
        return {"invoiced": round(sum(i.total or 0 for i in inv), 2), "collected": round(sum(i.paid or 0 for i in inv), 2),
                "outstanding": round(sum((i.total or 0) - (i.paid or 0) for i in inv), 2), "invoices": len(inv)}
    if module == "spa":
        ap = await A("appointments")
        return {"booked": sum(a.status == "booked" for a in ap), "completed": sum(a.status == "done" for a in ap),
                "income": round(sum(a.amount or 0 for a in ap if a.status == "done" and a.paid), 2)}
    if module == "storeappointments":
        ap = await A("appointments")
        return {"booked": sum(a.status == "booked" for a in ap), "attended": sum(a.status == "attended" for a in ap), "no_shows": sum(a.status == "no_show" for a in ap)}
    raise HTTPException(404)


@router.get("/{module}/{resource}")
async def list_rows(module: str, resource: str, q: str | None = None, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    await _gate(module, False, db, user)
    _model(module, resource)
    rows = await _all(db, module, resource, user.org_id)
    out = [_out(module, resource, r) for r in sorted(rows, key=lambda r: r.created_at or 0, reverse=True)]
    if q:
        ql = q.lower()
        out = [o for o in out if any(ql in str(v).lower() for v in o.values())]
    return {"items": out[:500], "total": len(out)}


@router.get("/{module}/{resource}/export")
async def export_rows(module: str, resource: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    """Everything in one table as a spreadsheet (CSV) file."""
    await _gate(module, False, db, user)
    _model(module, resource)
    cols = list(MODULES[module][resource])
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([c.replace("_", " ").title() for c in cols])
    for r in sorted(await _all(db, module, resource, user.org_id), key=lambda r: r.created_at or 0):
        d = _out(module, resource, r)
        w.writerow([json.dumps(d[c]) if isinstance(d[c], (list, dict)) else ("" if d[c] is None else
                    # a cell starting with = + - @ would run as a formula in Excel
                    ("'" + d[c] if isinstance(d[c], str) and d[c][:1] in "=+-@" else d[c])) for c in cols])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{module}-{resource}.csv"'})


@router.post("/ledger/sync")
async def sync_ledger(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    """Copy the school's posted fee invoices and payroll runs into this ledger.

    Safe to run again: each source record becomes ONE journal (tagged in
    ``reference``) and is skipped if it is already there.
    """
    from app.models.modules.finance import Invoice, PayrollRun
    await _gate("ledger", True, db, user)
    org = user.org_id
    Acc, Jnl = MODELS[("ledger", "accounts")], MODELS[("ledger", "journals")]
    have = {a.code: a for a in await _all(db, "ledger", "accounts", org)}
    wanted = [("1000", "Cash and Bank", "asset"), ("1100", "Fees Receivable", "asset"), ("2100", "Salaries Payable", "liability"),
              ("2200", "Deductions Payable", "liability"), ("4100", "Fee Income", "income"), ("5100", "Salaries Expense", "expense")]
    for code, name, typ in wanted:
        if code not in have:
            have[code] = Acc(org_id=org, code=code, name=name, type=typ)
            db.add(have[code])
    await db.flush()
    A = {c: a.id for c, a in have.items()}
    done = {j.reference for j in await _all(db, "ledger", "journals", org) if j.reference}
    added = 0

    def post(ref, d, memo, lines):
        nonlocal added
        db.add(Jnl(org_id=org, entry_date=d, memo=memo, reference=ref,
                   lines=[{"account_id": A[c], "debit": round(float(dr), 2), "credit": round(float(cr), 2)} for c, dr, cr in lines if dr or cr]))
        added += 1

    inv = (await db.execute(select(Invoice).where(Invoice.org_id == org, Invoice.is_deleted == False,  # noqa: E712
                                                  Invoice.status.in_(("posted", "paid"))))).scalars().all()
    for i in inv:
        d = i.invoice_date or date_type.today()
        if f"INV:{i.number}" not in done and float(i.total or 0) > 0:
            post(f"INV:{i.number}", d, f"Invoice {i.number} - {i.customer_name}", [("1100", i.total, 0), ("4100", 0, i.total)])
        if i.status == "paid" and f"INVPAY:{i.number}" not in done and float(i.total or 0) > 0:
            post(f"INVPAY:{i.number}", d, f"Payment for invoice {i.number}", [("1000", i.total, 0), ("1100", 0, i.total)])
    runs = (await db.execute(select(PayrollRun).where(PayrollRun.org_id == org, PayrollRun.is_deleted == False,  # noqa: E712
                                                      PayrollRun.status == "posted"))).scalars().all()
    for r in runs:
        if f"PAYROLL:{r.id}" not in done and float(r.total_gross or 0) > 0:
            post(f"PAYROLL:{r.id}", r.run_date or date_type.today(), f"Payroll {r.period_label}",
                 [("5100", r.total_gross, 0), ("2100", 0, r.total_net), ("2200", 0, r.total_deductions)])
    await db.commit()
    return {"journals_added": added, "invoices_seen": len(inv), "payroll_runs_seen": len(runs)}


@router.post("/{module}/{resource}", status_code=201)
async def create_row(module: str, resource: str, body: dict, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    await _gate(module, True, db, user)
    M = _model(module, resource)
    data = await _coerce(db, module, resource, body, user.org_id, partial=False)
    data = _defaults(module, resource, data)
    if (module, resource) == ("procurement", "requests"):
        data["requested_by"] = user.email
        if data.get("status") in ("approved", "ordered", "received"):
            data["status"] = "submitted"  # a request is approved by someone else, after it exists
    await _before_save(db, module, resource, data, user.org_id, user=user)
    row = M(org_id=user.org_id, **data)
    db.add(row)
    await db.flush()
    await _after_save(db, module, resource, row, user.org_id)
    await db.commit()
    return _out(module, resource, row)


@router.put("/{module}/{resource}/{rid}")
async def update_row(module: str, resource: str, rid: str, body: dict, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    await _gate(module, True, db, user)
    if (module, resource) == ("ledger", "journals"):
        raise HTTPException(405, "Posted journals can't be edited. Post a correcting journal instead.")
    row = await _get(db, module, resource, user.org_id, rid)
    data = await _coerce(db, module, resource, body, user.org_id, partial=True)
    await _before_save(db, module, resource, data, user.org_id, existing=row, user=user)
    for k, v in data.items():
        setattr(row, k, v)
    await db.flush()
    await _after_save(db, module, resource, row, user.org_id)
    await db.commit()
    return _out(module, resource, row)


@router.delete("/{module}/{resource}/{rid}", status_code=204)
async def delete_row(module: str, resource: str, rid: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    await _gate(module, True, db, user)
    if (module, resource) == ("ledger", "journals"):
        raise HTTPException(405, "Posted journals can't be deleted. Post a correcting journal instead.")
    row = await _get(db, module, resource, user.org_id, rid)
    if (module, resource) == ("ledger", "accounts"):
        if any(ln["account_id"] == rid for j in await _all(db, "ledger", "journals", user.org_id) for ln in (j.lines or [])):
            raise HTTPException(409, "This account has journal entries and can't be deleted.")
    row.is_deleted = True
    await db.commit()
