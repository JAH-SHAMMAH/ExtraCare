"""
Pydantic schemas for the School Experience Layer.

Every *Create schema omits org_id on purpose — it is pinned server-side from
the authenticated user's org, never from the client. Every *Response schema
includes id, org_id and timestamps so the frontend can render and mutate.
"""

from datetime import date, datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


# ── Common base ──────────────────────────────────────────────────────────────


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── eClassroom: assignments / submissions / reflections ──────────────────────


class AssignmentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    class_id: str
    subject_id: Optional[str] = None
    due_date: Optional[datetime] = None
    max_points: float = 100.0
    attachment_url: Optional[str] = None
    status: str = "published"


class AssignmentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    due_date: Optional[datetime] = None
    max_points: Optional[float] = None
    attachment_url: Optional[str] = None
    status: Optional[str] = None


class AssignmentResponse(_OrmBase):
    id: str
    title: str
    description: Optional[str]
    instructions: Optional[str]
    class_id: str
    subject_id: Optional[str]
    teacher_id: str
    due_date: Optional[datetime]
    max_points: float
    attachment_url: Optional[str]
    status: str
    created_at: datetime
    org_id: str


class SubmissionCreate(BaseModel):
    assignment_id: str
    student_id: str
    content: Optional[str] = None
    file_url: Optional[str] = None


class SubmissionGrade(BaseModel):
    score: float
    feedback: Optional[str] = None


class SubmissionResponse(_OrmBase):
    id: str
    assignment_id: str
    student_id: str
    content: Optional[str]
    file_url: Optional[str]
    submitted_at: Optional[datetime]
    score: Optional[float]
    feedback: Optional[str]
    graded_by: Optional[str]
    graded_at: Optional[datetime]
    status: str
    created_at: datetime
    org_id: str


class ReflectionCreate(BaseModel):
    student_id: str
    week_start: date
    content: str
    mood: Optional[str] = None


class ReflectionComment(BaseModel):
    teacher_comment: str


class ReflectionResponse(_OrmBase):
    id: str
    student_id: str
    week_start: date
    content: str
    mood: Optional[str]
    teacher_comment: Optional[str]
    commented_by: Optional[str]
    commented_at: Optional[datetime]
    created_at: datetime
    org_id: str


# ── CBT ──────────────────────────────────────────────────────────────────────


class ExamCreate(BaseModel):
    title: str
    description: Optional[str] = None
    class_id: Optional[str] = None
    subject_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: int = 60
    shuffle_questions: bool = False
    max_attempts: int = Field(default=1, ge=0)  # 0 = unlimited
    pass_percentage: Optional[int] = Field(default=None, ge=0, le=100)  # None = org default
    status: str = "draft"


class ExamUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    shuffle_questions: Optional[bool] = None
    max_attempts: Optional[int] = Field(default=None, ge=0)
    pass_percentage: Optional[int] = Field(default=None, ge=0, le=100)
    status: Optional[str] = None


class ExamResponse(_OrmBase):
    id: str
    title: str
    description: Optional[str]
    class_id: Optional[str]
    subject_id: Optional[str]
    created_by: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    duration_minutes: int
    total_points: float
    shuffle_questions: bool
    max_attempts: int
    pass_percentage: Optional[int]
    status: str
    created_at: datetime
    org_id: str


class QuestionCreate(BaseModel):
    question_text: str
    question_type: str = "mcq"
    options: Optional[list[dict[str, Any]]] = None
    correct_answer: Optional[str] = None
    points: float = 1.0
    position: int = 0


class QuestionResponse(_OrmBase):
    id: str
    exam_id: str
    question_text: str
    question_type: str
    options: Optional[list[dict[str, Any]]]
    # Correct answer is deliberately excluded from the student-facing list
    # endpoint; teachers get a separate endpoint that includes it.
    points: float
    position: int


class QuestionWithAnswer(QuestionResponse):
    correct_answer: Optional[str]


class AttemptAnswerInput(BaseModel):
    question_id: str
    answer_text: str


class AttemptSubmit(BaseModel):
    answers: list[AttemptAnswerInput]


class RemarkItem(BaseModel):
    """Manual grade override for one answer (Test Remark) — e.g. a subjective
    short/long-answer the auto-grader left ungraded."""
    answer_id: str
    points_awarded: float = Field(ge=0)


class AttemptResponse(_OrmBase):
    id: str
    exam_id: str
    student_id: str
    started_at: Optional[datetime]
    submitted_at: Optional[datetime]
    score: Optional[float]
    max_score: Optional[float]
    status: str
    submitted_late: bool = False
    superseded_at: Optional[datetime] = None
    # Absolute UTC instant this attempt must be submitted by (started_at +
    # duration, capped by the exam window). Computed server-side; None if the
    # exam has no duration. Clients run their countdown against this.
    deadline: Optional[datetime] = None
    created_at: datetime
    org_id: str


# ── Behaviour / Pastoral ─────────────────────────────────────────────────────


class BehaviourCreate(BaseModel):
    student_id: str
    type: str = "positive"
    category: Optional[str] = None
    description: str
    points: int = 0
    incident_date: date


class BehaviourResponse(_OrmBase):
    id: str
    student_id: str
    recorded_by: str
    type: str
    category: Optional[str]
    description: str
    points: int
    incident_date: date
    created_at: datetime
    org_id: str


# ── Feedback ─────────────────────────────────────────────────────────────────


class FeedbackCreate(BaseModel):
    subject: str
    message: str
    category: str = "general"
    is_anonymous: bool = False
    student_id: Optional[str] = None


class FeedbackResolve(BaseModel):
    admin_response: str
    is_resolved: bool = True


class FeedbackResponse(_OrmBase):
    id: str
    submitted_by: str
    student_id: Optional[str]
    subject: str
    message: str
    category: str
    is_anonymous: bool
    is_resolved: bool
    admin_response: Optional[str]
    responded_by: Optional[str]
    responded_at: Optional[datetime]
    created_at: datetime
    org_id: str


# ── Clubs ────────────────────────────────────────────────────────────────────


class ClubCreate(BaseModel):
    name: str
    description: Optional[str] = None
    advisor_id: Optional[str] = None
    meeting_day: Optional[str] = None
    meeting_time: Optional[str] = None
    location: Optional[str] = None
    max_members: Optional[int] = None
    cover_url: Optional[str] = None


class ClubUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    advisor_id: Optional[str] = None
    meeting_day: Optional[str] = None
    meeting_time: Optional[str] = None
    location: Optional[str] = None
    max_members: Optional[int] = None
    cover_url: Optional[str] = None
    is_active: Optional[bool] = None


class ClubResponse(_OrmBase):
    id: str
    name: str
    description: Optional[str]
    advisor_id: Optional[str]
    meeting_day: Optional[str]
    meeting_time: Optional[str]
    location: Optional[str]
    max_members: Optional[int]
    cover_url: Optional[str]
    is_active: bool
    created_at: datetime
    org_id: str


class ClubJoin(BaseModel):
    student_id: str
    role: str = "member"


class ClubMembershipResponse(_OrmBase):
    id: str
    club_id: str
    student_id: str
    joined_at: datetime
    role: str
    is_active: bool


# ── Journals & Remarks ───────────────────────────────────────────────────────


class JournalCreate(BaseModel):
    title: str
    description: Optional[str] = None
    photo_url: str
    taken_date: Optional[date] = None
    class_id: Optional[str] = None
    club_id: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class JournalResponse(_OrmBase):
    id: str
    title: str
    description: Optional[str]
    photo_url: str
    taken_date: Optional[date]
    posted_by: str
    class_id: Optional[str]
    club_id: Optional[str]
    tags: list[str]
    created_at: datetime
    org_id: str


class RemarkCreate(BaseModel):
    student_id: str
    week_start: date
    remark: str
    strengths: Optional[str] = None
    areas_to_improve: Optional[str] = None


class RemarkResponse(_OrmBase):
    id: str
    student_id: str
    teacher_id: str
    week_start: date
    remark: str
    strengths: Optional[str]
    areas_to_improve: Optional[str]
    created_at: datetime
    org_id: str


# ── Tuckshop ─────────────────────────────────────────────────────────────────


class TuckshopProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    stock: int = 0
    image_url: Optional[str] = None
    category: Optional[str] = None
    is_active: bool = True


class TuckshopProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    image_url: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


class TuckshopProductResponse(_OrmBase):
    id: str
    name: str
    description: Optional[str]
    price: float
    stock: int
    image_url: Optional[str]
    category: Optional[str]
    is_active: bool
    created_at: datetime
    org_id: str


class TuckshopPurchaseCreate(BaseModel):
    student_id: str
    product_id: str
    quantity: int = 1


class TuckshopPurchaseResponse(_OrmBase):
    id: str
    student_id: str
    product_id: str
    quantity: int
    unit_price: float
    total_price: float
    sold_by: Optional[str]
    created_at: datetime
    org_id: str
