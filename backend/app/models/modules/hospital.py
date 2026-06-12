from sqlalchemy import Column, String, Integer, Float, Date, DateTime, Text, Boolean, Enum, ForeignKey, JSON, Time
from sqlalchemy.orm import relationship
from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin
import enum


class BloodType(str, enum.Enum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"
    UNKNOWN = "unknown"


class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class Patient(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "patients"

    patient_id = Column(String(50), nullable=False, index=True)  # e.g. "PAT-00123"
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(320), nullable=True)
    phone = Column(String(50), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True)
    photo_url = Column(String(500), nullable=True)
    address = Column(Text, nullable=True)
    national_id = Column(String(50), nullable=True)

    # Medical
    blood_type = Column(Enum(BloodType), default=BloodType.UNKNOWN)
    allergies = Column(JSON, default=list)       # ["Penicillin", "Peanuts"]
    chronic_conditions = Column(JSON, default=list)
    emergency_contact_name = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(50), nullable=True)

    # Insurance
    insurance_provider = Column(String(255), nullable=True)
    insurance_policy_no = Column(String(100), nullable=True)

    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    appointments = relationship("Appointment", back_populates="patient")
    medical_records = relationship("MedicalRecord", back_populates="patient")
    invoices = relationship("MedicalInvoice", back_populates="patient")


class Appointment(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "appointments"

    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    appointment_date = Column(Date, nullable=False, index=True)
    start_time = Column(String(10), nullable=False)  # "09:00"
    end_time = Column(String(10), nullable=False)
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.SCHEDULED)
    reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    room = Column(String(50), nullable=True)
    reminder_sent = Column(Boolean, default=False)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("User", foreign_keys=[doctor_id])


class MedicalRecord(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """EMR-lite: visit notes, diagnoses, prescriptions."""
    __tablename__ = "medical_records"

    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    appointment_id = Column(String(36), ForeignKey("appointments.id"), nullable=True)
    doctor_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    visit_date = Column(Date, nullable=False)

    chief_complaint = Column(Text, nullable=True)
    diagnosis = Column(Text, nullable=True)
    icd_codes = Column(JSON, default=list)     # ["J00", "Z00.00"]
    treatment_plan = Column(Text, nullable=True)
    prescriptions = Column(JSON, default=list) # [{"drug": "Amoxicillin", "dosage": "500mg", "duration": "7 days"}]
    lab_results = Column(JSON, default=list)
    vitals = Column(JSON, default=dict)        # {"bp": "120/80", "temp": "36.5", "weight": "70kg"}
    follow_up_date = Column(Date, nullable=True)
    is_confidential = Column(Boolean, default=False)

    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    patient = relationship("Patient", back_populates="medical_records")


class MedicalInvoice(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "medical_invoices"

    invoice_number = Column(String(50), nullable=False, index=True)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    appointment_id = Column(String(36), ForeignKey("appointments.id"), nullable=True)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT)
    items = Column(JSON, default=list)  # [{"description": "Consultation", "qty": 1, "unit_price": 5000}]
    subtotal = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    currency = Column(String(10), default="NGN")
    due_date = Column(Date, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    payment_method = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)

    patient = relationship("Patient", back_populates="invoices")
