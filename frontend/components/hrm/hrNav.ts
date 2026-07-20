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
      { label: "Organization Structure", perm: W },
      { label: "Competency List", perm: W }, { label: "Qualification — Skills", perm: W },
      { label: "Qualification — Education", perm: W }, { label: "Qualification — Licenses", perm: W },
      { label: "Qualification — Languages", perm: W }, { label: "Qualification — Memberships", perm: W },
      { label: "Staff Confirmation", perm: W }, { label: "HR Departments", perm: W },
      { label: "HR Operations", perm: W }, { label: "Pension Fund Administrators", perm: W },
      { label: "Contributory Leave Allowance", perm: W }, { label: "Documents", perm: W },
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
      { label: "My Actions", perm: R }, { label: "Disciplinary Types", perm: W },
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

// Phase-1 Admin managed lists — the single source mapping URL slug ↔ backend
// list_type ↔ label, shared by the dynamic [list] page and its lookups.
export const HR_ADMIN_LISTS: { slug: string; type: string; label: string; hint: string }[] = [
  { slug: "job-titles", type: "job_title", label: "Job Titles", hint: "Positions staff can hold (e.g. Senior Teacher, Bursar)." },
  { slug: "job-categories", type: "job_category", label: "Job Categories", hint: "Groupings for job titles (e.g. Teaching, Admin, Support)." },
  { slug: "pay-grades", type: "pay_grade", label: "Pay Grades", hint: "Salary grade bands (e.g. Grade 8, TS3)." },
  { slug: "salary-components", type: "salary_component", label: "Salary Components", hint: "Earnings & deductions (e.g. Basic, Housing, Tax)." },
  { slug: "work-shifts", type: "work_shift", label: "Work Shifts", hint: "Named work schedules (e.g. Morning, Boarding Duty)." },
  { slug: "employment-status", type: "employment_status", label: "Employment Status", hint: "Contract states (e.g. Probation, Confirmed, Contract)." },
  { slug: "working-tools", type: "working_tool", label: "Working Tools", hint: "Assets issued to staff (e.g. Laptop, ID Card)." },
];

export const adminListBySlug = (slug: string) => HR_ADMIN_LISTS.find((l) => l.slug === slug);
