// ── Auth ──────────────────────────────────────────────────────────────────────

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  status: UserStatus;
  org_id: string;
  primary_role: string;
  permissions: string[];
  mfa_enabled: boolean;
  org?: Organization | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

// ── Users ─────────────────────────────────────────────────────────────────────

export type UserStatus = "active" | "inactive" | "suspended" | "pending" | "locked";

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  department: string | null;
  job_title: string | null;
  avatar_url: string | null;
  status: UserStatus;
  email_verified: boolean;
  mfa_enabled: boolean;
  last_login_at: string | null;
  last_login_ip: string | null;
  created_at: string;
  org_id: string;
  roles: Role[];
}

export interface Role {
  id: string;
  name: string;
  slug: string;
  color: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ── Organization ──────────────────────────────────────────────────────────────

export type IndustryType = "school" | "hospital" | "business" | "hybrid";
export type SubscriptionTier = "free" | "pro" | "starter" | "growth" | "enterprise";

export interface Organization {
  id: string;
  name: string;
  slug: string;
  industry: IndustryType;
  subscription_tier: SubscriptionTier;
  logo_url: string | null;
  primary_color: string;
  modules_enabled: string[];
  modules_configured?: string[];
  workspace?: {
    type: IndustryType;
    label: string;
    dashboard_type: string;
    modules: string[];
    features: string[];
  };
  max_users: number;
  is_active: boolean;
}

// ── Analytics ─────────────────────────────────────────────────────────────────

export interface OverviewStats {
  users: { total: number; active: number; online_today: number };
  school: { total_students: number; attendance_today: number };
  hospital: { total_patients: number; appointments_today: number };
  period: { start: string; end: string };
}

export interface ActivityLog {
  id: string;
  action: string;
  resource_type: string | null;
  resource_label: string | null;
  actor_email: string | null;
  severity: string;
  created_at: string;
}

// ── School ────────────────────────────────────────────────────────────────────

export interface Student {
  id: string;
  student_id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  date_of_birth: string | null;
  gender: "male" | "female" | "other";
  class_id: string | null;
  class_name: string | null;
  guardian_name: string | null;
  guardian_phone: string | null;
  address: string | null;
  avatar_url: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Teacher {
  id: string;
  teacher_id: string;
  user_id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  department: string | null;
  subjects: string[];
  qualification: string | null;
  hire_date: string | null;
  is_active: boolean;
  avatar_url: string | null;
  created_at: string;
}

export interface SchoolClass {
  id: string;
  name: string;
  grade_level: string | null;
  section: string | null;
  class_teacher_id: string | null;
  class_teacher_name: string | null;
  capacity: number;
  student_count: number;
  academic_year: string;
  is_active: boolean;
  created_at: string;
}

export interface Subject {
  id: string;
  name: string;
  code: string;
  department: string | null;
  class_ids: string[];
  teacher_id: string | null;
  teacher_name: string | null;
  credit_hours: number;
  is_active: boolean;
  created_at: string;
}

export interface Exam {
  id: string;
  name: string;
  exam_type: "midterm" | "final" | "quiz" | "assignment" | "practical";
  subject_id: string;
  subject_name: string | null;
  class_id: string;
  class_name: string | null;
  date: string;
  start_time: string | null;
  end_time: string | null;
  total_marks: number;
  pass_marks: number;
  status: "scheduled" | "in_progress" | "completed" | "cancelled";
  created_at: string;
}

export interface ExamResult {
  id: string;
  exam_id: string;
  student_id: string;
  student_name: string | null;
  marks_obtained: number;
  total_marks: number;
  grade: string | null;
  remarks: string | null;
}

export interface FeeRecord {
  id: string;
  student_id: string;
  student_name: string | null;
  fee_type: "tuition" | "admission" | "exam" | "transport" | "hostel" | "other";
  amount: number;
  paid_amount: number;
  balance: number;
  due_date: string;
  status: "paid" | "partial" | "unpaid" | "overdue";
  payment_date: string | null;
  payment_method: string | null;
  term: string;
  academic_year: string;
  created_at: string;
}

export interface AttendanceRecord {
  id: string;
  student_id: string;
  student_name: string | null;
  class_id: string;
  date: string;
  status: "present" | "absent" | "late" | "excused";
  remarks: string | null;
}

export interface TeacherRating {
  id: string;
  teacher_id: string;
  student_id: string;
  student_name: string | null;
  rating: number;
  comment: string | null;
  subject_id: string | null;
  term: string;
  created_at: string;
}

export interface TimetableSlot {
  id: string;
  class_id: string;
  subject_id: string;
  subject_name: string | null;
  teacher_id: string;
  teacher_name: string | null;
  day: "monday" | "tuesday" | "wednesday" | "thursday" | "friday";
  period: number;
  start_time: string;
  end_time: string;
}

// ── School Experience Layer ───────────────────────────────────────────────────

export type AssignmentStatus = "draft" | "published" | "closed";

export interface Assignment {
  id: string;
  title: string;
  description: string | null;
  instructions: string | null;
  class_id: string;
  subject_id: string | null;
  teacher_id: string;
  due_date: string | null;
  max_points: number;
  attachment_url: string | null;
  status: AssignmentStatus;
  created_at: string;
  org_id: string;
}

export type SubmissionStatus = "submitted" | "graded" | "returned";

export interface AssignmentSubmission {
  id: string;
  assignment_id: string;
  student_id: string;
  content: string | null;
  file_url: string | null;
  submitted_at: string | null;
  score: number | null;
  feedback: string | null;
  graded_by: string | null;
  graded_at: string | null;
  status: SubmissionStatus;
  created_at: string;
  org_id: string;
}

export interface WeeklyReflection {
  id: string;
  student_id: string;
  week_start: string;
  content: string;
  mood: string | null;
  teacher_comment: string | null;
  commented_by: string | null;
  commented_at: string | null;
  created_at: string;
  org_id: string;
}

export type CBTExamStatus = "draft" | "published" | "active" | "closed";
export type CBTQuestionType = "mcq" | "true_false" | "short_answer" | "long_answer";
export type CBTAttemptStatus = "in_progress" | "submitted" | "graded";

export interface CBTExam {
  id: string;
  title: string;
  description: string | null;
  class_id: string | null;
  subject_id: string | null;
  created_by: string;
  start_time: string | null;
  end_time: string | null;
  duration_minutes: number;
  total_points: number;
  shuffle_questions: boolean;
  status: CBTExamStatus;
  created_at: string;
  org_id: string;
}

export interface CBTQuestion {
  id: string;
  exam_id: string;
  question_text: string;
  question_type: CBTQuestionType;
  options: Array<{ key: string; text: string }> | null;
  correct_answer?: string | null;
  points: number;
  position: number;
}

export interface CBTAttempt {
  id: string;
  exam_id: string;
  student_id: string;
  started_at: string | null;
  submitted_at: string | null;
  score: number | null;
  max_score: number | null;
  status: CBTAttemptStatus;
  created_at: string;
  org_id: string;
  answers?: Array<{
    id: string;
    question_id: string;
    answer_text: string | null;
    is_correct: boolean | null;
    points_awarded: number | null;
  }>;
}

export type BehaviourType = "positive" | "negative" | "neutral";

export interface BehaviourRecord {
  id: string;
  student_id: string;
  recorded_by: string;
  type: BehaviourType;
  category: string | null;
  description: string;
  points: number;
  incident_date: string;
  created_at: string;
  org_id: string;
}

export type FeedbackCategory = "general" | "facilities" | "teaching" | "bullying" | "suggestion" | "other";

export interface FeedbackItem {
  id: string;
  submitted_by: string | null;
  student_id: string | null;
  subject: string;
  message: string;
  category: FeedbackCategory;
  is_anonymous: boolean;
  is_resolved: boolean;
  admin_response: string | null;
  responded_by: string | null;
  responded_at: string | null;
  created_at: string;
  org_id: string;
}

export interface Club {
  id: string;
  name: string;
  description: string | null;
  advisor_id: string | null;
  meeting_day: string | null;
  meeting_time: string | null;
  location: string | null;
  max_members: number | null;
  cover_url: string | null;
  is_active: boolean;
  member_count?: number;
  created_at: string;
  org_id: string;
}

export interface ClubMembership {
  id: string;
  club_id: string;
  student_id: string;
  joined_at: string;
  role: string;
  is_active: boolean;
}

export interface PhotoJournal {
  id: string;
  title: string;
  description: string | null;
  photo_url: string;
  taken_date: string | null;
  posted_by: string;
  class_id: string | null;
  club_id: string | null;
  tags: string[];
  created_at: string;
  org_id: string;
}

export interface WeeklyRemark {
  id: string;
  student_id: string;
  teacher_id: string;
  week_start: string;
  remark: string;
  strengths: string | null;
  areas_to_improve: string | null;
  created_at: string;
  org_id: string;
}

export interface TuckshopProduct {
  id: string;
  name: string;
  description: string | null;
  price: number;
  stock: number;
  image_url: string | null;
  category: string | null;
  is_active: boolean;
  created_at: string;
  org_id: string;
}

export interface TuckshopPurchase {
  id: string;
  student_id: string;
  product_id: string;
  quantity: number;
  unit_price: number;
  total_price: number;
  sold_by: string | null;
  created_at: string;
  org_id: string;
}

export interface StudentAttendanceHistory {
  student_id: string;
  records: Array<{
    id: string;
    date: string;
    status: "present" | "absent" | "late" | "excused";
    class_id: string;
    notes: string | null;
  }>;
  summary: {
    present: number;
    absent: number;
    late: number;
    excused: number;
    total: number;
    attendance_rate: number;
  };
}

export interface ReportCard {
  student: Student;
  term: string;
  academic_year: string;
  subjects: Array<{
    subject_name: string;
    score: number;
    grade: string;
    remarks: string | null;
    teacher_name: string | null;
  }>;
  total_score: number;
  average: number;
  position: number | null;
  class_size: number | null;
  teacher_remark: string | null;
  principal_remark: string | null;
}

// ── Hospital ──────────────────────────────────────────────────────────────────

export interface Patient {
  id: string;
  patient_id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  date_of_birth: string | null;
  gender: "male" | "female" | "other";
  blood_type: string | null;
  address: string | null;
  emergency_contact: string | null;
  insurance_id: string | null;
  avatar_url: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Doctor {
  id: string;
  doctor_id: string;
  user_id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  specialization: string;
  department: string | null;
  qualification: string | null;
  license_number: string | null;
  consultation_fee: number;
  is_available: boolean;
  avatar_url: string | null;
  created_at: string;
}

export interface Appointment {
  id: string;
  patient_id: string;
  patient_name: string | null;
  doctor_id: string;
  doctor_name: string | null;
  appointment_date: string;
  start_time: string;
  end_time: string;
  status: "scheduled" | "confirmed" | "in_progress" | "completed" | "cancelled" | "no_show";
  reason: string | null;
  notes: string | null;
  created_at: string;
}

export interface MedicalRecord {
  id: string;
  patient_id: string;
  doctor_id: string;
  doctor_name: string | null;
  record_type: "consultation" | "lab_result" | "prescription" | "surgery" | "follow_up";
  diagnosis: string | null;
  symptoms: string | null;
  notes: string | null;
  attachments: string[];
  created_at: string;
}

export interface Prescription {
  id: string;
  patient_id: string;
  doctor_id: string;
  doctor_name: string | null;
  record_id: string | null;
  medications: Array<{
    drug_name: string;
    dosage: string;
    frequency: string;
    duration: string;
    notes: string | null;
  }>;
  status: "active" | "completed" | "cancelled";
  created_at: string;
}

export interface LabResult {
  id: string;
  patient_id: string;
  patient_name: string | null;
  doctor_id: string;
  test_name: string;
  test_type: string;
  result: string | null;
  normal_range: string | null;
  status: "pending" | "in_progress" | "completed";
  ordered_at: string;
  completed_at: string | null;
  notes: string | null;
}

export interface PharmacyItem {
  id: string;
  drug_name: string;
  generic_name: string | null;
  category: string;
  quantity_in_stock: number;
  unit_price: number;
  supplier: string | null;
  batch_number: string | null;
  expiry_date: string | null;
  reorder_level: number;
  is_low_stock: boolean;
  is_expired: boolean;
  created_at: string;
}

export interface Ward {
  id: string;
  name: string;
  ward_type: "general" | "private" | "icu" | "emergency" | "maternity" | "pediatric";
  total_beds: number;
  occupied_beds: number;
  available_beds: number;
  floor: string | null;
  is_active: boolean;
}

export interface BedAssignment {
  id: string;
  ward_id: string;
  ward_name: string;
  bed_number: string;
  patient_id: string | null;
  patient_name: string | null;
  admitted_at: string | null;
  discharged_at: string | null;
  status: "available" | "occupied" | "reserved" | "maintenance";
}

export interface VitalSign {
  id: string;
  patient_id: string;
  patient_name: string | null;
  recorded_by: string;
  temperature: number | null;
  blood_pressure_systolic: number | null;
  blood_pressure_diastolic: number | null;
  heart_rate: number | null;
  respiratory_rate: number | null;
  oxygen_saturation: number | null;
  weight: number | null;
  notes: string | null;
  recorded_at: string;
}

export interface HospitalBill {
  id: string;
  patient_id: string;
  patient_name: string | null;
  items: Array<{
    description: string;
    quantity: number;
    unit_price: number;
    total: number;
  }>;
  subtotal: number;
  tax: number;
  discount: number;
  total: number;
  paid_amount: number;
  balance: number;
  status: "draft" | "sent" | "paid" | "partial" | "overdue" | "cancelled";
  insurance_claim_id: string | null;
  due_date: string;
  created_at: string;
}

// ── Business ──────────────────────────────────────────────────────────────────

export interface Employee {
  id: string;
  user_id: string;
  employee_code: string | null;
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  department: string | null;
  designation: string | null;
  employment_type: "full_time" | "part_time" | "contract" | "intern";
  hire_date: string | null;
  salary: number | null;
  avatar_url: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Department {
  id: string;
  name: string;
  code: string;
  head_id: string | null;
  head_name: string | null;
  employee_count: number;
  budget: number | null;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

export interface LeaveRequest {
  id: string;
  employee_id: string;
  employee_name: string | null;
  leave_type: "annual" | "sick" | "maternity" | "paternity" | "unpaid" | "compassionate";
  start_date: string;
  end_date: string;
  days: number;
  reason: string;
  status: "pending" | "approved" | "rejected" | "cancelled";
  reviewed_by: string | null;
  review_notes: string | null;
  created_at: string;
}

export interface PayrollRecord {
  id: string;
  employee_id: string;
  employee_name: string | null;
  pay_period_start: string;
  pay_period_end: string;
  basic_salary: number;
  allowances: number;
  deductions: number;
  tax: number;
  net_pay: number;
  status: "draft" | "processed" | "paid";
  payment_date: string | null;
  created_at: string;
}

export interface InventoryItem {
  id: string;
  sku: string;
  name: string;
  category: string | null;
  description: string | null;
  quantity_in_stock: number;
  unit_cost: number;
  selling_price: number;
  supplier: string | null;
  is_low_stock: boolean;
  reorder_level: number;
  last_restocked: string | null;
  created_at: string;
}

export interface Invoice {
  id: string;
  invoice_number: string;
  client_name: string;
  client_email: string | null;
  items: Array<{
    description: string;
    quantity: number;
    unit_price: number;
    total: number;
  }>;
  subtotal: number;
  tax: number;
  discount: number;
  total: number;
  paid_amount: number;
  balance: number;
  status: "draft" | "sent" | "paid" | "partial" | "overdue" | "cancelled";
  due_date: string;
  issued_date: string;
  created_at: string;
}

export interface CRMContact {
  id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  company: string | null;
  position: string | null;
  lead_source: "website" | "referral" | "social_media" | "cold_call" | "event" | "other";
  status: "lead" | "prospect" | "customer" | "churned";
  notes: string | null;
  assigned_to: string | null;
  last_contact_at: string | null;
  created_at: string;
}

export interface SalesDeal {
  id: string;
  title: string;
  contact_id: string;
  contact_name: string | null;
  value: number;
  stage: "discovery" | "proposal" | "negotiation" | "closed_won" | "closed_lost";
  probability: number;
  expected_close_date: string | null;
  assigned_to: string | null;
  notes: string | null;
  created_at: string;
}

export interface ProcurementOrder {
  id: string;
  order_number: string;
  supplier_name: string;
  supplier_email: string | null;
  items: Array<{
    description: string;
    quantity: number;
    unit_price: number;
    total: number;
  }>;
  total: number;
  status: "draft" | "submitted" | "approved" | "ordered" | "received" | "cancelled";
  expected_delivery: string | null;
  notes: string | null;
  created_by: string | null;
  created_at: string;
}

// ── HR ───────────────────────────────────────────────────────────────────────

export interface HRMembership {
  body?: string;
  membership_number?: string;
  expires_at?: string | null;
}

export interface HRNextOfKin {
  name?: string;
  relationship?: string;
  phone?: string;
  email?: string;
}

export interface HRDependent {
  name?: string;
  relationship?: string;
  date_of_birth?: string | null;
}

export interface HRProfile {
  id: string;
  user_id: string;
  org_id: string;
  email: string | null;
  full_name: string | null;
  phone: string | null;
  department: string | null;
  job_title: string | null;
  title: string | null;
  first_name: string | null;
  middle_name: string | null;
  surname: string | null;
  staff_id: string | null;
  employment_status: string | null;
  gender: string | null;
  marital_status: string | null;
  nationality: string | null;
  date_of_birth: string | null;
  national_id: string | null;
  national_id_expiry: string | null;
  address: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  emergency_contact_relationship: string | null;
  hire_date: string | null;
  salary: number | null;
  salary_currency: string | null;
  bank_name: string | null;
  bank_account_name: string | null;
  bank_account_number: string | null;
  pension_provider: string | null;
  pension_id: string | null;
  memberships: HRMembership[];
  next_of_kin: HRNextOfKin;
  dependents: HRDependent[];
  created_at: string | null;
  updated_at: string | null;
}

export interface HRBirthday {
  name: string;
  role: "staff" | "student";
  date_of_birth: string;
  is_today: boolean;
  days_until: number;
}

export interface HREvent {
  id: string;
  title: string;
  description: string | null;
  starts_at: string;
  ends_at: string | null;
  location: string | null;
  category: string | null;
  created_by: string | null;
  created_at: string | null;
}

export interface HROverview {
  total_active_staff: number;
  total_profiles: number;
  staff_per_department: Array<{ department: string; count: number }>;
  gender_distribution: Array<{ label: string; count: number }>;
  age_distribution: Array<{ label: string; count: number }>;
}

// ── Leave ────────────────────────────────────────────────────────────────────

export type LeaveType =
  | "annual" | "casual" | "sick" | "maternity"
  | "paternity" | "bereavement" | "unpaid" | "other";

export type LeaveStatus = "pending" | "approved" | "rejected";

export interface LeaveApplication {
  id: string;
  user_id: string;
  org_id: string;
  applicant_name: string | null;
  applicant_email: string | null;
  leave_type: LeaveType;
  start_date: string;
  end_date: string;
  days: number;
  reason: string | null;
  status: LeaveStatus;
  approver_id: string | null;
  approver_name: string | null;
  decided_at: string | null;
  decision_note: string | null;
  created_at: string | null;
}

export interface LeaveAnalytics {
  total: number;
  pending_count: number;
  by_status: Array<{ status: LeaveStatus; count: number }>;
  by_month: Array<{ month: string; count: number }>;
  by_type: Array<{ leave_type: LeaveType; count: number }>;
}

// ── Messenger ─────────────────────────────────────────────────────────────

export type ConversationKind = "global" | "direct" | "group";
export type MessageType = "text" | "image" | "video";

export interface MessengerMember {
  id: string;
  full_name: string;
  email: string | null;
  avatar_url: string | null;
}

export interface Conversation {
  id: string;
  org_id: string;
  kind: ConversationKind;
  title: string | null;
  members: MessengerMember[];
  last_message_at: string | null;
  last_message_preview: string | null;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  org_id: string;
  sender_id: string;
  sender_name: string | null;
  sender_avatar_url: string | null;
  type: MessageType;
  content: string | null;
  file_url: string | null;
  created_at: string;
}

export interface UploadResponse {
  file_url: string;
  type: MessageType;
  size_bytes: number;
  filename: string;
}

// ── News Feed ─────────────────────────────────────────────────────────────

export type FeedMediaType = "image" | "video";

export interface FeedPost {
  id: string;
  org_id: string;
  user_id: string;
  author_name: string | null;
  author_avatar_url: string | null;
  content: string | null;
  media_url: string | null;
  media_type: FeedMediaType | null;
  like_count: number;
  comment_count: number;
  liked_by_me: boolean;
  created_at: string;
}

export interface FeedComment {
  id: string;
  post_id: string;
  user_id: string;
  author_name: string | null;
  author_avatar_url: string | null;
  content: string;
  created_at: string;
}

export interface FeedLikeToggle {
  liked: boolean;
  like_count: number;
}

// ── Livestream ────────────────────────────────────────────────────────────

export interface LiveSession {
  id: string;
  org_id: string;
  host_user_id: string;
  host_name: string | null;
  title: string;
  description: string | null;
  class_id: string | null;
  subject_id: string | null;
  timetable_id: string | null;
  is_active: boolean;
  started_at: string;
  ended_at: string | null;
  viewer_count: number;
  has_recording: boolean;
  created_at: string;
}

export interface TimetableSlot {
  timetable_id: string;
  class_id: string;
  class_name: string | null;
  subject_id: string | null;
  subject_name: string | null;
  day_of_week: number;
  start_time: string;
  end_time: string;
  is_current: boolean;
  live_session_id: string | null;
  can_host: boolean;
}

export interface LiveRecording {
  id: string;
  session_id: string;
  file_url: string;
  file_size: number;
  duration_seconds: number | null;
  mime_type: string | null;
  created_at: string;
}

export interface LiveAttendee {
  user_id: string;
  user_name: string | null;
  joined_at: string;
  left_at: string | null;
  duration_seconds: number | null;
}

export interface LiveAnalytics {
  session_id: string;
  total_joins: number;
  unique_viewers: number;
  current_viewer_count: number;
  peak_viewer_count: number;
  average_watch_seconds: number | null;
  attendees: LiveAttendee[];
}
