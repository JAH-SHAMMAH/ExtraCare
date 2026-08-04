import { describe, expect, it } from "vitest";
import { canAccessPath } from "@/lib/access";

// The shipped classroom-tier preset (backend models/role.py "teacher"). Kept in
// sync by backend/tests/test_teacher_role_rbac.py, which asserts the same set
// against the real presets; this file proves the NAV agrees with it — a teacher
// must never see a link to a page the API would refuse.
const TEACHER_PERMISSIONS = [
  "users:read", "hr:read",
  "school:classes:read", "school:teachers:read", "school:students:read",
  "school:subjects:read", "school:timetable:read",
  "school:grades:read", "school:grades:write",
  "school:exams:read", "school:exams:write",
  "school:reports:read", "school:reports:write",
  "school:attendance:read", "school:attendance:write",
  "school:lessons:read", "school:lessons:write",
  "school:cbt:read", "school:cbt:write", "school:cbt:manage",
  "school:classroom:read", "school:classroom:write", "school:classroom:manage",
  "school:pastoral:read",
  "school:behaviour:read", "school:behaviour:write",
  "school:journals:read", "school:journals:write",
  "school:feedback:read", "school:feedback:write",
  "school:clubs:read", "school:clubs:write",
  "school:calendar:read", "school:calendar:write",
];

/** Mirrors useAuthStore.hasPermission (incl. the broad→fine scope hierarchy). */
function hasPermission(permission: string): boolean {
  if (TEACHER_PERMISSIONS.includes(permission)) return true;
  const parts = permission.split(":");
  if (TEACHER_PERMISSIONS.includes(`${parts[0]}:*`)) return true;
  if (parts.length === 3 && TEACHER_PERMISSIONS.includes(`${parts[0]}:${parts[2]}`)) return true;
  return false;
}

// Admin surfaces that must NOT appear in a teacher's sidebar. Benchmarked
// against Educare's teacher nav, where none of these exist teacher-side.
const HIDDEN = [
  // Students module — the whole roster-admin cluster
  "/dashboard/modules/school/students",
  "/dashboard/modules/school/students/withdrawal",
  "/dashboard/modules/school/students/withdrawal-list",
  "/dashboard/modules/school/students/inactive",
  "/dashboard/modules/school/students/pickup",
  "/dashboard/modules/school/admissions",
  "/dashboard/modules/school/admissions/appointments",
  "/dashboard/modules/school/admissions/post-entrance",
  "/dashboard/modules/school/admissions/acceptance",
  "/dashboard/modules/school/entrance-exams",
  "/dashboard/modules/school/promotion",
  "/dashboard/modules/school/transfer",
  // TimeTable structure
  "/dashboard/modules/school/timetable/setup",
  "/dashboard/modules/school/timetable/periods",
  "/dashboard/modules/school/timetable/activities",
  "/dashboard/modules/school/timetable/schedules",
  "/dashboard/modules/school/timetable/tabler",
  "/dashboard/modules/school/timetable/curriculum",
  "/dashboard/modules/school/timetable/subject-attendance",
  // Voting System
  "/dashboard/modules/voting/rating-setup",
  "/dashboard/modules/voting/manage-rating",
  "/dashboard/modules/voting/setup",
  "/dashboard/modules/voting/manage",
  // Staff Management
  "/dashboard/modules/school/staff",
  "/dashboard/modules/school/ratings",
  "/dashboard/modules/school/parents",
  "/dashboard/modules/school/staff-assessment",
  "/dashboard/modules/school/talent-pool",
  // Library administration
  "/dashboard/modules/school/library",
  "/dashboard/modules/school/library/catalogue",
  "/dashboard/modules/school/library/loans",
  "/dashboard/modules/school/library/setup",
  // Class + YearGroup taxonomy
  "/dashboard/modules/school/classes",
  "/dashboard/modules/school/classes/year-groups",
  // Behaviour Tracker configuration
  "/dashboard/modules/school/behaviour/categories",
  "/dashboard/modules/school/behaviour/subcategories",
  "/dashboard/modules/school/behaviour/levels",
  "/dashboard/modules/school/behaviour/settings",
  // Boarding cluster + pastoral config
  "/dashboard/modules/school/pastoral-setup",
  "/dashboard/modules/school/hostel",
  "/dashboard/modules/school/hostel-students",
  "/dashboard/modules/school/hostel-life",
  "/dashboard/modules/school/hostel-reports",
  "/dashboard/modules/school/exeat",
  "/dashboard/modules/school/mentor",
  // Lesson Planner supervision + CBT admin ops
  "/dashboard/modules/school/lessons/setup",
  "/dashboard/modules/school/lessons/approve",
  "/dashboard/modules/school/cbt/import",
  "/dashboard/modules/school/cbt/reset",
  "/dashboard/modules/school/cbt/export",
  "/dashboard/modules/school/cbt/remark",
  "/dashboard/modules/school/cbt/settings",
  "/dashboard/modules/school/cbt/interventions",
  // Report administration (T-1) + club administration + feedback config
  "/dashboard/modules/school/report-setup",
  "/dashboard/modules/school/report-entry",
  "/dashboard/modules/school/report-workflow",
  "/dashboard/modules/school/reports-upload",
  "/dashboard/modules/school/result-publish",
  "/dashboard/modules/school/clubs",
  "/dashboard/modules/school/clubs/membership",
  "/dashboard/modules/school/clubs/assessment",
  "/dashboard/modules/school/feedback/settings",
  "/dashboard/modules/school/feedback/crm",
  // Platform administration + analytics
  "/dashboard/analytics",
  "/dashboard/users",
  "/dashboard/audit",
  "/dashboard/hrm",
  "/dashboard/modules/school/school-setup",
  "/dashboard/modules/school/biometric",
  "/dashboard/modules/school/medicals",
  "/dashboard/modules/school/fees",
  "/dashboard/modules/school/payroll",
  "/dashboard/modules/school/tuckshop",
  "/dashboard/modules/school/sms",
  "/dashboard/modules/school/transport",
];

// The classroom nav a teacher must keep (Educare's teacher-side list).
const VISIBLE = [
  "/dashboard/modules/school/reports-view",
  "/dashboard/modules/school/make-report",
  "/dashboard/modules/school/mark-books",
  "/dashboard/modules/school/report-cards",
  "/dashboard/modules/school/grades",
  "/dashboard/modules/school/exams",
  "/dashboard/modules/school/subjects",
  "/dashboard/modules/school/subject-selection",
  "/dashboard/modules/school/lessons",
  "/dashboard/modules/school/cbt",
  "/dashboard/modules/school/cbt/question-bank",
  "/dashboard/modules/school/cbt/results",
  "/dashboard/modules/eclassroom/manage",
  "/dashboard/modules/school/eclassroom",
  "/dashboard/modules/school/attendance",
  "/dashboard/modules/school/attendance/monitor",
  "/dashboard/modules/school/pastoral-dashboard",
  "/dashboard/modules/school/pastoral-students",
  "/dashboard/modules/school/pastoral-report",
  "/dashboard/modules/school/behaviour",
  "/dashboard/modules/school/behaviour-sanction",
  "/dashboard/modules/school/point-entry",
  "/dashboard/modules/school/points-analysis",
  "/dashboard/modules/school/merits",
  "/dashboard/modules/school/journals",
  "/dashboard/modules/school/remarks",
  "/dashboard/modules/school/feedback",
  "/dashboard/modules/school/feedback/mine",
  "/dashboard/modules/school/feedback/manage",
  "/dashboard/modules/school/feedback/daily-reports",
  "/dashboard/modules/school/clubs/enrollment",
  "/dashboard/modules/school/calendar",
  "/dashboard/hrm/my-info",
  "/dashboard/hrm/leave",
];

describe("teacher sidebar parity", () => {
  it.each(HIDDEN)("hides %s", (path) => {
    expect(canAccessPath(path, hasPermission)).toBe(false);
  });

  it.each(VISIBLE)("keeps %s", (path) => {
    expect(canAccessPath(path, hasPermission)).toBe(true);
  });
});
