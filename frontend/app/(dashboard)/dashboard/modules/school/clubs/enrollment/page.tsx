"use client";

import { useEffect, useMemo, useState } from "react";
import { useSessions } from "@/hooks/usePlatform";
import { useClasses } from "@/hooks/useSchool";
import { useClubs, useEnrollmentCandidates, useEnrollStudents, useUnenrollMembership } from "@/hooks/useSchoolExperience";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { UserPlus, Loader2, AlertTriangle, Check, Trash2, Lock } from "lucide-react";
import type { Club, ClubEnrollCandidate } from "@/types";

export default function ClubEnrollmentPage() {
  const canWrite = useHasPermission("school:clubs:write");
  const { data: sessions } = useSessions();
  const { data: classesData } = useClasses({ page_size: 200 });
  const { data: clubsData } = useClubs();

  const rows = sessions ?? [];
  const sessionNames = useMemo(() => Array.from(new Set(rows.map((s: any) => s.name))), [rows]);
  const [session, setSession] = useState("");
  const [term, setTerm] = useState("");
  const termsFor = useMemo(() => Array.from(new Set(rows.filter((s: any) => s.name === session).map((s: any) => s.term).filter(Boolean))), [rows, session]);
  const [classId, setClassId] = useState("");
  const [clubId, setClubId] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (session || rows.length === 0) return;
    const cur = rows.find((s: any) => s.is_current) ?? rows[0];
    if (cur) { setSession(cur.name); setTerm(cur.term || ""); }
  }, [rows, session]);

  const classes = classesData?.items ?? [];
  const clubs: Club[] = clubsData?.items ?? [];
  const { data, isLoading, isError, refetch } = useEnrollmentCandidates(clubId || null, { academic_year: session || undefined, term: term || undefined, class_id: classId || undefined });
  const enroll = useEnrollStudents();
  const unenroll = useUnenrollMembership();
  const candidates: ClubEnrollCandidate[] = data?.items ?? [];

  const toggle = (id: string) => setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const unassigned = candidates.filter((c) => !c.membership_id);
  const enrollSelected = () => {
    const ids = [...selected].filter((id) => unassigned.some((c) => c.student_id === id));
    if (ids.length === 0) return;
    enroll.mutate({ id: clubId, data: { student_ids: ids, academic_year: session || null, term: term || null } }, { onSuccess: () => setSelected(new Set()) });
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Clubs</span><span>/</span><span className="text-brand-600 font-semibold">Club Enrollment</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Club Enrollment</h1>
        <p className="text-slate-500 text-sm mt-0.5">Assign students to a club for the selected term.</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div><label className="label">Session</label><select value={session} onChange={(e) => { setSession(e.target.value); setTerm(""); }} className="input"><option value="">All</option>{sessionNames.map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
        <div><label className="label">Term</label><select value={term} onChange={(e) => setTerm(e.target.value)} className="input"><option value="">All</option>{termsFor.map((t) => <option key={t} value={t}>{t}</option>)}</select></div>
        <div><label className="label">Class</label><select value={classId} onChange={(e) => setClassId(e.target.value)} className="input"><option value="">All classes</option>{classes.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
        <div><label className="label">Select Club *</label><select value={clubId} onChange={(e) => { setClubId(e.target.value); setSelected(new Set()); }} className="input"><option value="">Select…</option>{clubs.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
      </div>

      {!clubId ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400"><UserPlus size={32} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">Select a club to assign students</p></div>
      ) : (
        <>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-black uppercase tracking-widest text-slate-400">Assign Clubs to Students</h3>
            {canWrite && <button onClick={enrollSelected} disabled={selected.size === 0 || enroll.isPending} className="btn-primary gap-2">{enroll.isPending ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />} Enroll Selected ({[...selected].filter((id) => unassigned.some((c) => c.student_id === id)).length})</button>}
          </div>
          <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
            <table className="w-full text-left">
              <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["", "#", "Student Name", "Current Class", "Status", "Action"].map((h) => <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>)}</tr></thead>
              <tbody className="divide-y divide-slate-50">
                {isLoading ? Array.from({ length: 5 }).map((_, i) => <tr key={i}>{Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-4 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-16" /></td>)}</tr>)
                : isError ? <tr><td colSpan={6} className="py-14 text-center"><AlertTriangle size={26} className="mx-auto mb-2 text-amber-400" /><button onClick={() => refetch()} className="btn-secondary mt-2">Retry</button></td></tr>
                : candidates.length > 0 ? candidates.map((c, i) => (
                  <tr key={c.student_id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3">{canWrite && !c.membership_id && <input type="checkbox" checked={selected.has(c.student_id)} onChange={() => toggle(c.student_id)} className="w-4 h-4" />}</td>
                    <td className="px-4 py-3 text-sm text-slate-500">{i + 1}</td>
                    <td className="px-4 py-3 text-sm font-semibold text-slate-800">{c.student_name}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{c.current_class || "—"}</td>
                    <td className="px-4 py-3 text-sm">{c.membership_id ? <span className={cn("badge uppercase", c.status === "approved" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : c.status === "pending" ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-rose-50 text-rose-700 border-rose-200")}>{c.status}</span> : <span className="text-slate-300">Not enrolled</span>}</td>
                    <td className="px-4 py-3">
                      {canWrite && (c.membership_id
                        ? <button onClick={() => unenroll.mutate(c.membership_id!)} className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600 hover:text-rose-700 px-2 py-1 rounded hover:bg-rose-50"><Trash2 size={13} /> Remove</button>
                        : <button onClick={() => enroll.mutate({ id: clubId, data: { student_ids: [c.student_id], academic_year: session || null, term: term || null } })} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700 px-2 py-1 rounded hover:bg-emerald-50"><UserPlus size={13} /> Enroll</button>)}
                    </td>
                  </tr>
                )) : <tr><td colSpan={6} className="py-14 text-center text-slate-400 font-semibold">No students found</td></tr>}
              </tbody>
            </table>
          </div>
          {!canWrite && <p className="text-xs text-slate-400 mt-4 flex items-center gap-1"><Lock size={12} /> Enrolling requires club write access.</p>}
        </>
      )}
    </div>
  );
}
