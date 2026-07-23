"use client";

import { useEffect, useMemo, useState } from "react";
import { useSessions } from "@/hooks/usePlatform";
import { useClubs, useClubGrades, useClubAssessments, useSaveClubAssessments } from "@/hooks/useSchoolExperience";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { Award, Loader2, AlertTriangle, Save, Lock } from "lucide-react";
import type { Club, ClubGrade, ClubAssessmentRow } from "@/types";

type Draft = Record<string, { grade_id: string; remarks: string }>;

export default function ClubAssessmentPage() {
  const canWrite = useHasPermission("school:clubs:write");
  const { data: sessions } = useSessions();
  const { data: clubsData } = useClubs();
  const { data: gradesData } = useClubGrades();

  const rows = sessions ?? [];
  const sessionNames = useMemo(() => Array.from(new Set(rows.map((s: any) => s.name))), [rows]);
  const [session, setSession] = useState("");
  const [term, setTerm] = useState("");
  const termsFor = useMemo(() => Array.from(new Set(rows.filter((s: any) => s.name === session).map((s: any) => s.term).filter(Boolean))), [rows, session]);
  const [clubId, setClubId] = useState("");

  useEffect(() => {
    if (session || rows.length === 0) return;
    const cur = rows.find((s: any) => s.is_current) ?? rows[0];
    if (cur) { setSession(cur.name); setTerm(cur.term || ""); }
  }, [rows, session]);

  const clubs: Club[] = clubsData?.items ?? [];
  const grades: ClubGrade[] = gradesData?.items ?? [];
  const { data, isLoading, isError, refetch } = useClubAssessments(clubId || null, { academic_year: session || undefined, term: term || undefined });
  const save = useSaveClubAssessments();
  const members: ClubAssessmentRow[] = data?.items ?? [];

  const [draft, setDraft] = useState<Draft>({});
  // Seed the draft from the server rows whenever they change.
  useEffect(() => {
    const d: Draft = {};
    members.forEach((m) => { d[m.student_id] = { grade_id: m.grade_id || "", remarks: m.remarks || "" }; });
    setDraft(d);
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (sid: string, patch: Partial<{ grade_id: string; remarks: string }>) => setDraft((d) => ({ ...d, [sid]: { ...d[sid], ...patch } }));
  const submit = () => {
    const entries = members.map((m) => ({ student_id: m.student_id, grade_id: draft[m.student_id]?.grade_id || null, remarks: draft[m.student_id]?.remarks || null }));
    save.mutate({ id: clubId, data: { academic_year: session || null, term: term || null, entries } });
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Clubs</span><span>/</span><span className="text-brand-600 font-semibold">Club Assessment</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Club Assessment</h1>
        <p className="text-slate-500 text-sm mt-0.5">Grade a club’s members for the term against the grade bands.</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6 grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div><label className="label">Session</label><select value={session} onChange={(e) => { setSession(e.target.value); setTerm(""); }} className="input"><option value="">All</option>{sessionNames.map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
        <div><label className="label">Term</label><select value={term} onChange={(e) => setTerm(e.target.value)} className="input"><option value="">All</option>{termsFor.map((t) => <option key={t} value={t}>{t}</option>)}</select></div>
        <div><label className="label">Select Club *</label><select value={clubId} onChange={(e) => setClubId(e.target.value)} className="input"><option value="">Select…</option>{clubs.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
      </div>

      {!clubId ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400"><Award size={32} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">Select a club to grade its members</p></div>
      ) : (
        <>
          {grades.length === 0 && <div className="mb-4 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">No grade bands yet — add them in Manage Clubs → Club Grade to pick from.</div>}
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-black uppercase tracking-widest text-slate-400">Member Assessment</h3>
            {canWrite && members.length > 0 && <button onClick={submit} disabled={save.isPending} className="btn-primary gap-2">{save.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Save Assessment</button>}
          </div>
          <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
            <table className="w-full text-left">
              <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["#", "Student Name", "Current Class", "Grade", "Remarks"].map((h) => <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>)}</tr></thead>
              <tbody className="divide-y divide-slate-50">
                {isLoading ? Array.from({ length: 5 }).map((_, i) => <tr key={i}>{Array.from({ length: 5 }).map((_, j) => <td key={j} className="px-4 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-16" /></td>)}</tr>)
                : isError ? <tr><td colSpan={5} className="py-14 text-center"><AlertTriangle size={26} className="mx-auto mb-2 text-amber-400" /><button onClick={() => refetch()} className="btn-secondary mt-2">Retry</button></td></tr>
                : members.length > 0 ? members.map((m, i) => (
                  <tr key={m.student_id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3 text-sm text-slate-500">{i + 1}</td>
                    <td className="px-4 py-3 text-sm font-semibold text-slate-800 whitespace-nowrap">{m.student_name}</td>
                    <td className="px-4 py-3 text-sm text-slate-600 whitespace-nowrap">{m.current_class || "—"}</td>
                    <td className="px-4 py-3">
                      <select value={draft[m.student_id]?.grade_id || ""} onChange={(e) => set(m.student_id, { grade_id: e.target.value })} disabled={!canWrite} className="input py-1.5 text-sm min-w-[120px]">
                        <option value="">—</option>
                        {grades.map((g) => <option key={g.id} value={g.id}>{g.grade_letter}{g.remarks ? ` (${g.remarks})` : ""}</option>)}
                      </select>
                    </td>
                    <td className="px-4 py-3"><input value={draft[m.student_id]?.remarks || ""} onChange={(e) => set(m.student_id, { remarks: e.target.value })} disabled={!canWrite} className="input py-1.5 text-sm min-w-[200px]" placeholder="optional" /></td>
                  </tr>
                )) : <tr><td colSpan={5} className="py-14 text-center text-slate-400 font-semibold">No approved members for this term</td></tr>}
              </tbody>
            </table>
          </div>
          {!canWrite && <p className="text-xs text-slate-400 mt-4 flex items-center gap-1"><Lock size={12} /> Grading requires club write access.</p>}
        </>
      )}
    </div>
  );
}
