"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { platformApi } from "@/lib/api";
import { useClasses } from "@/hooks/useSchool";
import { useSessions, useCurrentSession } from "@/hooks/usePlatform";
import { Loader2, UserCheck, Save, Search } from "lucide-react";

type Cell = { subject_id: string; subject_name: string | null; enrolled: boolean; has_marks: boolean };
type Row = { student_id: string; student_name: string; admission_no: string | null; subjects: Cell[] };

export default function StudentEnrolmentPage() {
  const qc = useQueryClient();
  const { data: classData } = useClasses({ page_size: 300 } as any);
  const classes: any[] = (classData as any)?.items || [];
  const { data: sessions = [] } = useSessions();
  const { data: cur } = useCurrentSession();
  const [classId, setClassId] = useState("");
  const [year, setYear] = useState("");
  const [search, setSearch] = useState("");
  const [ticks, setTicks] = useState<Record<string, Set<string>>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (!year && cur?.name) setYear(cur.name); }, [cur?.name, year]);
  const years = Array.from(new Set((sessions as any[]).map((s) => s.name))).filter(Boolean) as string[];

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["subject-enrolment", classId, year],
    queryFn: () => platformApi.subjectEnrollments.grid(classId, year || undefined),
    enabled: !!classId,
  });
  useEffect(() => {
    if (!data) return;
    const next: Record<string, Set<string>> = {};
    (data.students as Row[]).forEach((r) => { next[r.student_id] = new Set(r.subjects.filter((c) => c.enrolled).map((c) => c.subject_id)); });
    setTicks(next);
  }, [data]);

  const subjects: { subject_id: string; subject_name: string | null }[] = data?.subjects || [];
  const students: Row[] = useMemo(() => {
    const q = search.trim().toLowerCase();
    return ((data?.students as Row[]) || []).filter((r) => !q || `${r.student_name} ${r.admission_no || ""}`.toLowerCase().includes(q));
  }, [data, search]);
  const marks = useMemo(() => {
    const m = new Set<string>();
    ((data?.students as Row[]) || []).forEach((r) => r.subjects.forEach((c) => { if (c.has_marks) m.add(`${r.student_id}:${c.subject_id}`); }));
    return m;
  }, [data]);

  const toggle = (sid: string, subj: string) => setTicks((t) => { const n = { ...t, [sid]: new Set(t[sid]) }; n[sid].has(subj) ? n[sid].delete(subj) : n[sid].add(subj); return n; });
  const toggleColumn = (subj: string) => setTicks((t) => {
    const all = students.every((r) => t[r.student_id]?.has(subj));
    const n = { ...t };
    students.forEach((r) => { n[r.student_id] = new Set(t[r.student_id]); all ? n[r.student_id].delete(subj) : n[r.student_id].add(subj); });
    return n;
  });
  const dirty = useMemo(() => ((data?.students as Row[]) || []).some((r) => {
    const base = new Set(r.subjects.filter((c) => c.enrolled).map((c) => c.subject_id));
    const now = ticks[r.student_id] || new Set<string>();
    return base.size !== now.size || [...base].some((x) => !now.has(x));
  }), [data, ticks]);

  const save = async () => {
    setSaving(true);
    try {
      await platformApi.subjectEnrollments.save({
        class_id: classId, academic_year: data?.academic_year,
        items: Object.entries(ticks).map(([student_id, set]) => ({ student_id, subject_ids: [...set] })),
      });
      toast.success("Enrolment saved.");
      qc.invalidateQueries({ queryKey: ["subject-enrolment", classId, year] });
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Could not save enrolment.");
    } finally { setSaving(false); }
  };

  return (
    <div className="p-4 sm:p-8 max-w-7xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-3"><span>Home</span><span>•</span><span>Subjects</span><span>•</span><span className="text-brand-600 font-semibold">Student Enrolment</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2 mb-1"><UserCheck size={22} className="text-brand-600" /> Student Enrolment</h1>
      <p className="text-slate-500 text-sm mb-5">Tick the subjects each pupil takes this session. A mark can only be entered for a subject the pupil is enrolled in.</p>

      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-5 grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
        <div><label className="label">Class</label><select aria-label="Class" value={classId} onChange={(e) => setClassId(e.target.value)} className="input"><option value="">Select class…</option>{classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
        <div><label className="label">Session</label><select aria-label="Session" value={year} onChange={(e) => setYear(e.target.value)} className="input">{years.map((y) => <option key={y} value={y}>{y}</option>)}</select></div>
        <div className="relative"><label className="label">Search</label><Search size={14} className="absolute left-3 bottom-3 text-slate-400" /><input aria-label="Search pupils" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name or ID" className="input pl-9 w-full" /></div>
      </div>

      {!classId ? (
        <div className="bg-white rounded-xl border border-dashed border-slate-200 py-16 text-center text-slate-400"><UserCheck size={30} className="mx-auto mb-3 opacity-40" /><p className="text-sm">Pick a class to enrol its pupils in subjects.</p></div>
      ) : isLoading ? (
        <div className="py-16 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-red-200 py-10 text-center text-sm text-red-700">{(error as any)?.response?.data?.detail || "Could not load the enrolment grid."}</div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-bold text-slate-800">{data?.class_name} · {data?.academic_year}</p>
            <button onClick={save} disabled={!dirty || saving} className="btn-primary gap-2">{saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Save enrolment</button>
          </div>
          <div className="overflow-auto max-h-[70vh]">
            <table className="text-sm min-w-full">
              <thead className="bg-slate-50 sticky top-0 z-10">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-bold text-slate-600 sticky left-0 bg-slate-50">Pupil</th>
                  {subjects.map((s) => (
                    <th key={s.subject_id} className="px-2 py-2 text-xs font-semibold text-slate-600 min-w-[84px]">
                      <button type="button" title="Tick / untick this subject for everyone shown" onClick={() => toggleColumn(s.subject_id)} className="hover:text-brand-600">{s.subject_name}</button>
                    </th>
                  ))}
                  <th className="px-2 py-2 text-xs font-bold text-slate-600">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {students.length === 0 ? (
                  <tr><td colSpan={subjects.length + 2} className="py-10 text-center text-slate-400">No pupils to show.</td></tr>
                ) : students.map((r) => (
                  <tr key={r.student_id} className="hover:bg-slate-50/60">
                    <td className="px-3 py-2 sticky left-0 bg-white"><span className="font-medium text-slate-800">{r.student_name}</span><span className="block text-[11px] text-slate-400">{r.admission_no}</span></td>
                    {subjects.map((s) => (
                      <td key={s.subject_id} className="px-2 py-2 text-center">
                        <input type="checkbox" aria-label={`${r.student_name} – ${s.subject_name}`} checked={!!ticks[r.student_id]?.has(s.subject_id)} onChange={() => toggle(r.student_id, s.subject_id)}
                          title={marks.has(`${r.student_id}:${s.subject_id}`) ? "Has marks — cannot be removed until the marks are deleted" : undefined} />
                      </td>
                    ))}
                    <td className="px-2 py-2 text-center font-semibold text-slate-600">{ticks[r.student_id]?.size ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
