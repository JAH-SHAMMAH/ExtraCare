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
  force_password_change?: boolean;
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

// FeeRecord is defined once, below, matching the real StudentFeeRecord backend shape
// (/finance/fee-records). An earlier phantom shape (amount/balance/fee_type for a
// never-built /school/fees API) was removed here to end the duplicate declaration.

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
  term: string | null;
  created_by: string;
  start_time: string | null;
  end_time: string | null;
  duration_minutes: number;
  total_points: number;
  shuffle_questions: boolean;
  max_attempts: number;
  pass_percentage: number | null;
  hold_results: boolean;
  results_published_at: string | null;
  published_pass_percentage: number | null;
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
  category_id: string | null;
  subcategory_id: string | null;
  description: string;
  points: number;
  incident_date: string;
  created_at: string;
  org_id: string;
}

export interface BehaviourCategory {
  id: string;
  name: string;
  type: BehaviourType;
  default_points: number | null;
  description: string | null;
  position: number;
  is_active: boolean;
  org_id: string;
  created_at: string;
}

export interface BehaviourSubCategory {
  id: string;
  category_id: string;
  name: string;
  default_points: number | null;
  position: number;
  is_active: boolean;
  org_id: string;
  created_at: string;
}

export interface BehaviourLevel {
  id: string;
  name: string;
  min_points: number;
  max_points: number | null;
  colour: string | null;
  description: string | null;
  position: number;
  is_active: boolean;
  org_id: string;
  created_at: string;
}

export interface BehaviourSettings {
  id: string;
  default_points: number;
  visible_to_students: boolean;
  visible_to_parents: boolean;
  auto_derive_levels: boolean;
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

export interface FeedbackSettings {
  id: string;
  allow_anonymous: boolean;
  notify_on_submit: boolean;
  acknowledgement_message: string | null;
  org_id: string;
}

export interface DailyReport {
  id: string;
  author_id: string;
  author_name: string | null;
  report_date: string;
  class_id: string | null;
  summary: string;
  highlights: string | null;
  challenges: string | null;
  created_at: string;
  org_id: string;
}

export interface StudentDailyReport {
  id: string;
  student_id: string;
  student_name: string | null;
  author_id: string;
  report_date: string;
  mood: string | null;
  academic: string | null;
  behaviour: string | null;
  notes: string | null;
  created_at: string;
  org_id: string;
}

// CRM: no dedicated type — the CRM page reuses AdmissionApplication (enquiry) data.

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

// ── People & HR (Batch 1) ──────────────────────────────────────────────────

export interface ParentSummary {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
}

export interface GuardedStudentSummary {
  id: string;
  student_id: string;
  full_name: string;
  class_name: string | null;
}

export type GuardianRelationship = "parent" | "guardian" | "other";

export interface ParentLink {
  id: string;
  relationship_type: GuardianRelationship | string;
  is_primary: boolean;
  parent: ParentSummary;
  student: GuardedStudentSummary;
  created_at: string;
  org_id: string;
}

export type AssessmentStatus = "draft" | "finalized";

export interface AssessmentCriterion {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  weight: number;
  max_score: number;
  position: number;
  is_active: boolean;
  org_id: string;
  created_at: string;
}

export interface AssessmentScore {
  criterion_id: string;
  criterion_name: string | null;
  category: string | null;
  score: number;
  max_score: number | null;
  weight: number | null;
  comment: string | null;
}

export interface StaffAssessment {
  id: string;
  staff_user_id: string;
  staff_name: string | null;
  reviewer_id: string | null;
  reviewer_name: string | null;
  period: string;
  review_date: string | null;
  overall_rating: number | null;
  strengths: string | null;
  improvements: string | null;
  goals: string | null;
  status: AssessmentStatus | string;
  scores: AssessmentScore[];
  created_at: string;
  updated_at: string;
  org_id: string;
}

export type TalentStage =
  | "applied" | "screening" | "interview" | "offer" | "hired" | "rejected";

export interface TalentCandidate {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  role_applied: string | null;
  source: string | null;
  stage: TalentStage | string;
  rating: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  org_id: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ── Admissions & Enrollment (Batch 2) ──────────────────────────────────────

export type AdmissionStatus =
  | "enquiry" | "applied" | "screening" | "offered" | "admitted" | "rejected" | "withdrawn";

export interface AdmissionApplication {
  id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  date_of_birth: string | null;
  gender: string | null;
  guardian_name: string | null;
  guardian_phone: string | null;
  guardian_email: string | null;
  applying_for_class_id: string | null;
  applying_for_class_name: string | null;
  applying_for_level: string | null;
  source: string | null;
  status: AdmissionStatus | string;
  notes: string | null;
  admitted_student_id: string | null;
  created_at: string;
  updated_at: string;
  org_id: string;
}

export type EntranceExamStatus = "scheduled" | "completed";
export type ExamOutcome = "pending" | "pass" | "fail";

export interface EntranceExam {
  id: string;
  title: string;
  exam_date: string | null;
  subject: string | null;
  max_score: number;
  status: EntranceExamStatus | string;
  notes: string | null;
  result_count: number;
  created_at: string;
  org_id: string;
}

export interface EntranceExamResult {
  id: string;
  exam_id: string;
  application_id: string | null;
  candidate_name: string;
  score: number | null;
  outcome: ExamOutcome | string;
  remark: string | null;
  created_at: string;
  org_id: string;
}

export type PromotionOutcome = "promoted" | "repeated" | "graduated";

export interface PromotionRecord {
  id: string;
  batch_id: string;
  student_id: string;
  student_name: string | null;
  from_class_id: string | null;
  from_class_name: string | null;
  to_class_id: string | null;
  to_class_name: string | null;
  academic_year: string | null;
  outcome: PromotionOutcome | string;
  reverted_at: string | null;
  created_at: string;
  org_id: string;
}

export interface PromotionPreviewItem {
  student_id: string;
  student_name: string | null;
  from_class_id: string | null;
  from_class_name: string | null;
  eligible: boolean;
  reason: string | null;
}

export interface PromotionPreview {
  outcome: string;
  to_class_id: string | null;
  to_class_name: string | null;
  eligible_count: number;
  skipped_count: number;
  items: PromotionPreviewItem[];
}

export type TransferType = "transfer_out" | "withdrawal";
export type TransferStatus = "pending" | "completed";

export interface TransferRecord {
  id: string;
  student_id: string;
  student_name: string | null;
  transfer_type: TransferType | string;
  destination_school: string | null;
  reason: string | null;
  transfer_date: string | null;
  status: TransferStatus | string;
  created_at: string;
  org_id: string;
}

// ── Academic Records & Recognition (Batch 3) ───────────────────────────────

export type SelectionStatus = "requested" | "approved" | "rejected";

export interface SubjectSelection {
  id: string;
  student_id: string;
  student_name: string | null;
  subject_id: string;
  subject_name: string | null;
  academic_year: string | null;
  term: string | null;
  status: SelectionStatus | string;
  created_at: string;
  org_id: string;
}

export interface TranscriptEntry {
  id: string;
  subject_name: string;
  score: number | null;
  grade: string | null;
  remark: string | null;
}

export type TranscriptStatus = "draft" | "issued";

export interface Transcript {
  id: string;
  student_id: string;
  student_name: string | null;
  academic_year: string | null;
  term: string | null;
  average: number | null;
  remark: string | null;
  status: TranscriptStatus | string;
  entries: TranscriptEntry[];
  created_at: string;
  org_id: string;
}

export type ReportStage = "draft" | "submitted" | "reviewed" | "approved" | "published";

export interface ReportApproval {
  id: string;
  class_id: string | null;
  class_name: string | null;
  academic_year: string | null;
  term: string | null;
  stage: ReportStage | string;
  notes: string | null;
  created_at: string;
  updated_at: string;
  org_id: string;
}

export type RecognitionType = "conduct_point" | "academic_award";
export type AwardType = "honor_roll" | "prize" | "certificate";

export interface Recognition {
  id: string;
  type: RecognitionType | string;
  student_id: string;
  student_name: string | null;
  title: string | null;
  reason: string | null;
  points: number | null;
  house: string | null;
  category: string | null;
  award_type: AwardType | string | null;
  term: string | null;
  awarded_on: string | null;
  created_at: string;
  org_id: string;
}

export interface HouseLeaderboardRow {
  house: string;
  total_points: number;
  entries: number;
}

// ── Pastoral, Boarding & Health (Batch 4) ──────────────────────────────────

export interface Hostel {
  id: string;
  name: string;
  gender: string | null;
  capacity: number | null;
  warden_id: string | null;
  warden_name: string | null;
  notes: string | null;
  occupancy: number;
  created_at: string;
  org_id: string;
}

export interface BoardingAllocation {
  id: string;
  student_id: string;
  student_name: string | null;
  hostel_id: string;
  hostel_name: string | null;
  room: string | null;
  bed: string | null;
  allocated_on: string | null;
  is_active: boolean;
  created_at: string;
  org_id: string;
}

export type ExeatStatus = "pending" | "approved" | "rejected" | "returned";

export interface ExeatRequest {
  id: string;
  student_id: string;
  student_name: string | null;
  reason: string | null;
  destination: string | null;
  depart_at: string | null;
  expected_return_at: string | null;
  actual_return_at: string | null;
  status: ExeatStatus | string;
  requested_by: string | null;
  approved_by: string | null;
  approved_by_name: string | null;
  decided_at: string | null;
  decision_note: string | null;
  created_at: string;
  org_id: string;
}

export interface MentorReport {
  id: string;
  student_id: string;
  student_name: string | null;
  mentor_id: string | null;
  mentor_name: string | null;
  term: string | null;
  period: string | null;
  summary: string | null;
  strengths: string | null;
  concerns: string | null;
  recommendations: string | null;
  created_at: string;
  org_id: string;
}

export type StudentMedicalRecordType = "visit" | "allergy" | "medication" | "immunization" | "condition" | "note";

export interface StudentMedicalRecord {
  id: string;
  student_id: string;
  student_name: string | null;
  record_type: StudentMedicalRecordType | string;
  title: string | null;
  description: string | null;
  treatment: string | null;
  severity: string | null;
  recorded_on: string | null;
  follow_up_on: string | null;
  recorded_by: string | null;
  created_at: string;
  org_id: string;
}

// ── Finance & Accounting (Batch 5) ─────────────────────────────────────────

export type AccountType = "asset" | "liability" | "equity" | "income" | "expense";

export interface LedgerAccount {
  id: string;
  code: string;
  name: string;
  type: AccountType | string;
  parent_id: string | null;
  description: string | null;
  is_active: boolean;
  created_at: string;
  org_id: string;
}

export interface AccountingPeriod {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  status: "open" | "locked" | string;
  locked_at: string | null;
  locked_by: string | null;
  created_at: string;
  org_id: string;
}

export interface JournalLine {
  id: string;
  account_id: string;
  account_code: string | null;
  account_name: string | null;
  debit: number;
  credit: number;
  description: string | null;
}

export interface JournalEntry {
  id: string;
  entry_date: string;
  memo: string | null;
  source: string;
  source_id: string | null;
  status: string;
  period_id: string | null;
  posted_by: string | null;
  posted_at: string | null;
  reversal_of_id: string | null;
  reversed_by_id: string | null;
  reversed_at: string | null;
  total: number;
  lines: JournalLine[];
  created_at: string;
  org_id: string;
}

export type InvoiceStatus = "draft" | "posted" | "paid" | "void";

export interface InvoiceLine {
  id: string;
  description: string;
  quantity: number;
  unit_price: number;
  amount: number;
  income_account_id: string;
  income_account_name: string | null;
}

// Named FinanceInvoice to avoid colliding with the legacy hospital/business
// `Invoice` type (different status model).
export interface FinanceInvoice {
  id: string;
  number: string;
  customer_name: string;
  student_id: string | null;
  invoice_date: string | null;
  due_date: string | null;
  status: InvoiceStatus | string;
  total: number;
  memo: string | null;
  receivable_account_id: string | null;
  journal_entry_id: string | null;
  payment_entry_id: string | null;
  created_by: string | null;
  posted_by: string | null;
  posted_at: string | null;
  lines: InvoiceLine[];
  created_at: string;
  org_id: string;
}

export type PayrollStatus = "draft" | "posted" | "void";

export interface Payslip {
  id: string;
  staff_user_id: string | null;
  staff_name: string | null;
  gross: number;
  deductions: number;
  net: number;
  notes: string | null;
}

export interface PayrollRun {
  id: string;
  period_label: string;
  run_date: string | null;
  status: PayrollStatus | string;
  total_gross: number;
  total_deductions: number;
  total_net: number;
  expense_account_id: string | null;
  net_account_id: string | null;
  deductions_account_id: string | null;
  journal_entry_id: string | null;
  created_by: string | null;
  approved_by: string | null;
  approved_at: string | null;
  payslips: Payslip[];
  created_at: string;
  org_id: string;
}

export interface SalaryAdvance {
  id: string;
  staff_user_id: string;
  staff_name: string | null;
  amount: number;
  reason: string | null;
  status: "pending" | "approved" | "rejected" | "repaid" | string;
  amount_repaid: number;
  outstanding: number;
  requested_by: string | null;
  approved_by: string | null;
  approved_at: string | null;
  disburse_entry_id: string | null;
  notes: string | null;
  created_at: string;
  org_id: string;
}

// ── Bonus / Reduction Pack (pay adjustments) ───────────────────────────────

export interface PayAdjustmentItem {
  id: string;
  staff_user_id: string | null;
  staff_name: string | null;
  amount: number;
  note: string | null;
}

export interface PayAdjustmentPack {
  id: string;
  label: string;
  kind: "bonus" | "reduction" | string;
  status: "draft" | "approved" | "void" | string;
  total_amount: number;
  reason: string | null;
  expense_account_id: string | null;
  settle_account_id: string | null;
  journal_entry_id: string | null;
  created_by: string | null;
  approved_by: string | null;
  approved_at: string | null;
  items: PayAdjustmentItem[];
  created_at: string;
  org_id: string;
}

// ── Requisitions / Request Form ────────────────────────────────────────────

export interface RequisitionItem {
  id: string;
  description: string;
  quantity: number;
  unit_cost: number;
  amount: number;
  note: string | null;
}

export interface Requisition {
  id: string;
  title: string;
  department: string | null;
  category: string | null;
  status: "draft" | "approved" | "rejected" | "void" | string;
  total_amount: number;
  justification: string | null;
  notes: string | null;
  expense_account_id: string | null;
  settle_account_id: string | null;
  journal_entry_id: string | null;
  requested_by: string | null;
  approved_by: string | null;
  approved_at: string | null;
  items: RequisitionItem[];
  created_at: string;
  org_id: string;
}

// ── Finance Reports (period income & expense) ──────────────────────────────

export interface ReportAccountRow {
  account_id: string;
  code: string;
  name: string;
  type: "income" | "expense" | string;
  amount: number;
}

export interface ReportSourceRow {
  source: string;
  income: number;
  expense: number;
}

export interface IncomeExpenseReport {
  start: string | null;
  end: string | null;
  income: number;
  expense: number;
  net: number;
  by_account: ReportAccountRow[];
  by_source: ReportSourceRow[];
}

// ── Fee Discounts (Manage Discounts) ───────────────────────────────────────

export interface FeeDiscount {
  id: string;
  student_id: string;
  student_name: string | null;
  fee_record_id: string | null;
  discount_type: "fixed" | "percent" | string;
  value: number;
  amount: number;
  reason: string | null;
  status: "draft" | "approved" | "rejected" | "void" | string;
  proposed_by: string | null;
  approved_by: string | null;
  approved_at: string | null;
  journal_entry_id: string | null;
  created_at: string;
  org_id: string;
}

// ── Fee Assignment (StudentFeeRecord) ──────────────────────────────────────

export interface FeeRecord {
  id: string;
  student_id: string;
  student_name: string | null;
  term: string;
  session_year: string;
  tuition_fee: number;
  exam_fee: number;
  activity_fee: number;
  transport_fee: number;
  hostel_fee: number;
  other_fees: number;
  total_fee: number;
  paid_amount: number;
  discount_amount: number;
  outstanding_balance: number;
  is_paid: boolean;
  payment_status: string;
  due_date: string | null;
  created_at: string;
  org_id: string;
}

export interface ClassFeeAssignResult {
  created: number;
  skipped: number;
  total_students: number;
  records: FeeRecord[];
}

export interface ClassOption {
  id: string;
  name: string;
  student_count: number;
}

// ── Bank Accounts (Account Numbers) ────────────────────────────────────────

export interface BankAccount {
  id: string;
  bank_name: string;
  account_name: string;
  account_number: string;
  bank_code: string | null;
  account_type: string | null;
  purpose: string | null;
  is_primary: boolean;
  is_active: boolean;
  notes: string | null;
  created_at: string;
  org_id: string;
}

export type GatewayProvider = "paystack" | "remita" | "flutterwave";

export interface PaymentGateway {
  id: string;
  provider: GatewayProvider;
  label: string | null;
  mode: "test" | "live";
  public_key: string | null;
  secret_key_set: boolean;       // never the plaintext — only whether it's set
  webhook_secret_set: boolean;
  merchant_id: string | null;        // Remita (non-secret)
  service_type_id: string | null;    // Remita (non-secret)
  is_active: boolean;
  created_at: string;
  org_id: string;
}

export interface BankAccountPublic {
  bank_name: string;
  account_name: string;
  account_number: string;
  bank_code: string | null;
  account_type: string | null;
  purpose: string | null;
}

// ── Accounts Setup (default posting accounts) ──────────────────────────────

export interface FinanceSettings {
  default_cash_account_id: string | null;
  default_cash_account_name: string | null;
  default_income_account_id: string | null;
  default_income_account_name: string | null;
  default_receivable_account_id: string | null;
  default_receivable_account_name: string | null;
  default_expense_account_id: string | null;
  default_expense_account_name: string | null;
  org_id: string;
}

// ── Financial Statements (derived from ledger) ─────────────────────────────

export interface TrialBalanceRow {
  account_id: string; code: string; name: string; type: string;
  debit: number; credit: number; balance: number;
}
export interface FinancialStatements {
  as_of: string | null;
  trial_balance: TrialBalanceRow[];
  total_debit: number; total_credit: number; balanced: boolean;
  income: number; expense: number; net_income: number;
  assets: number; liabilities: number; equity: number; balance_sheet_balanced: boolean;
}

// ── Finance ops (Batch 5, second half) ─────────────────────────────────────

export interface Budget {
  id: string;
  account_id: string;
  account_name: string | null;
  period_label: string | null;
  start_date: string | null;
  end_date: string | null;
  amount: number;
  spent: number;
  remaining: number;
  notes: string | null;
  created_at: string;
  org_id: string;
}

export interface PettyCashTxn {
  id: string;
  txn_date: string | null;
  description: string | null;
  amount: number;
  expense_account_id: string;
  expense_account_name: string | null;
  cash_account_id: string;
  category: string | null;
  status: string;
  journal_entry_id: string | null;
  warning: string | null;
  created_at: string;
  org_id: string;
}

export type CashTxnType = "receipt" | "payment";

export interface CashTransaction {
  id: string;
  txn_date: string | null;
  type: CashTxnType | string;
  amount: number;
  cash_account_id: string;
  cash_account_name: string | null;
  counter_account_id: string;
  counter_account_name: string | null;
  counterparty: string | null;
  description: string | null;
  status: string;
  journal_entry_id: string | null;
  created_at: string;
  org_id: string;
}

export interface StoreItem {
  id: string;
  name: string;
  sku: string | null;
  unit_price: number;
  cost_price: number;
  quantity: number;
  reorder_level: number;
  is_active: boolean;
  low_stock: boolean;
  created_at: string;
  org_id: string;
}

export interface StoreSaleLine {
  id: string;
  item_id: string | null;
  item_name: string | null;
  quantity: number;
  unit_price: number;
  amount: number;
}

export interface Warehouse {
  id: string;
  name: string;
  location: string | null;
  is_active: boolean;
  notes: string | null;
  item_count: number;
  total_units: number;
  created_at: string;
  org_id: string;
}

export interface WarehouseStockRow {
  item_id: string;
  item_name: string;
  sku: string | null;
  quantity: number;
  reorder_level: number;
  low_stock: boolean;
}

export interface PickupPoint {
  id: string;
  name: string;
  location: string | null;
  is_active: boolean;
  notes: string | null;
  pending_count: number;
  created_at: string;
  org_id: string;
}

export interface Pickup {
  id: string;
  pickup_point_id: string | null;
  pickup_point_name: string | null;
  student_id: string | null;
  customer_name: string | null;
  description: string;
  reference: string | null;
  status: "pending" | "collected" | "cancelled";
  collected_at: string | null;
  collected_by: string | null;
  notes: string | null;
  created_at: string;
  org_id: string;
}

export interface StoreSale {
  id: string;
  reference: string | null;
  customer_name: string | null;
  student_id: string | null;
  subtotal: number;
  discount: number;
  total: number;
  payment_method: string;
  status: "completed" | "void" | string;
  journal_entry_id: string | null;
  cashier_id: string | null;
  notes: string | null;
  lines: StoreSaleLine[];
  created_at: string;
  org_id: string;
}

export interface SalesTopItem {
  item_name: string;
  quantity: number;
  revenue: number;
}

export interface SalesGroup {
  key: string;
  label: string;
  count: number;
  revenue: number;
}

export interface StoreSalesSummary {
  start: string | null;
  end: string | null;
  total_sales: number;
  total_revenue: number;
  average_sale: number;
  top_items: SalesTopItem[];
  by_payment: SalesGroup[];
  by_cashier: SalesGroup[];
}

export interface StockMovement {
  id: string;
  item_id: string;
  type: string;
  quantity: number;
  unit_cost: number;
  note: string | null;
  journal_entry_id: string | null;
  created_at: string;
  org_id: string;
}

// ── Wallet / PocketMoney + Cooperative (Batch 6) ───────────────────────────

export interface StudentWallet {
  id: string;
  student_id: string;
  student_name: string | null;
  spend_limit_daily: number | null;
  is_active: boolean;
  balance: number;
  created_at: string;
  org_id: string;
}

export interface WalletEntry {
  id: string;
  kind: string;
  signed_amount: number;
  memo: string | null;
  journal_entry_id: string | null;
  reversed: boolean;
  created_at: string;
}

export interface WalletDetail extends StudentWallet {
  entries: WalletEntry[];
}

export interface CooperativeMember {
  id: string;
  member_name: string;
  member_user_id: string | null;
  is_active: boolean;
  joined_on: string | null;
  balance: number;
  created_at: string;
  org_id: string;
}

export interface CoopEntry {
  id: string;
  kind: string;
  signed_amount: number;
  memo: string | null;
  journal_entry_id: string | null;
  reversed: boolean;
  created_at: string;
}

export interface CoopMemberDetail extends CooperativeMember {
  entries: CoopEntry[];
}

export interface Reconciliation {
  control_account: string;
  gl_balance: number;
  subledger_total: number;
  balanced: boolean;
}

// ── Operations (Batch 6, non-financial) ────────────────────────────────────

export interface CalendarEvent {
  id: string;
  title: string;
  description: string | null;
  start_at: string;
  end_at: string | null;
  all_day: boolean;
  category: string | null;
  location: string | null;
  audience: string | null;
  created_at: string;
  org_id: string;
}

export interface Facility {
  id: string;
  name: string;
  type: string | null;
  capacity: number | null;
  location: string | null;
  status: string;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  org_id: string;
}

export interface FacilityBooking {
  id: string;
  facility_id: string;
  title: string;
  purpose: string | null;
  start_at: string;
  end_at: string;
  status: string;
  booked_by: string | null;
  created_at: string;
  org_id: string;
}

export interface VisitorLog {
  id: string;
  visitor_name: string;
  organization: string | null;
  purpose: string | null;
  host_name: string | null;
  phone: string | null;
  badge_no: string | null;
  sign_in_at: string | null;
  sign_out_at: string | null;
  status: string;
  recorded_by: string | null;
  created_at: string;
  org_id: string;
}

export interface StudentCollection {
  id: string;
  student_id: string;
  student_name: string | null;
  collector_name: string;
  relationship_to_student: string | null;
  authorized_by: string;
  authorized_by_name: string | null;
  collected_at: string | null;
  notes: string | null;
  recorded_by: string | null;
  created_at: string;
  org_id: string;
}

// ── Administration & Platform (Batch 7) ────────────────────────────────────

export interface BiometricDevice {
  id: string; device_id: string; name: string; location: string | null;
  is_active: boolean; last_seen_at: string | null; clock_skew_seconds: number | null;
  notes: string | null; created_at: string; org_id: string;
}
export interface BiometricEnrollment {
  id: string; biometric_user_id: string; student_id: string; student_name: string | null;
  label: string | null; created_at: string; org_id: string;
}
export interface UnmappedPunch {
  id: string; device_id: string | null; biometric_user_id: string | null;
  event_time: string | null; direction: string | null; reason: string; status: string;
  created_at: string; org_id: string;
}
export interface IngestSummary { ingested: number; duplicates: number; quarantined: number; }

export interface AcademicSession {
  id: string; name: string; term: string | null; start_date: string | null; end_date: string | null;
  is_current: boolean; created_at: string; org_id: string;
}
export interface AcademicWeek {
  id: string; academic_year: string; term: string; week_number: number;
  start_date: string; end_date: string; label: string | null;
  is_holiday: boolean; is_locked: boolean; created_at: string; org_id: string;
}
export interface SchoolHouse { id: string; name: string; color: string | null; motto: string | null; created_at: string; org_id: string; }
export interface GradingBand { id: string; grade: string; min_score: number; max_score: number; remark: string | null; created_at: string; org_id: string; }

export interface CustomFieldDef {
  id: string; entity_type: string; field_key: string; label: string; field_type: string;
  options: string[] | null; required: boolean; created_at: string; org_id: string;
}

export interface PollOptionResult { id: string; label: string; votes: number; }
export interface Poll {
  id: string; title: string; description: string | null; status: string; closes_at: string | null;
  total_votes: number; options: PollOptionResult[]; my_vote_option_id: string | null; created_at: string; org_id: string;
}

export interface MailboxMessage {
  id: string; subject: string; body: string | null; sender_id: string | null; audience: string | null;
  recipient_count: number; read_count: number; created_at: string; org_id: string;
}
export interface InboxItem {
  recipient_row_id: string; message_id: string; subject: string; body: string | null;
  sender_id: string | null; read_at: string | null; created_at: string;
}

export interface MobileDevice {
  id: string; user_id: string | null; push_token: string; platform: string | null; label: string | null;
  is_active: boolean; last_seen_at: string | null; created_at: string; org_id: string;
}
export interface AppConfigItem { id: string; key: string; value: string | null; description: string | null; org_id: string; }

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
