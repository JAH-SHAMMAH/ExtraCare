"use client";

import { StaffDirectory } from "@/components/staff/StaffDirectory";

// The staff & admin directory lives in a shared component so the HR Manager
// (PIM › Employee List) can render the same list inside its own tab-bar shell.
export default function StaffDirectoryPage() {
  return <StaffDirectory breadcrumb={["People & HR", "Staff & Admin"]} />;
}
