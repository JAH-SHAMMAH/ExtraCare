"use client";

import { InactiveRoster } from "@/components/students/InactiveRoster";

export default function WithdrawalListPage() {
  return <InactiveRoster status="withdrawn" crumb="Withdrawal List" title="Withdrawal List" subtitle="Students who have been withdrawn — reason, date, and reactivate." />;
}
