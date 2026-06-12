"use client";

import { ImportWizard } from "@/components/import/ImportWizard";
import { studentImportPreset } from "@/lib/import/presets";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { ShieldAlert } from "lucide-react";

export default function StudentsImportPage() {
  const canWrite = useHasPermission("school:write");

  if (!canWrite) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-400 p-8">
        <ShieldAlert size={40} className="mb-3 opacity-40" />
        <p className="font-semibold text-slate-600 text-lg">Access Restricted</p>
        <p className="text-sm mt-1">You don&apos;t have permission to import students.</p>
      </div>
    );
  }

  return <ImportWizard preset={studentImportPreset} />;
}
