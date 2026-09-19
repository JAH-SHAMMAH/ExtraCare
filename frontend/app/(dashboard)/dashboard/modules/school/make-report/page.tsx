"use client";

import { useEffect, useMemo, useState } from "react";
import { useMyTeachingAssignments, useReportEntryGrid, useSaveReportEntry, useSubTerms, useTerms } from "@/hooks/usePlatform";
import { cn } from "@/lib/utils";
import { classesFromAssignments, defaultSubTermId, subjectsForClass, subTermDisplay } from "@/lib/reportEntry";
import { useSubmitClassReport } from "@/hooks/useAcademics";
import { Loader2, Save, NotebookPen, AlertTriangle, SendHorizonal, CheckCircle2 } from "lucide-react";

export default function MakeReportPage() {
  const { data: assignments = [], isLoading: loadingA } = useMyTeachingAssignments();
  const { data: terms = [] } = useTerms();
  const { data: subTerms = [] } = useSubTerms();
  // Four fields, matching Report Entry (the admin page) rather than the single
  // combined "class - subject" list this page used to carry: a Fairview teacher
  // has 2 classes and 10 subjects, so that one list held 20 entries.
  const [classId, setClassId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [termId, setTermId] = useState("");
  const [subTermId, setSubTermId] = useState("");

  const myClasses = useMemo(() => classesFromAssignments(assignments as any[]), [assignments]);
  // Subject depends on Class: the Timetable assigns per class per subject, so an
  // independent pair could be one this teacher does not teach, which the grid
  // answers with a 403.
  const mySubjects = useMemo(() => subjectsForClass(assignments as any[], classId), [assignments, classId]);

  // Default to Full-Term, as the backend's own resolver does, so the grid opens
  // on exactly the columns it showed before this selector existed.
  useEffect(() => {
    if (!subTermId && (subTerms as any[]).length) setSubTermId(defaultSubTermId(subTerms as any[]));
  }, [subTerms, subTermId]);

  // A subject held from a previous class may not be taught in the new one.
  useEffect(() => {
    if (subjectId && !mySubjects.some((s) => s.id === subjectId)) setSubjectId("");
  }, [mySubjects, subjectId]);

  const ready = !!classId && !!subjectId && !!termId;
  const { data: grid, isLoading } = useReportEntryGrid({ class_id: classId, subject_id: subjectId, term_id: termId, sub_term_id: subTermId || undefined });
  const save = useSaveReportEntry();
  const submitReport = useSubmitClassReport();
  const [draft, setDraft] = useState<Record<string, Record<string, string>>>({});

  const scores = useMemo(() => {
    const seed: Record<string, Record<string, string>> = {};
    (grid?.students ?? []).forEach((s: any) => {
      seed[s.id] = {};
      (grid?.assessments ?? []).forEach((a: any) => { const v = grid?.scores?.[s.id]?.[a.id]; seed[s.id][a.id] = v == null ? "" : String(v); });
    });
    return seed;
  }, [grid]);
  // The grid holds every assessment for the term, across sub-terms — without
  // this two same-named columns (Half-Term EXAM / Full-Term EXAM) are
  // indistinguishable to the teacher filling them in.
  const subTerm = useMemo(() => subTermDisplay(grid?.assessments), [grid]);

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
            <div><label className="label">Term</label><select value={termId} onChange={(e) => setTermId(e.target.value)} className="input"><option value="">— Select —</option>{(terms as any[]).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
            {/* Scopes the grid to one sub-term's assessments. Without it a term
                holding both a Half-Term and a Full-Term "EXAM" showed the
                teacher both columns at once with no way to choose. */}
            <div><label className="label">Sub-Term</label><select value={subTermId} onChange={(e) => setSubTermId(e.target.value)} className="input">{(subTerms as any[]).map((st) => <option key={st.id} value={st.id}>{st.name}</option>)}</select></div>
            <div className="min-w-[180px]"><label className="label">Class</label>
              <select value={classId} onChange={(e) => setClassId(e.target.value)} className="input">
                <option value="">— Select —</option>
                {myClasses.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div className="min-w-[180px]"><label className="label">Subject</label>
              {/* Disabled until a class is chosen: which subjects are available
                  depends on it, so an enabled-but-empty list would just puzzle. */}
              <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)} className="input" disabled={!classId}>
                <option value="">{classId ? "— Select —" : "— Pick a class first —"}</option>
                {mySubjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            {ready && grid && (grid.students?.length ?? 0) > 0 && <button onClick={submit} disabled={save.isPending} className="btn-primary gap-2 ml-auto">{save.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Save Scores</button>}
          </div>

          {/* Above the table, not below it: a class can run to forty pupils, and a
              teacher should not have to scroll past all of them to find out the
              report has already gone in. */}
          {ready && grid?.submission && (grid.students?.length ?? 0) > 0 && (
            (() => {
              const sub = grid.submission;
              const termName = (terms as any[]).find((t) => t.id === termId)?.name;
              const done = sub.stage && sub.stage !== "draft";
              return (
                <div className={cn(
                  "rounded-xl border p-4 mb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3",
                  done ? "border-emerald-200 bg-emerald-50" : "border-slate-200 bg-white",
                )}>
                  <div className="flex items-start gap-2.5">
                    {done
                      ? <CheckCircle2 size={18} className="text-emerald-600 mt-0.5 shrink-0" />
                      : <SendHorizonal size={18} className="text-brand-600 mt-0.5 shrink-0" />}
                    <div>
                      <p className={cn("text-sm font-bold", done ? "text-emerald-900" : "text-slate-800")}>
                        {done ? "Handed in" : "Finished this class?"}
                      </p>
                      {/* `reason` explains a missing button rather than leaving a
                          subject teacher staring at a page that seems incomplete. */}
                      <p className={cn("text-xs mt-0.5", done ? "text-emerald-800" : "text-slate-500")}>
                        {sub.reason
                          ? sub.reason
                          : done
                            ? <>This report is with the office at &ldquo;{sub.stage}&rdquo;.</>
                            : <>Submitting hands the whole class&rsquo;s {termName ? `${termName} ` : ""}report to the office for approval. You can keep saving scores until then.</>}
                      </p>
                    </div>
                  </div>
                  {sub.can_submit && (
                    <button
                      onClick={() => {
                        if (!termName) return;
                        if (confirm(`Submit ${termName} for this class? Scores stay editable until an administrator approves it.`))
                          submitReport.mutate({ class_id: classId, term: termName });
                      }}
                      disabled={submitReport.isPending}
                      className="btn-primary gap-2 shrink-0"
                    >
                      {submitReport.isPending ? <Loader2 size={15} className="animate-spin" /> : <SendHorizonal size={15} />}
                      Submit for approval
                    </button>
                  )}
                </div>
              );
            })()
          )}

          {!ready ? (
            <p className="text-sm text-slate-400 py-10 text-center bg-white rounded-xl border border-slate-200">Pick a class and subject to enter scores.</p>
          ) : isLoading || !grid ? (
            <div className="py-14 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
          ) : (grid.assessments?.length ?? 0) === 0 ? (
            <p className="text-sm text-slate-400 py-10 text-center bg-white rounded-xl border border-slate-200">
              No assessments are set up for{" "}
              <span className="font-semibold text-slate-600">{(subTerms as any[]).find((st) => st.id === subTermId)?.name ?? "this sub-term"}</span>
              {" "}in this term. Try another sub-term, or ask an administrator to set them up.
            </p>
          ) : (grid.students?.length ?? 0) === 0 ? (
            <p className="text-sm text-slate-400 py-10 text-center bg-white rounded-xl border border-slate-200">No pupils in this class.</p>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
              {/* Why an expected column is empty. Without this a CBT exam whose
                  scores were refused looks exactly like a class nobody marked —
                  the teacher's only clue was a blank column. Phrased for this
                  viewer by the API: a setup problem only an admin can fix arrives
                  already generalised. */}
              {grid.notices?.length > 0 && (
                <div className="m-4 mb-0 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-3">
                  <p className="text-xs font-bold text-amber-900 flex items-center gap-1.5">
                    <AlertTriangle size={13} className="shrink-0" />
                    Some CBT scores haven&apos;t reached this grid
                  </p>
                  <ul className="mt-1.5 space-y-1">
                    {grid.notices.map((n: string, i: number) => (
                      <li key={i} className="text-xs text-amber-800 leading-relaxed">{n}</li>
                    ))}
                  </ul>
                </div>
              )}
              {/* Only when the grid is UNFILTERED. With a sub-term selected the
                  field above already names it, and repeating it here would be
                  noise; without one the grid spans the whole term, and this is
                  the only thing saying which sub-term a column belongs to. */}
              {!subTermId && subTerm.only && (
                <p className="px-4 pt-3 text-xs text-slate-500">Sub-term: <span className="font-semibold text-slate-700">{subTerm.only}</span></p>
              )}
              <table className="w-full text-left">
                <thead><tr className="bg-slate-50/80 border-b border-slate-100">
                  <th className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">Pupil</th>
                  {grid.assessments.map((a: any) => (
                    <th key={a.id} className="px-3 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 text-center">
                      {a.name}
                      {subTerm.perColumn && a.sub_term_name && (
                        <span className="block font-semibold normal-case tracking-normal text-brand-600">{a.sub_term_name}</span>
                      )}
                      <span className="block font-normal text-slate-400">/{Number(a.max_score)}</span>
                    </th>
                  ))}
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
