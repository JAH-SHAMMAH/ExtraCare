"use client";

import { StaffDirectory } from "@/components/staff/StaffDirectory";

// PIM › Employee List. Renders the shared staff directory under /dashboard/hrm so
// the HR Manager tab bar stays visible (previously this linked out to the school
// module's staff page and dropped the HR shell).
export default function PimEmployeesPage() {
  return <StaffDirectory breadcrumb={["HR Manager", "Employee List"]} />;
}
