"use client";

import { useMemo, useState } from "react";
import { useMyTeachingAssignments, useReportEntryGrid, useSaveReportEntry, useTerms } from "@/hooks/usePlatform";
import { cn } from "@/lib/utils";
import { Loader2, Save, NotebookPen } from "lucide-react";

export default function MakeReportPage() {
  const { data: assignments = [], isLoading: loadingA } = useMyTeachingAssignments();
  const { data: terms = [] } = useTerms();
  const [pair, setPair] = useState("");   // "classId|subjectId"
  const [termId, setTermId] = useState("");
  const [classId, subjectId] = pair ? pair.split("|") : ["", ""];
  const ready = !!classId && !!subjectId && !!termId;
  const { data: grid, isLoading } = useReportEntryGrid({ class_id: classId, subject_id: subjectId, term_id: termId });
  const save = useSaveReportEntry();
  const [draft, setDraft] = useState<Record<string, Record<string, string>>>({});

  const scores = useMemo(() => {
    const seed: Record<string, Record<string, string>> = {};
    (grid?.students ?? []).forEach((s: any) => {
      seed[s.id] = {};
      (grid?.assessments ?? []).forEach((a: any) => { const v = grid?.scores?.[s.id]?.[a.id]; seed[s.id][a.id] = v == null ? "" : String(v); });
    });
    return seed;
  }, [grid]);
  const cur = (sid: string, aid: string) => (draft[sid]?.[aid] ?? scores[sid]?.[aid] ?? "");
  const setCell = (sid: string, aid: string, v: string) => setDraft((p) => ({ ...p, [sid]: { ...(p[sid] ?? scores[sid] ?? {}), [aid]: v } }));

  const submit = () => {
    const items: any[] = [];
    (grid?.students ?? []).forEach((s: any) => (grid?.assessments ?? []).forEach((a: any) => {
      const v = cur(s.id, a.id);
      items.push({ student_id: s.id, assessment_id: a.id, score: v === "" ? null : Number(v) });
    }));
    save.mutate({ subject_id: subjectId, class_id: classId, items }, { onSuccess: () => setDraft({}) });
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Secondary School Report</span><span>/</span><span className="text-brand-600 font-semibold">Make Report</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2"><NotebookPen size={22} className="text-brand-600" /> Make Report</h1>
      <p className="text-slate-500 text-sm mb-5">Enter scores for the subjects you teach. You only see the classes and subjects assigned to you on the timetable.</p>

      {loadingA ? (
        <div className="py-16 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : (assignments as any[]).length === 0 ? (
        <div className="bg-white rounded-xl border border-dashed border-slate-200 py-16 text-center text-slate-400">
          <NotebookPen size={30} className="mx-auto mb-3 opacity-40" />
          <p className="text-sm font-semibold text-slate-600">No teaching assignments</p>
          <p className="text-xs mt-1">You aren&apos;t assigned any class/subject on the timetable yet. Ask an administrator to assign you.</p>
        </div>
      ) : (
        <>
          <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3 mb-4">
            <div className="flex-1 min-w-[240px]"><label className="label">My class &amp; subject</label>
              <select value={pair} onChange={(e) => setPair(e.target.value)} className="input">
                <option value="">— Select —</option>
                {(assignments as any[]).map((a) => <option key={`${a.class_id}|${a.subject_id}`} value={`${a.class_id}|${a.subject_id}`}>{a.class_name} · {a.subject_name}</option>)}
              </select>
            </div>
            <div><label className="label">Term</label><select value={termId} onChange={(e) => setTermId(e.target.value)} className="input"><option value="">— Select —</option>{(terms as any[]).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
            {ready && grid && (grid.students?.length ?? 0) > 0 && <button onClick={submit} disabled={save.isPending} className="btn-primary gap-2 ml-auto">{save.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Save Scores</button>}
          </div>

          {!ready ? (
            <p className="text-sm text-slate-400 py-10 text-center bg-white rounded-xl border border-slate-200">Pick a class/subject and term to enter scores.</p>
          ) : isLoading || !grid ? (
            <div className="py-14 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
          ) : (grid.assessments?.length ?? 0) === 0 ? (
            <p className="text-sm text-slate-400 py-10 text-center bg-white rounded-xl border border-slate-200">No assessments configured for this term. Ask an administrator to set up assessments.</p>
          ) : (grid.students?.length ?? 0) === 0 ? (
            <p className="text-sm text-slate-400 py-10 text-center bg-white rounded-xl border border-slate-200">No pupils in this class.</p>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
              <table className="w-full text-left">
                <thead><tr className="bg-slate-50/80 border-b border-slate-100">
                  <th className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">Pupil</th>
                  {grid.assessments.map((a: any) => <th key={a.id} className="px-3 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 text-center">{a.name}<span className="block font-normal text-slate-400">/{Number(a.max_score)}</span></th>)}
                </tr></thead>
                <tbody className="divide-y divide-slate-50">
                  {grid.students.map((s: any) => (
                    <tr key={s.id} className="hover:bg-slate-50/70">
                      <td className="px-4 py-2 text-sm font-semibold text-slate-800 whitespace-nowrap">{s.name}</td>
                      {grid.assessments.map((a: any) => (
                        <td key={a.id} className="px-2 py-1.5 text-center">
                          <input type="number" value={cur(s.id, a.id)} onChange={(e) => setCell(s.id, a.id, e.target.value)}
                            className="input w-16 py-1 text-center text-sm" max={Number(a.max_score)} min={0} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
