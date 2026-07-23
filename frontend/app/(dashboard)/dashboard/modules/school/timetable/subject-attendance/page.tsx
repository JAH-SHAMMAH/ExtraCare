"use client";

import { useState } from "react";
import { useClasses, useSubjects } from "@/hooks/useSchool";
import { useSubjectAttendance } from "@/hooks/useTimetableModule";
import { CalendarCheck, Loader2, Info } from "lucide-react";
import type { SubjectAttendanceRow } from "@/types";

export default function SubjectAttendancePage() {
  const { data: classesData } = useClasses({ page_size: 200 });
  const { data: subjectsData } = useSubjects({ page_size: 200 });
  const classes = classesData?.items ?? [];
  const subjects = subjectsData?.items ?? [];

  const [filters, setFilters] = useState({ class_id: "", subject_id: "", start_date: "", end_date: "" });
  const [applied, setApplied] = useState<{ class_id: string; start_date?: string; end_date?: string } | null>(null);
  const { data, isLoading } = useSubjectAttendance({ class_id: applied?.class_id ?? null, start_date: applied?.start_date, end_date: applied?.end_date });
  const rows: SubjectAttendanceRow[] = data?.items ?? [];

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>TimeTable</span><span>/</span><span className="text-brand-600 font-semibold">Subject Student Attendance</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">View Subject Student Attendance</h1>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
        <div><label className="label">Class *</label><select value={filters.class_id} onChange={(e) => setFilters({ ...filters, class_id: e.target.value })} className="input"><option value="">Select…</option>{classes.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
        <div><label className="label">Subject</label><select value={filters.subject_id} onChange={(e) => setFilters({ ...filters, subject_id: e.target.value })} className="input"><option value="">All</option>{subjects.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
        <div><label className="label">From</label><input type="date" value={filters.start_date} onChange={(e) => setFilters({ ...filters, start_date: e.target.value })} className="input" /></div>
        <div><label className="label">To</label><input type="date" value={filters.end_date} onChange={(e) => setFilters({ ...filters, end_date: e.target.value })} className="input" /></div>
        <div className="lg:col-span-4"><button onClick={() => setApplied({ class_id: filters.class_id, start_date: filters.start_date || undefined, end_date: filters.end_date || undefined })} disabled={!filters.class_id} className="btn-primary gap-2"><CalendarCheck size={15} /> View History</button></div>
      </div>

      <div className="flex items-start gap-2 text-xs text-slate-500 bg-slate-50 border border-slate-100 rounded-lg px-3 py-2 mb-4">
        <Info size={14} className="mt-0.5 shrink-0 text-slate-400" />
        <span>We record class/day attendance (not per-lesson), so this rolls up each student’s attendance for the selected class and dates; the subject filter is informational.</span>
      </div>

      {!applied ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400"><CalendarCheck size={30} className="mx-auto mb-2 opacity-40" /><p className="font-semibold">Pick a class and date range, then View History</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
          <div className="px-5 py-2.5 border-b border-slate-100 text-xs text-slate-400">{data ? `${data.days} school day(s) in range` : ""}</div>
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Present", "Absent", "Late", "Total"].map((h) => <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-slate-50">
              {isLoading ? <tr><td colSpan={5} className="px-5 py-10 text-center text-slate-400"><Loader2 className="animate-spin mx-auto" /></td></tr>
              : rows.length > 0 ? rows.map((r) => (
                <tr key={r.student_id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-3 text-sm font-semibold text-slate-800">{r.student_name}</td>
                  <td className="px-5 py-3 text-sm font-bold text-emerald-600">{r.present}</td>
                  <td className="px-5 py-3 text-sm font-bold text-rose-500">{r.absent}</td>
                  <td className="px-5 py-3 text-sm font-bold text-amber-600">{r.late}</td>
                  <td className="px-5 py-3 text-sm text-slate-600">{r.total}</td>
                </tr>
              )) : <tr><td colSpan={5} className="py-14 text-center text-slate-400 font-semibold">No Data Available</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
