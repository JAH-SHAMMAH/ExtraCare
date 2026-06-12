from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import date

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.modules.business import (
    Employee, LeaveRequest, Payslip, InventoryItem, PayrollStatus, LeaveStatus,
    FinanceTransaction, TransactionType,
)
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker

router = APIRouter(
    prefix="/business",
    tags=["Business Module"],
    dependencies=[Depends(require_role_module("business"))],
)

# Generic business scopes
_biz_read = Depends(PermissionChecker("business:read"))
_biz_write = Depends(PermissionChecker("business:write"))

# Sensitive sub-scopes — payroll and finance are separated so that
# regular staff can be denied access even if they have general business:read.
_payroll_read = Depends(PermissionChecker("payroll:read"))
_payroll_write = Depends(PermissionChecker("payroll:write"))
_finance_read = Depends(PermissionChecker("finance:read"))
_finance_write = Depends(PermissionChecker("finance:write"))


# ── Employees ─────────────────────────────────────────────────────────────────

@router.get("/employees", dependencies=[_biz_read])
async def list_employees(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, le=100),
    department: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(Employee).where(Employee.org_id == current_user.org_id, Employee.is_deleted == False)
    if department:
        query = query.where(Employee.department == department)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    employees = result.scalars().all()

    return {
        "items": [_emp_dict(e) for e in employees],
        "total": total,
        "page": page,
    }


# ── Leave Management ──────────────────────────────────────────────────────────

@router.post("/leave-requests", status_code=201, dependencies=[_biz_read])
async def submit_leave(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Find employee record for current user
    emp_result = await db.execute(
        select(Employee).where(Employee.user_id == current_user.id, Employee.org_id == current_user.org_id)
    )
    employee = emp_result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee profile not found.")

    leave = LeaveRequest(
        employee_id=employee.id,
        leave_type=data["leave_type"],
        start_date=date.fromisoformat(data["start_date"]),
        end_date=date.fromisoformat(data["end_date"]),
        days=data.get("days", 1),
        reason=data.get("reason"),
        org_id=current_user.org_id,
    )
    db.add(leave)
    await db.flush()
    return {"id": leave.id, "status": leave.status.value}


@router.patch("/leave-requests/{leave_id}/review", dependencies=[_biz_write])
async def review_leave(
    leave_id: str,
    status: LeaveStatus,
    notes: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(LeaveRequest).where(LeaveRequest.id == leave_id, LeaveRequest.org_id == current_user.org_id)
    )
    leave = result.scalar_one_or_none()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found.")

    leave.status = status
    leave.reviewed_by = current_user.id
    leave.review_notes = notes
    return {"id": leave.id, "status": leave.status.value}


# ── Payroll ───────────────────────────────────────────────────────────────────

@router.get("/payroll", dependencies=[_payroll_read])
async def list_payslips(
    month: int | None = None,
    year: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(Payslip).where(Payslip.org_id == current_user.org_id)
    if year:
        query = query.where(func.strftime("%Y", Payslip.pay_period_start) == str(year))
    if month:
        query = query.where(func.strftime("%m", Payslip.pay_period_start) == f"{month:02d}")

    result = await db.execute(query.order_by(Payslip.pay_period_start.desc()))
    return [_payslip_dict(p) for p in result.scalars().all()]


@router.post("/payroll/run", status_code=201, dependencies=[_payroll_write])
async def run_payroll(
    pay_period_start: date,
    pay_period_end: date,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Generate payslips for all active employees in the org."""
    emp_result = await db.execute(
        select(Employee).where(Employee.org_id == current_user.org_id, Employee.is_deleted == False)
    )
    employees = emp_result.scalars().all()

    generated = []
    for emp in employees:
        gross = emp.base_salary or 0
        tax = round(gross * 0.075, 2)      # 7.5% PAYE simplified
        pension = round(gross * 0.08, 2)    # 8% employee pension
        nhf = round(gross * 0.025, 2)       # 2.5% NHF
        total_deductions = tax + pension + nhf
        net = gross - total_deductions

        payslip = Payslip(
            employee_id=emp.id,
            pay_period_start=pay_period_start,
            pay_period_end=pay_period_end,
            basic_salary=gross,
            gross_salary=gross,
            tax=tax,
            pension=pension,
            nhf=nhf,
            total_deductions=total_deductions,
            net_salary=net,
            status=PayrollStatus.DRAFT,
            org_id=current_user.org_id,
        )
        db.add(payslip)
        generated.append(emp.id)

    return {"generated": len(generated), "period": f"{pay_period_start} to {pay_period_end}"}


# ── Inventory ─────────────────────────────────────────────────────────────────

@router.get("/inventory", dependencies=[_biz_read])
async def list_inventory(
    low_stock_only: bool = False,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(InventoryItem).where(InventoryItem.org_id == current_user.org_id, InventoryItem.is_deleted == False)
    if category:
        query = query.where(InventoryItem.category == category)

    result = await db.execute(query)
    items = result.scalars().all()

    if low_stock_only:
        items = [i for i in items if i.is_low_stock]

    return [_item_dict(i) for i in items]


@router.post("/inventory", status_code=201, dependencies=[_biz_write])
async def add_inventory_item(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    item = InventoryItem(**{k: v for k, v in data.items() if k not in ("org_id", "id")}, org_id=current_user.org_id)
    db.add(item)
    await db.flush()
    return _item_dict(item)


def _emp_dict(e: Employee) -> dict:
    return {
        "id": e.id, "user_id": e.user_id, "employee_code": e.employee_code,
        "department": e.department, "designation": e.designation,
        "employment_type": e.employment_type.value, "hire_date": str(e.hire_date) if e.hire_date else None,
    }


def _payslip_dict(p: Payslip) -> dict:
    return {
        "id": p.id, "employee_id": p.employee_id,
        "pay_period_start": str(p.pay_period_start), "pay_period_end": str(p.pay_period_end),
        "gross_salary": p.gross_salary, "net_salary": p.net_salary, "status": p.status.value,
    }


def _item_dict(i: InventoryItem) -> dict:
    return {
        "id": i.id, "sku": i.sku, "name": i.name, "category": i.category,
        "quantity_in_stock": i.quantity_in_stock, "unit_cost": i.unit_cost,
        "is_low_stock": i.is_low_stock, "reorder_level": i.reorder_level,
    }


# ── Finance Transactions ─────────────────────────────────────────────────────

@router.get("/finance/transactions", dependencies=[_finance_read])
async def list_transactions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, le=100),
    type: str | None = None,
    category: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(FinanceTransaction).where(
        FinanceTransaction.org_id == current_user.org_id,
        FinanceTransaction.is_deleted == False,
    )
    if type:
        query = query.where(FinanceTransaction.type == type)
    if category:
        query = query.where(FinanceTransaction.category == category)
    if start_date:
        query = query.where(FinanceTransaction.transaction_date >= date.fromisoformat(start_date))
    if end_date:
        query = query.where(FinanceTransaction.transaction_date <= date.fromisoformat(end_date))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    result = await db.execute(
        query.order_by(FinanceTransaction.transaction_date.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    txns = result.scalars().all()

    return {
        "items": [_txn_dict(t) for t in txns],
        "total": total,
        "page": page,
    }


@router.post("/finance/transactions", status_code=201, dependencies=[_finance_write])
async def create_transaction(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a single finance transaction."""
    txn_type = data.get("type")
    if txn_type:
        try:
            txn_type = TransactionType(txn_type)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid type: {txn_type}. Must be one of: income, expense, transfer, refund")

    amount = data.get("amount")
    if amount is None:
        raise HTTPException(status_code=422, detail="amount is required")

    txn_date = data.get("transaction_date")
    if not txn_date:
        raise HTTPException(status_code=422, detail="transaction_date is required")

    txn = FinanceTransaction(
        transaction_date=date.fromisoformat(txn_date),
        type=txn_type or TransactionType.EXPENSE,
        category=data.get("category"),
        description=data.get("description"),
        amount=float(amount),
        currency=data.get("currency", "NGN"),
        reference=data.get("reference"),
        payment_method=data.get("payment_method"),
        counterparty=data.get("counterparty"),
        notes=data.get("notes"),
        import_job_id=data.get("import_job_id"),
        org_id=current_user.org_id,
    )
    db.add(txn)
    await db.flush()
    return _txn_dict(txn)


@router.get("/finance/overview", dependencies=[_finance_read])
async def finance_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Summary of income vs expense for the organization."""
    query = select(FinanceTransaction).where(
        FinanceTransaction.org_id == current_user.org_id,
        FinanceTransaction.is_deleted == False,
    )
    result = await db.execute(query)
    txns = result.scalars().all()

    total_income = sum(t.amount for t in txns if t.type == TransactionType.INCOME)
    total_expense = sum(t.amount for t in txns if t.type == TransactionType.EXPENSE)

    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "net": total_income - total_expense,
        "transaction_count": len(txns),
    }


def _txn_dict(t: FinanceTransaction) -> dict:
    return {
        "id": t.id,
        "transaction_date": str(t.transaction_date),
        "type": t.type.value if t.type else None,
        "category": t.category,
        "description": t.description,
        "amount": t.amount,
        "currency": t.currency,
        "reference": t.reference,
        "payment_method": t.payment_method,
        "counterparty": t.counterparty,
        "notes": t.notes,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }
