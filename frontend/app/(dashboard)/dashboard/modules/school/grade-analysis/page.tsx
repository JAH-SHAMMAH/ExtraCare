"use client";

import { useMemo, useState } from "react";
import { useGradeAnalysis } from "@/hooks/useAcademics";
import { useMyTeachingAssignments, useSubTerms, useTerms } from "@/hooks/usePlatform";
import { classesFromAssignments, formatMark, subjectsForClass } from "@/lib/reportEntry";
import { cn } from "@/lib/utils";
import { BarChart3, Loader2, Search } from "lucide-react";

export default function GradeAnalysisPage() {
  const { data: assignments = [], isLoading: loadingAssignments } = useMyTeachingAssignments();
  const { data: terms = [] } = useTerms();
  const { data: subTerms = [] } = useSubTerms();

  const [classId, setClassId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [termId, setTermId] = useState("");
  const [subTermId, setSubTermId] = useState("");
  const [search, setSearch] = useState("");

  // The filters offer only what this teacher teaches, derived from the same
  // assignments the API scopes on — so a pair that would return nothing is never
  // offered in the first place.
  const myClasses = useMemo(() => classesFromAssignments(assignments as any[]), [assignments]);
  const mySubjects = useMemo(() => subjectsForClass(assignments as any[], classId), [assignments, classId]);

  const { data, isLoading } = useGradeAnalysis({
    class_id: classId || undefined,
    subject_id: subjectId || undefined,
    term_id: termId || undefined,
    sub_term_id: subTermId || undefined,
    page_size: 100,
  });

  const items: any[] = data?.items ?? [];
  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (r) =>
        (r.student_name || "").toLowerCase().includes(q) ||
        (r.subject_name || "").toLowerCase().includes(q),
    );
  }, [items, search]);

  // Colour follows the mark, so a weak row is visible without reading numbers.
  const tone = (pct: number) =>
    pct >= 70 ? "text-emerald-700" : pct >= 50 ? "text-slate-700" : pct >= 40 ? "text-amber-700" : "text-red-700";

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
        <span>School Report</span><span>/</span>
        <span className="text-brand-600 font-semibold">Grade Analysis</span>
      </nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2">
        <BarChart3 size={22} className="text-brand-600" /> Grade Analysis
      </h1>
      <p className="text-slate-500 text-sm mb-5">
        How your pupils scored, by subject and assessment type. Covers the classes and
        subjects you teach.
      </p>

      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3 mb-5">
        <div><label className="label">Term</label>
          <select value={termId} onChange={(e) => setTermId(e.target.value)} className="input">
            <option value="">All terms</option>
            {(terms as any[]).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        {/* A real filter, not orientation: a term can hold both a Half-Term and a
            Full-Term assessment in the same group, and without this they are
            summed into one row the teacher cannot break apart. Defaults to all,
            so the figures match what the page showed before it existed. */}
        <div><label className="label">Sub-Term</label>
          <select value={subTermId} onChange={(e) => setSubTermId(e.target.value)} className="input">
            <option value="">All sub-terms</option>
            {(subTerms as any[]).map((st) => <option key={st.id} value={st.id}>{st.name}</option>)}
          </select>
        </div>
        <div className="min-w-[180px]"><label className="label">Class</label>
          <select
            value={classId}
            onChange={(e) => { setClassId(e.target.value); setSubjectId(""); }}
            className="input"
          >
            <option value="">All my classes</option>
            {myClasses.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div className="min-w-[180px]"><label className="label">Subject</label>
          {/* Subject depends on class: the Timetable assigns per class per subject,
              so the pairs are not independent. */}
          <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)} className="input" disabled={!classId}>
            <option value="">{classId ? "All subjects in this class" : "— Pick a class first —"}</option>
            {mySubjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
        <div className="flex-1 min-w-[200px]"><label className="label">Search</label>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Pupil or subject"
              className="input pl-9"
            />
          </div>
        </div>
      </div>

      {loadingAssignments || isLoading ? (
        <div className="py-16 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : (assignments as any[]).length === 0 ? (
        /* The API derives what you can see from your Timetable rows, so an account
           with none - including an administrator - gets an empty result. Saying so
           beats an empty table that reads as "no marks exist". */
        <div className="bg-white rounded-xl border border-dashed border-slate-200 py-16 px-6 text-center">
          <BarChart3 size={30} className="mx-auto mb-3 text-slate-300" />
          <p className="text-sm font-semibold text-slate-600 mb-1">No teaching assignments</p>
          <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
            This page shows the classes and subjects <span className="font-semibold">you</span> teach,
            taken from the timetable. You aren&apos;t assigned any yet, so there is nothing to analyse.
            An administrator can assign you on the timetable.
          </p>
        </div>
      ) : rows.length === 0 ? (
        <p className="text-sm text-slate-400 py-14 text-center bg-white rounded-xl border border-slate-200">
          {items.length === 0
            ? "No marks recorded yet for this selection. Enter them under Make Report."
            : "No pupil or subject matches that search."}
        </p>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-100">
                {["Pupil", "Subject", "Term", "Assessment", "Score", "%"].map((h) => (
                  <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {rows.map((r, i) => (
                <tr key={`${r.student_id}-${r.subject_id}-${r.term_id}-${i}`} className="hover:bg-slate-50/50">
                  <td className="px-4 py-2.5 text-sm font-medium text-slate-800">{r.student_name}</td>
                  <td className="px-4 py-2.5 text-sm text-slate-600">{r.subject_name}</td>
                  <td className="px-4 py-2.5 text-xs text-slate-500">{r.term_name}</td>
                  <td className="px-4 py-2.5 text-xs text-slate-500">
                    {r.assessment_type}
                    {r.assessment_count > 1 && (
                      <span className="text-slate-400"> ({r.assessment_count})</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-sm text-slate-600 tabular-nums">
                    {formatMark(r.total_score)} / {formatMark(r.total_max_score)}
                  </td>
                  <td className={cn("px-4 py-2.5 text-sm font-bold tabular-nums", tone(r.percentage ?? 0))}>
                    {formatMark(r.percentage)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data?.total > rows.length && (
            <p className="px-4 py-3 text-xs text-slate-400 border-t border-slate-100">
              Showing {rows.length} of {data.total}. Narrow by class, subject or term to see the rest.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
