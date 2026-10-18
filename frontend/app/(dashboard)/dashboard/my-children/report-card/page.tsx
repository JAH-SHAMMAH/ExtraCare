"use client";

import Link from "next/link";
import { GraduationCap, Loader2, ArrowLeft } from "lucide-react";
import { useMyContexts, type ParentChild } from "@/hooks/useMyContexts";
import { ReportCardViewer } from "@/components/reports/ReportCardViewer";

/** A parent's view of their children's report cards — the designed report the school prints. */
export default function ParentReportCardPage() {
  const { data, isLoading } = useMyContexts();
  const children: ParentChild[] = data?.as_parent?.children ?? [];
  const people = children.map((c) => ({ id: c.id, name: `${c.first_name} ${c.last_name}`, first_name: c.first_name }));

  return (
    <div className="p-4 sm:p-8 max-w-4xl mx-auto">
      <Link href="/dashboard/my-children" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4 no-print"><ArrowLeft size={13} /> My Children</Link>
      <div className="mb-6 no-print">
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Report Card</h1>
        <p className="text-slate-500 text-sm mt-0.5">Your child&apos;s finalised report. It appears here once the school publishes it.</p>
      </div>
      {isLoading ? (
        <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
      ) : people.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400">
          <GraduationCap size={34} className="mx-auto mb-3 opacity-40" />
          <p className="font-semibold text-slate-500">No children linked to your account</p>
          <p className="text-sm mt-1">Ask the school to link your child to your parent account.</p>
        </div>
      ) : (
        <ReportCardViewer people={people} />
      )}
    </div>
  );
}
