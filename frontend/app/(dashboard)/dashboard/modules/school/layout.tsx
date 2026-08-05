"use client";

import { ModuleGate } from "@/components/guards/ModuleGate";

export default function SchoolModuleLayout({ children }: { children: React.ReactNode }) {
  // Permission checks are handled per-route by access.ts rules (e.g., school:reports:read
  // for reports-view, school:reports:write for make-report, etc.). Do NOT gate at the
  // module level with a broad school:read permission — that was removed from the teacher
  // role in migration 118 as part of fine-grained RBAC narrowing. Let ModuleGate handle
  // only the industry/workspace check, not permission checks.
  return <ModuleGate module="school">{children}</ModuleGate>;
}
