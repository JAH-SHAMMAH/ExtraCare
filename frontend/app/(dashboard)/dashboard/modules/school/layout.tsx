"use client";

import { ModuleGate } from "@/components/guards/ModuleGate";

export default function SchoolModuleLayout({ children }: { children: React.ReactNode }) {
  return <ModuleGate module="school" permission="school:read">{children}</ModuleGate>;
}
