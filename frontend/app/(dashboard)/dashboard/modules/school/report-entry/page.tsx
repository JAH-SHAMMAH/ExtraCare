"use client";

import { useEffect, useState } from "react";
import { useClasses, useSubjects } from "@/hooks/useSchool";
import { useTerms, useReportEntryGrid, useSaveReportEntry } from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { Loader2, NotebookPen, Save } from "lucide-react";

export default function ReportEntryPage() {
  const canWrite = useHasPermission("school:reports:write");
  const classesData: any = useClasses({ page_size: 200 }).data;
  const classes: any[] = classesData?.items ?? classesData ?? [];
  const subjectsData: any = useSubjects({ page_size: 200 }).data;
  const subjects: any[] = subjectsData?.items ?? subjectsData ?? [];
  const { data: terms = [] } = useTerms();

  const [classId, setClassId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [termId, setTermId] = useState("");
  const { data: grid, isLoading } = useReportEntryGrid({ class_id: classId, subject_id: subjectId, term_id: termId });
  const save = useSaveReportEntry();

  // draft[studentId][assessmentId] = string
  const [draft, setDraft] = useState<Record<string, Record<string, string>>>({});
  useEffect(() => {
    if (!grid) return;
    const seed: Record<string, Record<string, string>> = {};
    for (const s of grid.students) {
      seed[s.id] = {};
      const row = grid.scores?.[s.id] || {};
      for (const a of grid.assessments) seed[s.id][a.id] = row[a.id] != null ? String(row[a.id]) : "";
    }
    setDraft(seed);
  }, [grid]);

  const setCell = (sid: string, aid: string, v: string) =>
    setDraft((p) => ({ ...p, [sid]: { ...p[sid], [aid]: v } }));

  const submit = () => {
    if (!grid) return;
    const items: any[] = [];
    for (const s of grid.students) {
      for (const a of grid.assessments) {
        const raw = draft[s.id]?.[a.id];
        items.push({ student_id: s.id, assessment_id: a.id, score: raw === "" || raw == null ? null : Number(raw) });
      }
    }
    save.mutate({ subject_id: subjectId, items });
  };

  const ready = grid && grid.assessments.length > 0 && grid.students.length > 0;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Secondary School Report</span><span>/</span><span className="text-brand-600 font-semibold">Report Entry</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2"><NotebookPen size={22} className="text-brand-600" /> Report Entry</h1>
      <p className="text-slate-500 text-sm mb-5">Enter pupils&apos; marks for each assessment. These feed the cumulative columns and the report card.</p>

      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3 mb-5">
        <div><label className="label">Class</label><select value={classId} onChange={(e) => setClassId(e.target.value)} className="input"><option value="">— Select —</option>{classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
        <div><label className="label">Subject</label><select value={subjectId} onChange={(e) => setSubjectId(e.target.value)} className="input"><option value="">— Select —</option>{subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
        <div><label className="label">Term</label><select value={termId} onChange={(e) => setTermId(e.target.value)} className="input"><option value="">— Select —</option>{(terms as any[]).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
        {canWrite && ready && <button onClick={submit} disabled={save.isPending} className="btn-primary gap-2 ml-auto">{save.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Save Scores</button>}
      </div>

      {!classId || !subjectId || !termId ? (
        <div className="bg-white rounded-xl border border-dashed border-slate-200 py-16 text-center text-slate-400"><NotebookPen size={30} className="mx-auto mb-3 opacity-40" /><p className="text-sm">Choose a class, subject and term to enter marks.</p></div>
      ) : isLoading ? (
        <div className="py-16 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : !grid || grid.students.length === 0 ? (
        <p className="text-sm text-slate-400 py-14 text-center bg-white rounded-xl border border-slate-200">No pupils in this class.</p>
      ) : grid.assessments.length === 0 ? (
        <p className="text-sm text-slate-400 py-14 text-center bg-white rounded-xl border border-slate-200">No assessments defined for this term/level. Set them up under Report Setup → Assessment.</p>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-100">
                <th className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 sticky left-0 bg-slate-50">Pupil</th>
                {grid.assessments.map((a: any) => (
                  <th key={a.id} className="px-3 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 text-center whitespace-nowrap">{a.name}<span className="block font-normal text-slate-400">/{Number(a.max_score)}</span></th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {grid.students.map((s: any) => (
                <tr key={s.id} className="hover:bg-slate-50/70">
                  <td className="px-4 py-2 text-sm font-semibold text-slate-800 whitespace-nowrap sticky left-0 bg-white">{s.name}</td>
                  {grid.assessments.map((a: any) => (
                    <td key={a.id} className="px-2 py-2 text-center">
                      <input type="number" disabled={!canWrite} value={draft[s.id]?.[a.id] ?? ""} onChange={(e) => setCell(s.id, a.id, e.target.value)}
                        max={Number(a.max_score)} min={0}
                        className="input w-16 py-1 text-sm text-center tabular-nums" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
