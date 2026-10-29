"use client";

import { useState } from "react";
import { useStudents, useMarkAttendance, useAttendance, useAbsenceReasons, useClasses } from "@/hooks/useSchool";
import { cn, formatDate } from "@/lib/utils";
import { ClipboardList, Loader2, Check, X as XIcon, Clock } from "lucide-react";
import type { Student } from "@/types";

export default function AttendancePage() {
  const [classId, setClassId] = useState("");
  const [date, setDate] = useState(new Date().toISOString().split("T")[0]);
  const [records, setRecords] = useState<Record<string, string>>({});
  const [reasons, setReasons] = useState<Record<string, string>>({});

  const { data: classesResp } = useClasses({ page_size: 100 });
  const classes: any[] = classesResp?.items || [];
  const { data: students, isLoading } = useStudents({ class_id: classId || undefined, page_size: 100 });
  const { data: attendance } = useAttendance({ class_id: classId || undefined, date });
  const { data: reasonList } = useAbsenceReasons(true);
  const markAttendance = useMarkAttendance();

  const items = students?.items || [];
  const existingRecords = attendance?.items || (Array.isArray(attendance) ? attendance : []);
  const reasonOptions: any[] = reasonList || [];

  const handleMark = (studentId: string, status: string) => {
    setRecords((prev) => ({ ...prev, [studentId]: status }));
    if (status === "present") setReasons((prev) => { const n = { ...prev }; delete n[studentId]; return n; });
  };

  const markAll = (status: string) => {
    const next: Record<string, string> = {};
    items.forEach((st: any) => { next[st.id] = status; });
    setRecords((prev) => ({ ...prev, ...next }));
    if (status === "present") setReasons({});
  };

  const handleSubmit = () => {
    const payload = Object.entries(records).map(([student_id, status]) => ({
      student_id, status, ...(classId ? { class_id: classId } : {}), reason_id: reasons[student_id] || null,
    }));
    if (payload.length === 0) return;
    markAttendance.mutate({ records: payload, date });
  };

  const getStatus = (studentId: string) => {
    if (records[studentId]) return records[studentId];
    const existing = existingRecords.find((r: any) => r.student_id === studentId);
    return existing?.status || "";
  };

  const getReason = (studentId: string) => {
    if (reasons[studentId] !== undefined) return reasons[studentId];
    const existing = existingRecords.find((r: any) => r.student_id === studentId);
    return existing?.reason_id || "";
  };

  const statusBtn = (studentId: string, status: string, icon: any, label: string, color: string) => {
    const Icon = icon;
    const active = getStatus(studentId) === status;
    return (
      <button onClick={() => handleMark(studentId, status)} className={cn("flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border", active ? color : "border-slate-200 text-slate-400 hover:bg-slate-50")}>
        <Icon size={12} />{label}
      </button>
    );
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span className="text-brand-600 font-semibold">Attendance</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Attendance Tracker</h1>
        <p className="text-slate-500 text-sm mt-0.5">Mark and track daily student attendance.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: "Students", value: items.length || "—" },
          { label: "Present", value: Object.values(records).filter((s) => s === "present").length + existingRecords.filter((r: any) => r.status === "present" && !records[r.student_id]).length || "0" },
          { label: "Absent", value: Object.values(records).filter((s) => s === "absent").length + existingRecords.filter((r: any) => r.status === "absent" && !records[r.student_id]).length || "0" },
          { label: "Late", value: Object.values(records).filter((s) => s === "late").length + existingRecords.filter((r: any) => r.status === "late" && !records[r.student_id]).length || "0" },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white rounded-xl border border-slate-200 p-4"><p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">{label}</p><p className="text-xl font-black text-slate-900">{value}</p></div>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6 flex flex-wrap items-end gap-4">
        <div className="min-w-[200px]"><label className="label">Class</label><select value={classId} onChange={(e) => { setClassId(e.target.value); setRecords({}); setReasons({}); }} className="input"><option value="">Select a class…</option>{classes.map((c: any) => (<option key={c.id} value={c.id}>{c.name}</option>))}</select></div>
        <div><label className="label">Date</label><input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="input" /></div>
        <div className="flex gap-2">
          <button type="button" onClick={() => markAll("present")} disabled={!classId || items.length === 0} className="btn-secondary gap-1.5 disabled:opacity-50">
            <Check size={15} />Mark all present
          </button>
          <button type="button" onClick={() => markAll("absent")} disabled={!classId || items.length === 0} className="btn-ghost border border-slate-200 gap-1.5 disabled:opacity-50">
            <XIcon size={15} />All absent
          </button>
        </div>
        <button onClick={handleSubmit} disabled={markAttendance.isPending || !classId || Object.keys(records).length === 0} className="btn-primary gap-2">
          {markAttendance.isPending && <Loader2 size={15} className="animate-spin" />}Save Attendance
        </button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Student ID", "Status", "Mark"].map((h) => (<th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>))}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? Array.from({ length: 8 }).map((_, i) => (<tr key={i}><td colSpan={4} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-48" /></td></tr>))
            : items.length === 0 ? (<tr><td colSpan={4} className="px-5 py-16 text-center text-slate-400 text-sm"><ClipboardList size={32} className="mx-auto mb-2 opacity-50" />{classId ? "No students in this class." : "Choose a class to load its pupils."}</td></tr>)
            : items.map((s: Student) => (
              <tr key={s.id} className="hover:bg-slate-50/70 transition-colors">
                <td className="px-5 py-3.5 text-sm font-bold text-slate-900">{s.first_name} {s.last_name}</td>
                <td className="px-5 py-3.5 text-xs font-mono text-slate-500">{s.student_id}</td>
                <td className="px-5 py-3.5">
                  {getStatus(s.id) ? (<span className={cn("badge capitalize", getStatus(s.id) === "present" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : getStatus(s.id) === "absent" ? "bg-red-50 text-red-700 border-red-200" : "bg-amber-50 text-amber-700 border-amber-200")}>{getStatus(s.id)}</span>) : (<span className="text-xs text-slate-400">Not marked</span>)}
                </td>
                <td className="px-5 py-3.5">
                  <div className="flex items-center gap-2">
                    {statusBtn(s.id, "present", Check, "Present", "bg-emerald-50 text-emerald-700 border-emerald-200")}
                    {statusBtn(s.id, "absent", XIcon, "Absent", "bg-red-50 text-red-700 border-red-200")}
                    {statusBtn(s.id, "late", Clock, "Late", "bg-amber-50 text-amber-700 border-amber-200")}
                  </div>
                  {(getStatus(s.id) === "absent" || getStatus(s.id) === "late") && reasonOptions.length > 0 && (
                    <select value={getReason(s.id)} onChange={(e) => setReasons((prev) => ({ ...prev, [s.id]: e.target.value }))} className="input mt-2 max-w-[220px] text-xs py-1.5">
                      <option value="">— Reason (optional) —</option>
                      {reasonOptions.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
                    </select>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
