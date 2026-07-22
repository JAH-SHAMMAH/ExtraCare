"use client";

import { InactiveRoster } from "@/components/students/InactiveRoster";

export default function ManageInactiveStudentsPage() {
  return <InactiveRoster status="inactive" crumb="Manage Inactive Students" title="Manage Inactive Students" subtitle="All inactive students (withdrawn or graduated) — reactivate to restore them." />;
}
