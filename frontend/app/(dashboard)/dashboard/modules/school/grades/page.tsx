"use client";

import { useState } from "react";
import { useStudents, useSubmitGrades } from "@/hooks/useSchool";
import { useTermState } from "@/hooks/usePlatform";
import { BookOpen, Loader2, Save } from "lucide-react";
import { TERMS, DEFAULT_TERM } from "@/lib/terms";
import type { Student } from "@/types";

export default function GradebookPage() {
  const [classId, setClassId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [term, setTerm] = useTermState(DEFAULT_TERM);
  const [grades, setGrades] = useState<Record<string, { score: string; grade: string; remarks: string }>>({});

  const { data: students, isLoading } = useStudents({ class_id: classId || undefined, page_size: 100 });
  const submitGrades = useSubmitGrades();

  const items = students?.items || [];

  const updateGrade = (studentId: string, field: string, value: string) => {
    setGrades((prev) => ({ ...prev, [studentId]: { ...(prev[studentId] || { score: "", grade: "", remarks: "" }), [field]: value } }));
  };

  const handleSubmit = () => {
    const payload = Object.entries(grades).filter(([, g]) => g.score).map(([student_id, g]) => ({ student_id, subject_id: subjectId, score: parseFloat(g.score), grade: g.grade, remarks: g.remarks, term }));
    if (payload.length === 0) return;
    submitGrades.mutate(payload);
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span className="text-brand-600 font-semibold">Gradebook</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Gradebook</h1>
        <p className="text-slate-500 text-sm mt-0.5">Enter and manage student grades by subject.</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6 flex flex-wrap items-end gap-4">
        <div><label className="label">Class ID</label><input value={classId} onChange={(e) => setClassId(e.target.value)} placeholder="Enter class ID" className="input w-48" /></div>
        <div><label className="label">Subject ID</label><input value={subjectId} onChange={(e) => setSubjectId(e.target.value)} placeholder="Enter subject ID" className="input w-48" /></div>
        <div><label className="label">Term</label><select value={term} onChange={(e) => setTerm(e.target.value)} className="input">{TERMS.map((t) => (<option key={t} value={t}>{t}</option>))}</select></div>
        <button onClick={handleSubmit} disabled={submitGrades.isPending || Object.keys(grades).length === 0} className="btn-primary gap-2">
          {submitGrades.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}Submit Grades
        </button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Student ID", "Score", "Grade", "Remarks"].map((h) => (<th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>))}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? Array.from({ length: 8 }).map((_, i) => (<tr key={i}><td colSpan={5} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-48" /></td></tr>))
            : items.length === 0 ? (<tr><td colSpan={5} className="px-5 py-16 text-center text-slate-400 text-sm"><BookOpen size={32} className="mx-auto mb-2 opacity-50" />{classId ? "No students found." : "Enter a Class ID to load students."}</td></tr>)
            : items.map((s: Student) => (
              <tr key={s.id} className="hover:bg-slate-50/70">
                <td className="px-5 py-3 text-sm font-bold text-slate-900">{s.first_name} {s.last_name}</td>
                <td className="px-5 py-3 text-xs font-mono text-slate-500">{s.student_id}</td>
                <td className="px-5 py-3"><input type="number" min="0" max="100" value={grades[s.id]?.score || ""} onChange={(e) => updateGrade(s.id, "score", e.target.value)} placeholder="0-100" className="input w-20 text-sm" /></td>
                <td className="px-5 py-3"><input value={grades[s.id]?.grade || ""} onChange={(e) => updateGrade(s.id, "grade", e.target.value)} placeholder="A/B/C..." className="input w-16 text-sm" /></td>
                <td className="px-5 py-3"><input value={grades[s.id]?.remarks || ""} onChange={(e) => updateGrade(s.id, "remarks", e.target.value)} placeholder="Optional remarks" className="input text-sm" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
