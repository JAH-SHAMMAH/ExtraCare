"use client";

import { useState } from "react";
import { usePastoralReport, useRemarkBank, useAddPastoralRemark, useDeletePastoralRemark } from "@/hooks/usePastoral";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn } from "@/lib/utils";
import { Loader2, FileText, Trash2, Home, BedDouble } from "lucide-react";

const TERMS = ["Autumn Term", "Spring Term", "Summer Term"];

export default function PastoralReportPage() {
  const canWrite = useHasPermission("school:hostel:write");
  const [studentId, setStudentId] = useState<string | null>(null);
  const [term, setTerm] = useState("");
  const { data: report, isLoading } = usePastoralReport({ student_id: studentId || "", term: term || undefined });
  const { data: bank = [] } = useRemarkBank();
  const addRemark = useAddPastoralRemark();
  const delRemark = useDeletePastoralRemark();
  const [remark, setRemark] = useState("");

  const kpi = (label: string, value: any, cls = "text-slate-900") => (
    <div className="bg-white rounded-xl border border-slate-200 p-4"><p className={cn("text-2xl font-black tabular-nums", cls)}>{value ?? 0}</p><p className="text-xs text-slate-500 mt-0.5">{label}</p></div>
  );

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Pastoral</span><span>/</span><span className="text-brand-600 font-semibold">Pastoral Report</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2"><FileText size={22} className="text-brand-600" /> Pastoral Report</h1>
      <p className="text-slate-500 text-sm mb-5">A boarder&apos;s pastoral summary: conduct points, hostel life, discipline and remarks.</p>

      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3 mb-6">
        <div className="flex-1 min-w-[220px]"><label className="label">Student</label><EntityPicker type="student" value={studentId} onChange={setStudentId} /></div>
        <div><label className="label">Term</label><select value={term} onChange={(e) => setTerm(e.target.value)} className="input"><option value="">All terms</option>{TERMS.map((t) => <option key={t} value={t}>{t}</option>)}</select></div>
      </div>

      {!studentId ? (
        <div className="bg-white rounded-xl border border-dashed border-slate-200 py-16 text-center text-slate-400"><FileText size={30} className="mx-auto mb-3 opacity-40" /><p className="text-sm">Select a student to build their pastoral report.</p></div>
      ) : isLoading ? (
        <div className="py-16 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : report ? (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-lg font-black text-slate-900">{report.student_name}</h2>
            {report.house_name && <span className="badge bg-slate-50 text-slate-600 border-slate-200 gap-1"><Home size={12} /> {report.house_name}</span>}
            {report.hostel_name && <span className="badge bg-slate-50 text-slate-600 border-slate-200 gap-1"><BedDouble size={12} /> {report.hostel_name}</span>}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {kpi("Net Points", report.total_points, report.total_points >= 0 ? "text-emerald-600" : "text-red-600")}
            {kpi("Gained", report.points_gained, "text-emerald-600")}
            {kpi("Lost", report.points_lost, "text-red-600")}
            {kpi("Open Cases", report.open_cases, report.open_cases > 0 ? "text-amber-600" : "text-slate-900")}
            {kpi("Total Cases", report.total_cases)}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="px-5 py-3 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">Hostel Life Comments</h3></div>
              {(report.life_comments ?? []).length === 0 ? <p className="text-sm text-slate-400 py-8 text-center">None.</p> : (
                <ul className="divide-y divide-slate-50 max-h-72 overflow-y-auto">
                  {report.life_comments.map((c: any) => (
                    <li key={c.id} className="px-5 py-3">
                      <div className="flex items-center gap-2">{c.grade && <span className="badge bg-brand-50 text-brand-700 border-brand-200">{c.grade}</span>}<span className="text-xs text-slate-400">{[c.term, c.recorded_on].filter(Boolean).join(" · ")}</span></div>
                      {c.comment && <p className="text-sm text-slate-700 mt-1">{c.comment}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="px-5 py-3 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">Pastoral Remarks</h3></div>
              {(report.remarks ?? []).length === 0 ? <p className="text-sm text-slate-400 py-8 text-center">None.</p> : (
                <ul className="divide-y divide-slate-50 max-h-72 overflow-y-auto">
                  {report.remarks.map((r: any) => (
                    <li key={r.id} className="px-5 py-3 flex items-start justify-between gap-3">
                      <div className="min-w-0"><p className="text-sm text-slate-700">{r.remark}</p><p className="text-xs text-slate-400 mt-0.5">{[r.term, r.recorded_by_name, r.recorded_on].filter(Boolean).join(" · ")}</p></div>
                      {canWrite && <button onClick={() => delRemark.mutate(r.id)} className="text-slate-400 hover:text-red-600 p-1 shrink-0"><Trash2 size={14} /></button>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {canWrite && (
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="text-sm font-bold text-slate-800 mb-3">Add a remark{term ? ` · ${term}` : ""}</h3>
              <textarea value={remark} onChange={(e) => setRemark(e.target.value)} className="input" rows={3} placeholder="Write a pastoral remark…" />
              {(bank as any[]).filter((b) => b.is_active).length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {(bank as any[]).filter((b) => b.is_active).slice(0, 12).map((b) => (
                    <button key={b.id} type="button" onClick={() => setRemark((p) => p ? `${p} ${b.text}` : b.text)} className="text-[11px] px-2 py-1 rounded-full bg-slate-100 text-slate-600 hover:bg-brand-50 hover:text-brand-700">+ {b.text.length > 34 ? b.text.slice(0, 34) + "…" : b.text}</button>
                  ))}
                </div>
              )}
              <div className="flex justify-end mt-3">
                <button onClick={() => remark.trim() && studentId && addRemark.mutate({ student_id: studentId, term: term || null, remark: remark.trim() }, { onSuccess: () => setRemark("") })} disabled={!remark.trim() || addRemark.isPending} className="btn-primary gap-2">{addRemark.isPending && <Loader2 size={15} className="animate-spin" />} Save Remark</button>
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
