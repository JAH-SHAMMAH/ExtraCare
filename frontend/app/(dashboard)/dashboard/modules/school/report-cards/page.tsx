"use client";

import { useState } from "react";
import { useStudents, useReportCard } from "@/hooks/useSchool";
import { cn, getInitials } from "@/lib/utils";
import { FileText, Search, Printer, Loader2 } from "lucide-react";
import type { Student } from "@/types";

export default function ReportCardsPage() {
  const [search, setSearch] = useState("");
  const [selectedStudent, setSelectedStudent] = useState("");
  const [term, setTerm] = useState("1st Term");

  const { data: students, isLoading: studentsLoading } = useStudents({ search: search || undefined, page_size: 50 });
  const { data: reportCard, isLoading: rcLoading } = useReportCard(selectedStudent, term);

  const items = students?.items || [];

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span className="text-brand-600 font-semibold">Report Cards</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Report Cards</h1>
        <p className="text-slate-500 text-sm mt-0.5">View and print student report cards.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Student list */}
        <div>
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
          <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4 flex items-center justify-between">
            <select value={term} onChange={(e) => setTerm(e.target.value)} className="input w-40"><option>1st Term</option><option>2nd Term</option><option>3rd Term</option></select>
            {reportCard && (<button onClick={() => window.print()} className="btn-secondary gap-2"><Printer size={14} />Print</button>)}
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6">
            {!selectedStudent ? (
              <div className="py-16 text-center text-slate-400"><FileText size={40} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">Select a student</p><p className="text-sm mt-1">Choose a student from the list to view their report card.</p></div>
            ) : rcLoading ? (
              <div className="py-16 text-center"><Loader2 size={24} className="animate-spin text-slate-400 mx-auto" /></div>
            ) : !reportCard ? (
              <div className="py-16 text-center text-slate-400"><p className="font-semibold">No report card available</p><p className="text-sm mt-1">No grades have been submitted for this term.</p></div>
            ) : (
              <div>
                <div className="text-center mb-6 pb-4 border-b border-slate-100">
                  <h2 className="text-lg font-bold text-slate-900">{reportCard.student?.first_name} {reportCard.student?.last_name}</h2>
                  <p className="text-sm text-slate-500">{reportCard.term} — {reportCard.academic_year}</p>
                </div>

                <table className="w-full text-left mb-6">
                  <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Subject", "Score", "Grade", "Remarks", "Teacher"].map((h) => (<th key={h} className="px-4 py-2.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>))}</tr></thead>
                  <tbody className="divide-y divide-slate-50">
                    {reportCard.subjects?.map((s: any, i: number) => (
                      <tr key={i}><td className="px-4 py-2.5 text-sm font-medium text-slate-800">{s.subject_name}</td><td className="px-4 py-2.5 text-sm text-slate-600">{s.score}</td><td className="px-4 py-2.5"><span className="badge bg-brand-50 text-brand-700 border-brand-200">{s.grade}</span></td><td className="px-4 py-2.5 text-xs text-slate-500">{s.remarks || "—"}</td><td className="px-4 py-2.5 text-xs text-slate-500">{s.teacher_name || "—"}</td></tr>
                    ))}
                  </tbody>
                </table>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-slate-50 rounded-lg">
                  <div><p className="text-[10px] font-bold uppercase text-slate-400">Total</p><p className="text-lg font-bold text-slate-900">{reportCard.total_score}</p></div>
                  <div><p className="text-[10px] font-bold uppercase text-slate-400">Average</p><p className="text-lg font-bold text-slate-900">{reportCard.average?.toFixed(1)}</p></div>
                  <div><p className="text-[10px] font-bold uppercase text-slate-400">Position</p><p className="text-lg font-bold text-slate-900">{reportCard.position || "—"}{reportCard.class_size ? ` / ${reportCard.class_size}` : ""}</p></div>
                </div>

                {(reportCard.teacher_remark || reportCard.principal_remark) && (
                  <div className="mt-4 space-y-2">
                    {reportCard.teacher_remark && (<div className="p-3 bg-blue-50 rounded-lg"><p className="text-[10px] font-bold uppercase text-blue-500">Teacher&apos;s Remark</p><p className="text-sm text-blue-800">{reportCard.teacher_remark}</p></div>)}
                    {reportCard.principal_remark && (<div className="p-3 bg-purple-50 rounded-lg"><p className="text-[10px] font-bold uppercase text-purple-500">Principal&apos;s Remark</p><p className="text-sm text-purple-800">{reportCard.principal_remark}</p></div>)}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
