"use client";

import { useState } from "react";
import Link from "next/link";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { AssessmentForm } from "./AssessmentForm";
import { Settings2, ListChecks } from "lucide-react";

export default function StaffAssessmentPage() {
  const canWrite = useHasPermission("hr:write");
  const [formKey, setFormKey] = useState(0);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Staff Management</span><span>/</span><span className="text-brand-600 font-semibold">Staff Assessment</span></nav>
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">Staff Assessment</h1>
            <p className="text-slate-500 text-sm mt-0.5">Record a performance appraisal against the configured rubric.</p>
          </div>
          <div className="flex gap-3">
            <Link href="/dashboard/modules/school/staff-assessment/setup" className="btn-secondary gap-2"><Settings2 size={15} /> Setup</Link>
            <Link href="/dashboard/modules/school/staff-assessment/manage" className="btn-secondary gap-2"><ListChecks size={15} /> Manage</Link>
          </div>
        </div>
      </div>

      {canWrite ? (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <AssessmentForm key={formKey} onDone={() => setFormKey((k) => k + 1)} />
        </div>
      ) : (
        <p className="text-slate-400 text-sm">You don’t have permission to create assessments.</p>
      )}
    </div>
  );
}
