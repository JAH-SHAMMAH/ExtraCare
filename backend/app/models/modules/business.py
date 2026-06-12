from sqlalchemy import Column, String, Integer, Float, Date, DateTime, Text, Boolean, Enum, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin
import enum


class EmploymentType(str, enum.Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERN = "intern"


class LeaveStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class PayrollStatus(str, enum.Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"


class Employee(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Extends User with HR-specific fields."""
    __tablename__ = "employees"

    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    employee_code = Column(String(50), nullable=True, index=True)
    department = Column(String(255), nullable=True)
    designation = Column(String(255), nullable=True)
    employment_type = Column(Enum(EmploymentType), default=EmploymentType.FULL_TIME)
    hire_date = Column(Date, nullable=True)
    termination_date = Column(Date, nullable=True)
    manager_id = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Compensation
    base_salary = Column(Float, nullable=True)
    currency = Column(String(10), default="NGN")
    pay_frequency = Column(String(20), default="monthly")  # weekly, biweekly, monthly
    bank_name = Column(String(255), nullable=True)
    bank_account_no = Column(String(50), nullable=True)  # encrypt in production

    # Compliance
    tax_id = Column(String(50), nullable=True)
    pension_id = Column(String(50), nullable=True)
    nhf_id = Column(String(50), nullable=True)  # National Housing Fund

    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    user = relationship("User", foreign_keys=[user_id])
    manager = relationship("User", foreign_keys=[manager_id])
    leave_requests = relationship("LeaveRequest", back_populates="employee")
    payslips = relationship("Payslip", back_populates="employee")


class LeaveRequest(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "leave_requests"

    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, index=True)
    leave_type = Column(String(50), nullable=False)  # annual, sick, maternity, emergency
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    days = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(Enum(LeaveStatus), default=LeaveStatus.PENDING)
    reviewed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    review_notes = Column(Text, nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    employee = relationship("Employee", back_populates="leave_requests")


class Payslip(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "payslips"

    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, index=True)
    pay_period_start = Column(Date, nullable=False)
    pay_period_end = Column(Date, nullable=False)
    pay_date = Column(Date, nullable=True)
    status = Column(Enum(PayrollStatus), default=PayrollStatus.DRAFT)

    # Earnings
    basic_salary = Column(Float, default=0.0)
    allowances = Column(JSON, default=list)   # [{"name": "Housing", "amount": 20000}]
    bonuses = Column(JSON, default=list)
    gross_salary = Column(Float, default=0.0)

    # Deductions
    tax = Column(Float, default=0.0)
    pension = Column(Float, default=0.0)
    nhf = Column(Float, default=0.0)
    other_deductions = Column(JSON, default=list)
    total_deductions = Column(Float, default=0.0)

    net_salary = Column(Float, default=0.0)
    currency = Column(String(10), default="NGN")
    notes = Column(Text, nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    employee = relationship("Employee", back_populates="payslips")


class InventoryItem(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "inventory_items"

    sku = Column(String(100), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    unit = Column(String(50), nullable=True)  # kg, pcs, litres
    quantity_in_stock = Column(Float, default=0.0)
    reorder_level = Column(Float, default=10.0)
    unit_cost = Column(Float, default=0.0)
    unit_price = Column(Float, default=0.0)
    supplier = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    barcode = Column(String(100), nullable=True)
    image_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    @property
    def is_low_stock(self) -> bool:
        return self.quantity_in_stock <= self.reorder_level


class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    REFUND = "refund"


class FinanceTransaction(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Financial transaction record — income, expense, transfer, or refund."""
    __tablename__ = "finance_transactions"

    transaction_date = Column(Date, nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    category = Column(String(100), nullable=True)  # Rent, Utilities, Sales, etc.
    description = Column(Text, nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="NGN")
    reference = Column(String(100), nullable=True, index=True)  # Invoice #, receipt #
    payment_method = Column(String(50), nullable=True)  # cash, bank_transfer, card, mobile_money
    counterparty = Column(String(255), nullable=True)  # vendor/customer name
    notes = Column(Text, nullable=True)

    # Link to related records (optional)
    related_invoice_id = Column(String(36), nullable=True)
    related_employee_id = Column(String(36), nullable=True)

    # Import tracking
    import_job_id = Column(String(36), ForeignKey("import_jobs.id", ondelete="SET NULL"), nullable=True, index=True)

    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
