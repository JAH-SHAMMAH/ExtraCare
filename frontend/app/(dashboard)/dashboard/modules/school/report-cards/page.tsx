"use client";

import { useState, useEffect } from "react";
import { useStudents, useReportCard, useSaveReportMeta } from "@/hooks/useSchool";
import { useTermState } from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, getInitials } from "@/lib/utils";
import { FileText, Search, Printer, Loader2, Pencil, X } from "lucide-react";
import { PrintLetterhead } from "@/components/branding/Brand";
import { TERMS, DEFAULT_TERM } from "@/lib/terms";
import type { Student } from "@/types";

export default function ReportCardsPage() {
  const [search, setSearch] = useState("");
  const [selectedStudent, setSelectedStudent] = useState("");
  const [term, setTerm] = useTermState(DEFAULT_TERM);
  const canWrite = useHasPermission("school:reports:write");

  const { data: students, isLoading: studentsLoading } = useStudents({ search: search || undefined, page_size: 50 });
  const { data: reportCard, isLoading: rcLoading } = useReportCard(selectedStudent, term);

  const items = students?.items || [];

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8 no-print">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span className="text-brand-600 font-semibold">Report Cards</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Report Cards</h1>
        <p className="text-slate-500 text-sm mt-0.5">View, complete and print student report cards.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Student list */}
        <div className="no-print">
          <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4">
            <div className="relative"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search students..." className="input pl-9" /></div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden max-h-[600px] overflow-y-auto">
            {studentsLoading ? Array.from({ length: 8 }).map((_, i) => (<div key={i} className="px-4 py-3 border-b border-slate-50"><div className="h-4 bg-slate-100 rounded animate-pulse w-32" /></div>))
            : items.length === 0 ? (<div className="p-8 text-center text-slate-400 text-sm">No students found.</div>)
            : items.map((s: Student) => (
              <button key={s.id} onClick={() => setSelectedStudent(s.id)} className={cn("w-full flex items-center gap-3 px-4 py-3 border-b border-slate-50 hover:bg-slate-50 transition-colors text-left", selectedStudent === s.id && "bg-brand-50 border-brand-100")}>
                <div className="w-8 h-8 rounded-lg bg-indigo-600/10 flex items-center justify-center text-indigo-700 text-xs font-bold shrink-0">{getInitials(`${s.first_name} ${s.last_name}`)}</div>
                <div className="min-w-0"><p className="text-sm font-medium text-slate-900 truncate">{s.first_name} {s.last_name}</p><p className="text-xs text-slate-400">{s.student_id}</p></div>
              </button>
            ))}
          </div>
        </div>

        {/* Report card */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4 flex items-center justify-between gap-3 no-print">
            <select value={term} onChange={(e) => setTerm(e.target.value)} className="input w-40">{TERMS.map((t) => (<option key={t} value={t}>{t}</option>))}</select>
            {reportCard && (<button onClick={() => window.print()} className="btn-secondary gap-2"><Printer size={14} />Print</button>)}
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6 print:border-0 print:p-0">
            {!selectedStudent ? (
              <div className="py-16 text-center text-slate-400"><FileText size={40} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">Select a student</p><p className="text-sm mt-1">Choose a student from the list to view their report card.</p></div>
            ) : rcLoading ? (
              <div className="py-16 text-center"><Loader2 size={24} className="animate-spin text-slate-400 mx-auto" /></div>
            ) : !reportCard ? (
              <div className="py-16 text-center text-slate-400"><p className="font-semibold">No report card available</p><p className="text-sm mt-1">No grades have been submitted for this term.</p></div>
            ) : (
              <ReportCardView card={reportCard} term={term} studentId={selectedStudent} canWrite={canWrite} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ReportCardView({ card, term, studentId, canWrite }: { card: any; term: string; studentId: string; canWrite: boolean }) {
  const [editing, setEditing] = useState(false);
  const subjects: any[] = card.subjects || [];
  const hasAttendance = card.attendance_total != null;

  return (
    <div>
      {/* Staff-only controls (never printed) */}
      {canWrite && (
        <div className="flex justify-end mb-3 no-print">
          <button onClick={() => setEditing((v) => !v)} className="btn-secondary gap-2 text-xs py-1.5">
            {editing ? <><X size={13} /> Close</> : <><Pencil size={13} /> Edit report details</>}
          </button>
        </div>
      )}
      {editing && canWrite && <ReportMetaForm card={card} term={term} studentId={studentId} onDone={() => setEditing(false)} />}

      <PrintLetterhead title="Report Card" subtitle={`${card.term || term}${card.academic_year ? ` — ${card.academic_year}` : ""}`} />

      {/* Header */}
      <div className="text-center mb-5 pb-4 border-b border-slate-100">
        <h2 className="text-lg font-bold text-slate-900">{card.student?.first_name} {card.student?.last_name}</h2>
        <p className="text-sm text-slate-500">
          {[card.class_name, card.level, card.section && `Section ${card.section}`].filter(Boolean).join(" · ") || "—"}
        </p>
        <p className="text-xs text-slate-400 mt-0.5">{card.term || term}{card.academic_year ? ` — ${card.academic_year}` : ""}</p>
      </div>

      {/* Marks table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left mb-5">
          <thead>
            <tr className="bg-slate-50/80 border-b border-slate-100">
              {["Subject", "CA (40)", "Exam (60)", "Total", "Grade", "Remarks", "Teacher"].map((h) => (
                <th key={h} className="px-3 py-2.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {subjects.length === 0 ? (
              <tr><td colSpan={7} className="px-3 py-6 text-center text-sm text-slate-400">No grades recorded for this term.</td></tr>
            ) : subjects.map((s, i) => (
              <tr key={i}>
                <td className="px-3 py-2.5 text-sm font-medium text-slate-800">{s.subject_name || "—"}</td>
                <td className="px-3 py-2.5 text-sm text-slate-600 tabular-nums">{s.ca_score ?? "—"}</td>
                <td className="px-3 py-2.5 text-sm text-slate-600 tabular-nums">{s.exam_score ?? "—"}</td>
                <td className="px-3 py-2.5 text-sm font-semibold text-slate-900 tabular-nums">{s.total ?? "—"}</td>
                <td className="px-3 py-2.5"><span className="badge bg-brand-50 text-brand-700 border-brand-200">{s.grade || "—"}</span></td>
                <td className="px-3 py-2.5 text-xs text-slate-500">{s.remarks || "—"}</td>
                <td className="px-3 py-2.5 text-xs text-slate-500">{s.teacher_name || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-slate-50 rounded-lg">
        <div><p className="text-[10px] font-bold uppercase text-slate-400">Total</p><p className="text-lg font-bold text-slate-900 tabular-nums">{card.total_score ?? "—"}</p></div>
        <div><p className="text-[10px] font-bold uppercase text-slate-400">Average</p><p className="text-lg font-bold text-slate-900 tabular-nums">{card.average != null ? Number(card.average).toFixed(1) : "—"}</p></div>
        <div><p className="text-[10px] font-bold uppercase text-slate-400">Position</p><p className="text-lg font-bold text-slate-900 tabular-nums">{card.position || "—"}{card.class_size ? ` / ${card.class_size}` : ""}</p></div>
        <div><p className="text-[10px] font-bold uppercase text-slate-400">Attendance</p><p className="text-lg font-bold text-slate-900 tabular-nums">{hasAttendance ? `${card.attendance_present ?? 0} / ${card.attendance_total}` : "—"}</p>{hasAttendance && card.attendance_absent != null && <p className="text-[10px] text-slate-400">{card.attendance_absent} absent</p>}</div>
      </div>

      {/* Comments + next term */}
      {(card.teacher_remark || card.principal_remark || card.next_term_begins) && (
        <div className="mt-4 space-y-2">
          {card.teacher_remark && (<div className="p-3 bg-blue-50 rounded-lg"><p className="text-[10px] font-bold uppercase text-blue-500">Class Teacher&apos;s Comment</p><p className="text-sm text-blue-800">{card.teacher_remark}</p></div>)}
          {card.principal_remark && (<div className="p-3 bg-purple-50 rounded-lg"><p className="text-[10px] font-bold uppercase text-purple-500">Head Teacher&apos;s Comment</p><p className="text-sm text-purple-800">{card.principal_remark}</p></div>)}
          {card.next_term_begins && (<p className="text-sm text-slate-600"><span className="font-semibold">Next term begins:</span> {card.next_term_begins}</p>)}
        </div>
      )}
    </div>
  );
}

function ReportMetaForm({ card, term, studentId, onDone }: { card: any; term: string; studentId: string; onDone: () => void }) {
  const save = useSaveReportMeta();
  const [form, setForm] = useState({
    class_teacher_comment: card.teacher_remark || "",
    head_teacher_comment: card.principal_remark || "",
    attendance_present: card.attendance_present ?? "",
    attendance_total: card.attendance_total ?? "",
    next_term_begins: card.next_term_begins || "",
  });
  // Re-seed when switching student/term.
  useEffect(() => {
    setForm({
      class_teacher_comment: card.teacher_remark || "",
      head_teacher_comment: card.principal_remark || "",
      attendance_present: card.attendance_present ?? "",
      attendance_total: card.attendance_total ?? "",
      next_term_begins: card.next_term_begins || "",
    });
  }, [studentId, term]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = () => {
    save.mutate({
      student_id: studentId, term,
      data: {
        class_teacher_comment: form.class_teacher_comment || null,
        head_teacher_comment: form.head_teacher_comment || null,
        attendance_present: form.attendance_present === "" ? null : Number(form.attendance_present),
        attendance_total: form.attendance_total === "" ? null : Number(form.attendance_total),
        next_term_begins: form.next_term_begins || null,
      },
    }, { onSuccess: onDone });
  };

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 mb-5 no-print">
      <h3 className="text-sm font-bold text-slate-800 mb-4">Report details — {term}</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2"><label className="label">Class teacher&apos;s comment</label><textarea value={form.class_teacher_comment} onChange={(e) => setForm({ ...form, class_teacher_comment: e.target.value })} className="input" rows={2} /></div>
        <div className="md:col-span-2"><label className="label">Head teacher&apos;s comment</label><textarea value={form.head_teacher_comment} onChange={(e) => setForm({ ...form, head_teacher_comment: e.target.value })} className="input" rows={2} /></div>
        <div><label className="label">Days present</label><input type="number" min={0} value={form.attendance_present} onChange={(e) => setForm({ ...form, attendance_present: e.target.value })} className="input" /></div>
        <div><label className="label">Total school days</label><input type="number" min={0} value={form.attendance_total} onChange={(e) => setForm({ ...form, attendance_total: e.target.value })} className="input" /></div>
        <div><label className="label">Next term begins</label><input type="date" value={form.next_term_begins} onChange={(e) => setForm({ ...form, next_term_begins: e.target.value })} className="input" /></div>
      </div>
      <div className="flex justify-end gap-3 mt-4">
        <button onClick={onDone} className="btn-secondary">Cancel</button>
        <button onClick={submit} disabled={save.isPending} className="btn-primary gap-2">{save.isPending && <Loader2 size={15} className="animate-spin" />}Save details</button>
      </div>
    </div>
  );
}
