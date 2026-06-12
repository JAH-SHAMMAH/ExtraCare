from app.models.modules.school import (
    Student,
    SchoolClass,
    Subject,
    AttendanceRecord,
    AttendanceStatus,
    Grade,
    GradeStatus,
    Timetable,
    # School Experience Layer
    Assignment,
    AssignmentStatus,
    AssignmentSubmission,
    SubmissionStatus,
    WeeklyReflection,
    CBTExam,
    ExamStatus,
    CBTQuestion,
    QuestionType,
    CBTAttempt,
    AttemptStatus,
    CBTAnswer,
    BehaviourRecord,
    BehaviourType,
    StudentFeedback,
    FeedbackCategory,
    Club,
    ClubMembership,
    PhotoJournal,
    WeeklyRemark,
    TuckshopProduct,
    TuckshopPurchase,
    LibraryBook,
    LibraryLoan,
    LoanStatus,
    LessonPlan,
    LessonPlanStatus,
    ParentGuardian,
)
from app.models.modules.hospital import Patient, Appointment, MedicalRecord, MedicalInvoice
from app.models.modules.business import Employee, LeaveRequest, Payslip, InventoryItem
from app.models.modules.transport import (
    TransportVehicle, TransportDriver, TransportRoute, TransportStop,
    StudentRouteAssignment, TransportTrip, TripBoarding,
    VehicleStatus, TripDirection, TripStatus, BoardingStatus,
)

__all__ = [
    # School core
    "Student", "SchoolClass", "Subject", "AttendanceRecord", "AttendanceStatus",
    "Grade", "GradeStatus", "Timetable",
    # School experience
    "Assignment", "AssignmentStatus", "AssignmentSubmission", "SubmissionStatus",
    "WeeklyReflection",
    "CBTExam", "ExamStatus", "CBTQuestion", "QuestionType",
    "CBTAttempt", "AttemptStatus", "CBTAnswer",
    "BehaviourRecord", "BehaviourType",
    "StudentFeedback", "FeedbackCategory",
    "Club", "ClubMembership",
    "PhotoJournal", "WeeklyRemark",
    "TuckshopProduct", "TuckshopPurchase",
    "LibraryBook", "LibraryLoan", "LoanStatus",
    "LessonPlan", "LessonPlanStatus",
    "ParentGuardian",
    # Other modules
    "Patient", "Appointment", "MedicalRecord", "MedicalInvoice",
    "Employee", "LeaveRequest", "Payslip", "InventoryItem",
    # Transport (Phase 6.7)
    "TransportVehicle", "TransportDriver", "TransportRoute", "TransportStop",
    "StudentRouteAssignment", "TransportTrip", "TripBoarding",
    "VehicleStatus", "TripDirection", "TripStatus", "BoardingStatus",
]
