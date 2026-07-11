"use client";

import { useState } from "react";
import Link from "next/link";
import { useApplications, useUpdateApplication } from "@/hooks/useEnrollment";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import { ArrowLeft, Contact, Loader2, ExternalLink, Mail, Phone } from "lucide-react";
import type { AdmissionApplication } from "@/types";

// CRM = a pipeline lens over Admissions & Enquiries. There is no separate CRM
// store — prospective-parent contact, source and stage all live on the admission
// application, so this reads the same data rather than duplicating it.
const STAGES = ["enquiry", "applied", "screening", "offered", "admitted", "rejected", "withdrawn"];
const STAGE_STYLE: Record<string, string> = {
  enquiry: "bg-slate-50 text-slate-600 border-slate-200",
  applied: "bg-blue-50 text-blue-700 border-blue-200",
  screening: "bg-indigo-50 text-indigo-700 border-indigo-200",
  offered: "bg-amber-50 text-amber-700 border-amber-200",
  admitted: "bg-emerald-50 text-emerald-700 border-emerald-200",
  rejected: "bg-rose-50 text-rose-700 border-rose-200",
  withdrawn: "bg-slate-50 text-slate-400 border-slate-200",
};

export default function CrmPage() {
  const canWrite = useHasPermission("school:admissions:write");
  const [stageFilter, setStageFilter] = useState("");
  const { data, isLoading } = useApplications({ status: stageFilter || undefined, page: 1, page_size: 100 });
  const update = useUpdateApplication();
  const contacts = (data?.items as AdmissionApplication[] | undefined) || [];

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <Link href="/dashboard/modules/school/feedback" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Feedback</Link>
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-4 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Feedback</span><span>/</span><span className="text-brand-600 font-semibold">CRM</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">CRM</h1>
          <p className="text-slate-500 text-sm mt-0.5">Prospective-parent enquiry pipeline — a view of your Admissions &amp; Enquiries data.</p>
        </div>
        <Link href="/dashboard/modules/school/admissions" className="btn-secondary gap-2"><ExternalLink size={15} /> Open Admissions</Link>
      </div>

      <div className="rounded-xl border border-slate-200 bg-slate-50/60 px-4 py-3 mb-6 text-xs text-slate-500">
        This is the same data as <Link href="/dashboard/modules/school/admissions" className="text-brand-600 font-semibold hover:underline">Admissions &amp; Enquiries</Link> — moving a contact through stages here updates the application there. Add new enquiries and admit applicants from Admissions.
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4">
        <select value={stageFilter} onChange={(e) => setStageFilter(e.target.value)} className="input max-w-48 capitalize"><option value="">All stages</option>{STAGES.map((s) => <option key={s} value={s}>{s}</option>)}</select>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        {isLoading ? (
          <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
        ) : contacts.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-sm"><Contact size={30} className="mx-auto mb-2 opacity-50" />No enquiries yet. Add them from Admissions.</div>
        ) : (
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Prospect", "Guardian / contact", "Source", "Stage", "Added"].map((h) => (<th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>))}</tr></thead>
            <tbody className="divide-y divide-slate-50">
              {contacts.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-3 text-sm font-bold text-slate-900">{c.full_name || `${c.first_name} ${c.last_name}`}{c.applying_for_level && <p className="text-xs font-normal text-slate-400">for {c.applying_for_level}</p>}</td>
                  <td className="px-5 py-3 text-xs text-slate-500">
                    {c.guardian_name && <p className="font-semibold text-slate-600">{c.guardian_name}</p>}
                    {c.guardian_email && <p className="inline-flex items-center gap-1"><Mail size={11} />{c.guardian_email}</p>}
                    {c.guardian_phone && <p className="inline-flex items-center gap-1"><Phone size={11} />{c.guardian_phone}</p>}
                    {!c.guardian_name && !c.guardian_email && !c.guardian_phone && "—"}
                  </td>
                  <td className="px-5 py-3 text-sm text-slate-600">{c.source || "—"}</td>
                  <td className="px-5 py-3">
                    {canWrite ? (
                      <select value={c.status} onChange={(e) => update.mutate({ id: c.id, data: { status: e.target.value } })} className={cn("text-xs font-semibold rounded-lg border px-2 py-1 capitalize", STAGE_STYLE[c.status as string] || "bg-slate-50 text-slate-600 border-slate-200")}>
                        {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                    ) : (
                      <span className={cn("badge capitalize", STAGE_STYLE[c.status as string] || "bg-slate-50 text-slate-600 border-slate-200")}>{c.status}</span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-xs text-slate-400">{formatDate(c.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
