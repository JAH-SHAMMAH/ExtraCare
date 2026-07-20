import {
  Home, Settings2, Users2, UserCircle, CalendarClock, GraduationCap,
  Star, AlertTriangle, Fingerprint, Briefcase, FileText,
} from "lucide-react";

/**
 * Single source of truth for the HR Manager navigation — the 10 top-level tabs and
 * their sub-items, shared by the tab bar (HrTabNav), the section landing page, and
 * the dashboard Quick Links. Each item declares the permission it needs and whether
 * its page is built yet (net-new items render disabled to admins, hidden from staff).
 */

export type HrPerm = "hr:read" | "hr:write";
export type HrItem = { label: string; href?: string; perm: HrPerm; built?: boolean };
export type HrTab = { key: string; label: string; icon: any; href?: string; perm: HrPerm; items?: HrItem[] };

const W: HrPerm = "hr:write";
const R: HrPerm = "hr:read";

export const HR_TABS: HrTab[] = [
  { key: "home", label: "Home", icon: Home, href: "/dashboard/hrm", perm: W },
  {
    key: "admin", label: "Admin", icon: Settings2, perm: W, items: [
      { label: "Job Titles", href: "/dashboard/hrm/admin/job-titles", perm: W, built: true },
      { label: "Job Categories", href: "/dashboard/hrm/admin/job-categories", perm: W, built: true },
      { label: "Pay Grades", href: "/dashboard/hrm/admin/pay-grades", perm: W, built: true },
      { label: "Salary Components", href: "/dashboard/hrm/admin/salary-components", perm: W, built: true },
      { label: "Work Shifts", href: "/dashboard/hrm/admin/work-shifts", perm: W, built: true },
      { label: "Employment Status", href: "/dashboard/hrm/admin/employment-status", perm: W, built: true },
      { label: "Working Tools", href: "/dashboard/hrm/admin/working-tools", perm: W, built: true },
      { label: "Competency List", href: "/dashboard/hrm/admin/competencies", perm: W, built: true },
      { label: "Qualification — Skills", href: "/dashboard/hrm/admin/qualification-skills", perm: W, built: true },
      { label: "Qualification — Education", href: "/dashboard/hrm/admin/qualification-education", perm: W, built: true },
      { label: "Qualification — Licenses", href: "/dashboard/hrm/admin/qualification-licenses", perm: W, built: true },
      { label: "Qualification — Languages", href: "/dashboard/hrm/admin/qualification-languages", perm: W, built: true },
      { label: "Qualification — Memberships", href: "/dashboard/hrm/admin/qualification-memberships", perm: W, built: true },
      { label: "Pension Fund Administrators", href: "/dashboard/hrm/admin/pension-fund-administrators", perm: W, built: true },
      { label: "HR Operations", href: "/dashboard/hrm/admin/hr-operations", perm: W, built: true },
      { label: "Contributory Leave Allowance", href: "/dashboard/hrm/admin/contributory-leave-allowance", perm: W, built: true },
      // Deferred (need real modelling / wiring, not flat lists):
      { label: "Organization Structure", perm: W }, { label: "Staff Confirmation", perm: W },
      { label: "HR Departments", perm: W }, { label: "Documents", perm: W },
    ],
  },
  {
    key: "pim", label: "PIM", icon: Users2, perm: W, items: [
      { label: "Employee List", href: "/dashboard/modules/school/staff", perm: W, built: true },
      { label: "Staff Transfer Log", perm: W }, { label: "Staff Account Numbers", perm: W },
      { label: "Staff Confirmation List", perm: W }, { label: "Configuration", perm: W },
    ],
  },
  { key: "my-info", label: "My Info", icon: UserCircle, href: "/dashboard/hrm/my-info", perm: R },
  {
    key: "leave", label: "Leave", icon: CalendarClock, perm: R, items: [
      { label: "Apply", href: "/dashboard/hrm/leave", perm: R, built: true },
      { label: "My Leave", href: "/dashboard/hrm/leave", perm: R, built: true },
      { label: "Leave List", href: "/dashboard/hrm/leave/admin", perm: W, built: true },
      { label: "Reports", href: "/dashboard/hrm/leave/admin", perm: W, built: true },
      { label: "Entitlements", perm: R }, { label: "Assign Leave", perm: W }, { label: "Configure", perm: W },
    ],
  },
  {
    key: "training", label: "Training", icon: GraduationCap, perm: W, items: [
      { label: "Trainings", perm: W }, { label: "Sessions", perm: W }, { label: "Configuration", perm: W },
    ],
  },
  {
    key: "performance", label: "Performance", icon: Star, perm: W, items: [
      { label: "Appraisals", href: "/dashboard/hrm/performance", perm: W, built: true },
      { label: "Appraisal Configuration", perm: W }, { label: "Competency Mappings", perm: W },
    ],
  },
  {
    key: "discipline", label: "Discipline", icon: AlertTriangle, perm: R, items: [
      { label: "Disciplinary Cases", href: "/dashboard/hrm/disciplinary", perm: W, built: true },
      { label: "My Actions", href: "/dashboard/hrm/disciplinary/my-actions", perm: R, built: true },
      { label: "Disciplinary Types", href: "/dashboard/hrm/admin/disciplinary-types", perm: W, built: true },
    ],
  },
  {
    key: "access", label: "Access Control", icon: Fingerprint, perm: R, items: [
      { label: "Clock in / Clock out Log", perm: W }, { label: "My Attendance Record", perm: R },
      { label: "Configuration", perm: W },
    ],
  },
  {
    key: "recruitment", label: "Recruitment", icon: Briefcase, perm: W, items: [
      { label: "Vacancies", href: "/dashboard/hrm/recruitment", perm: W, built: true },
      { label: "Configuration", perm: W },
    ],
  },
];

// Dashboard Quick Links — the admin-facing HR categories (Educare's landing grid).
// Each opens the section page with that tab's dropdown pre-expanded.
export const HR_QUICK_LINKS: { key: string; label: string; icon: any }[] = [
  { key: "admin", label: "Admin", icon: Settings2 },
  { key: "pim", label: "PIM", icon: Users2 },
  { key: "recruitment", label: "Recruitment", icon: Briefcase },
  { key: "access", label: "Access Control", icon: Fingerprint },
  { key: "performance", label: "Performance", icon: Star },
  { key: "leave", label: "Leave", icon: CalendarClock },
  { key: "training", label: "Training", icon: GraduationCap },
  { key: "discipline", label: "Discipline", icon: AlertTriangle },
  { key: "documents", label: "Document & Templates", icon: FileText },
];

// "Document & Templates" isn't its own tab — Documents lives under Admin.
export const quickLinkTarget = (key: string) =>
  `/dashboard/hrm/section?open=${key === "documents" ? "admin" : key}`;

// HR managed lists — the single source mapping URL slug ↔ backend list_type ↔
// label, shared by the dynamic [list] page and its lookups. Most live under the
// Admin tab; `section` marks a list that belongs to a different tab (e.g.
// Disciplinary Types under Discipline) so the list page breadcrumbs correctly and
// the Admin landing can exclude it.
export type HrAdminList = { slug: string; type: string; label: string; hint: string; section?: { label: string; href: string } };
const DISCIPLINE_SECTION = { label: "Discipline", href: "/dashboard/hrm/disciplinary" };

export const HR_ADMIN_LISTS: HrAdminList[] = [
  // Phase 1 — Job cluster
  { slug: "job-titles", type: "job_title", label: "Job Titles", hint: "Positions staff can hold (e.g. Senior Teacher, Bursar)." },
  { slug: "job-categories", type: "job_category", label: "Job Categories", hint: "Groupings for job titles (e.g. Teaching, Admin, Support)." },
  { slug: "pay-grades", type: "pay_grade", label: "Pay Grades", hint: "Salary grade bands (e.g. Grade 8, TS3)." },
  { slug: "salary-components", type: "salary_component", label: "Salary Components", hint: "Earnings & deductions (e.g. Basic, Housing, Tax)." },
  { slug: "work-shifts", type: "work_shift", label: "Work Shifts", hint: "Named work schedules (e.g. Morning, Boarding Duty)." },
  { slug: "employment-status", type: "employment_status", label: "Employment Status", hint: "Contract states (e.g. Probation, Confirmed, Contract)." },
  { slug: "working-tools", type: "working_tool", label: "Working Tools", hint: "Assets issued to staff (e.g. Laptop, ID Card)." },
  // Phase 2 — Admin reference lists
  { slug: "competencies", type: "competency", label: "Competency List", hint: "Skills & behaviours scored in appraisals (e.g. Communication, Leadership)." },
  { slug: "qualification-skills", type: "qual_skill", label: "Qualification — Skills", hint: "Recognised staff skills (e.g. First Aid, Coaching)." },
  { slug: "qualification-education", type: "qual_education", label: "Qualification — Education", hint: "Education levels / degrees (e.g. B.Ed, M.Sc)." },
  { slug: "qualification-licenses", type: "qual_license", label: "Qualification — Licenses", hint: "Professional licences (e.g. TRCN, Driving)." },
  { slug: "qualification-languages", type: "qual_language", label: "Qualification — Languages", hint: "Languages staff may speak (e.g. English, French)." },
  { slug: "qualification-memberships", type: "qual_membership", label: "Qualification — Memberships", hint: "Professional bodies (e.g. CIPM, NUT)." },
  { slug: "pension-fund-administrators", type: "pension_fund", label: "Pension Fund Administrators", hint: "PFAs staff enrol with (e.g. Stanbic IBTC, ARM)." },
  { slug: "hr-operations", type: "hr_operation", label: "HR Operations", hint: "Named HR operational processes / checklists." },
  { slug: "contributory-leave-allowance", type: "contributory_leave", label: "Contributory Leave Allowance", hint: "Leave-allowance schemes staff contribute to." },
  // Phase 2 — Discipline config (lives under the Discipline tab, not Admin)
  { slug: "disciplinary-types", type: "disciplinary_type", label: "Disciplinary Types", hint: "Categories of disciplinary action (e.g. Verbal Warning, Suspension).", section: DISCIPLINE_SECTION },
];

export const adminListBySlug = (slug: string) => HR_ADMIN_LISTS.find((l) => l.slug === slug);
