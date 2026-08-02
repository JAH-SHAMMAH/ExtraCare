"use client";

import { useState } from "react";
import { useClasses } from "@/hooks/useSchool";
import { useTerms, useSubTerms, useBroadsheet, useReportCard } from "@/hooks/usePlatform";
import { Loader2, Printer, FileText } from "lucide-react";

export function BulkPrintTab() {
  const classesData: any = useClasses({ page_size: 200 }).data;
  const classes: any[] = classesData?.items ?? classesData ?? [];
  const { data: terms = [] } = useTerms();
  const { data: subs = [] } = useSubTerms();
  const [classId, setClassId] = useState("");
  const [termId, setTermId] = useState("");
  const [subTermId, setSubTermId] = useState("");
  const [studentId, setStudentId] = useState("");
  const { data: bs } = useBroadsheet({ class_id: classId, term_id: termId, sub_term_id: subTermId });
  const { data: card, isLoading } = useReportCard({ student_id: studentId, term_id: termId, sub_term_id: subTermId });

  const students: any[] = bs?.rows ?? [];
  const num = (v: any) => (v == null ? "–" : Number(v));

  return (
    <div className="space-y-4">
      <style>{`@media print { body * { visibility: hidden !important; } #report-card, #report-card * { visibility: visible !important; } #report-card { position: absolute; left: 0; top: 0; width: 100%; } }`}</style>

      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3 no-print">
        <div><label className="label">Class</label><select value={classId} onChange={(e) => { setClassId(e.target.value); setStudentId(""); }} className="input"><option value="">— Select —</option>{classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
        <div><label className="label">Term</label><select value={termId} onChange={(e) => setTermId(e.target.value)} className="input"><option value="">— Select —</option>{(terms as any[]).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
        <div><label className="label">Sub-term</label><select value={subTermId} onChange={(e) => setSubTermId(e.target.value)} className="input"><option value="">— Select —</option>{(subs as any[]).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
        <div><label className="label">Student</label><select value={studentId} onChange={(e) => setStudentId(e.target.value)} disabled={!bs} className="input min-w-[180px]"><option value="">— Select —</option>{students.map((r) => <option key={r.student_id} value={r.student_id}>{r.student_name}</option>)}</select></div>
        {card && <button onClick={() => window.print()} className="btn-primary gap-2 ml-auto"><Printer size={15} /> Print</button>}
      </div>

      {!studentId ? (
        <div className="bg-white rounded-xl border border-dashed border-slate-200 py-16 text-center text-slate-400 no-print"><FileText size={30} className="mx-auto mb-3 opacity-40" /><p className="text-sm">Choose a class, term, sub-term and student to view the report card.</p></div>
      ) : isLoading || !card ? (
        <div className="py-16 text-center no-print"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : (
        <div id="report-card" className="bg-white rounded-xl border border-slate-300 p-6 max-w-4xl mx-auto text-slate-900">
          <Card card={card} num={num} />
        </div>
      )}
    </div>
  );
}

function Card({ card, num }: { card: any; num: (v: any) => any }) {
  const b = card.branding || {};
  const attPct = card.attendance_total ? Math.round((card.attendance_present / card.attendance_total) * 100) : null;
  return (
    <>
      <div className="flex items-center gap-4 border-b-2 border-slate-800 pb-3">
        {b.logo_url ? <img src={b.logo_url} alt="" className="w-16 h-16 object-contain" /> : <div className="w-16 h-16" />}
        <div className="flex-1 text-center">
          <h2 className="text-xl font-black tracking-tight">{b.school_name_alias || "SCHOOL REPORT"}</h2>
          {b.school_address && <p className="text-[11px] text-slate-600">{b.school_address}</p>}
          {b.school_email && <p className="text-[11px] text-slate-600">Email: {b.school_email}</p>}
          <p className="text-xs font-bold mt-1">{card.report_title} {b.school_name_alias ? "" : ""}</p>
        </div>
        {card.photo_url ? <img src={card.photo_url} alt="" className="w-16 h-20 object-cover border border-slate-300" /> : <div className="w-16 h-20 border border-dashed border-slate-200" />}
      </div>

      <table className="w-full text-xs mt-3 border border-slate-300">
        <tbody>
          <tr>
            <td className="border border-slate-300 px-2 py-1 font-bold bg-slate-50">Name</td>
            <td className="border border-slate-300 px-2 py-1">{card.student_name}</td>
            <td className="border border-slate-300 px-2 py-1 font-bold bg-slate-50">Class</td>
            <td className="border border-slate-300 px-2 py-1">{card.class_name || "—"}</td>
            <td className="border border-slate-300 px-2 py-1 font-bold bg-slate-50">Position</td>
            <td className="border border-slate-300 px-2 py-1">{card.position} of {card.class_size}</td>
          </tr>
          <tr>
            <td className="border border-slate-300 px-2 py-1 font-bold bg-slate-50">Admission No</td>
            <td className="border border-slate-300 px-2 py-1">{card.admission_no || "—"}</td>
            <td className="border border-slate-300 px-2 py-1 font-bold bg-slate-50">Days Present</td>
            <td className="border border-slate-300 px-2 py-1">{card.attendance_present ?? "—"}{card.attendance_total ? ` / ${card.attendance_total}` : ""}</td>
            <td className="border border-slate-300 px-2 py-1 font-bold bg-slate-50">% Attendance</td>
            <td className="border border-slate-300 px-2 py-1">{attPct != null ? `${attPct}%` : "—"}</td>
          </tr>
        </tbody>
      </table>

      <table className="w-full text-xs mt-3 border border-slate-300">
        <thead>
          <tr className="bg-slate-100">
            <th className="border border-slate-300 px-2 py-1 text-left">Subject</th>
            {card.columns.map((c: any) => <th key={c.key} className="border border-slate-300 px-2 py-1 text-center">{c.name}{c.max_score != null ? <span className="block font-normal text-[9px] text-slate-500">/{num(c.max_score)}</span> : null}</th>)}
            <th className="border border-slate-300 px-2 py-1 text-center">Grade</th>
            <th className="border border-slate-300 px-2 py-1 text-center">Remark</th>
            <th className="border border-slate-300 px-2 py-1 text-center">Arm Avg</th>
          </tr>
        </thead>
        <tbody>
          {card.subjects.map((r: any) => (
            <tr key={r.subject_id}>
              <td className="border border-slate-300 px-2 py-1 font-semibold">{r.subject_name}</td>
              {card.columns.map((c: any) => <td key={c.key} className="border border-slate-300 px-2 py-1 text-center tabular-nums">{num(r.values[c.key])}</td>)}
              <td className="border border-slate-300 px-2 py-1 text-center font-bold">{r.grade || "–"}</td>
              <td className="border border-slate-300 px-2 py-1 text-center">{r.remark || "–"}</td>
              <td className="border border-slate-300 px-2 py-1 text-center tabular-nums">{num(r.subject_arm_average)}</td>
            </tr>
          ))}
          {card.subjects.length === 0 && <tr><td colSpan={card.columns.length + 4} className="border border-slate-300 px-2 py-3 text-center text-slate-400">No marks entered for this pupil.</td></tr>}
        </tbody>
      </table>

      <div className="grid grid-cols-3 gap-3 mt-3 text-xs">
        <div className="border border-slate-300 p-2 text-center"><p className="font-bold text-slate-500">Student Average</p><p className="text-lg font-black">{num(card.average)}</p></div>
        <div className="border border-slate-300 p-2 text-center"><p className="font-bold text-slate-500">Total Score</p><p className="text-lg font-black">{num(card.total)}</p></div>
        <div className="border border-slate-300 p-2 text-center"><p className="font-bold text-slate-500">Overall Grade</p><p className="text-lg font-black">{card.grade || "–"}</p></div>
      </div>

      {card.bands.length > 0 && (
        <div className="mt-3 text-[10px]">
          <p className="font-bold text-slate-500 uppercase tracking-widest mb-1">Grading Scale</p>
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {card.bands.map((bnd: any) => <span key={bnd.grade}><b>{bnd.grade}</b> {bnd.min_score != null ? `${num(bnd.min_score)}–${num(bnd.max_score)}` : ""}{bnd.remark ? ` ${bnd.remark}` : ""}</span>)}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-6 mt-6 text-xs">
        <div><p className="border-t border-slate-400 pt-1 mt-8">{b.class_teacher_title || "Class Teacher"} Signature</p></div>
        <div><p className="border-t border-slate-400 pt-1 mt-8">{b.school_head_title || "Principal"}{b.school_head_name ? ` — ${b.school_head_name}` : ""}</p></div>
      </div>
    </>
  );
}
