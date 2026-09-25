"use client";

import { useEffect, useMemo, useState } from "react";
import { useClassList } from "@/hooks/useAcademics";
import { useMyTeachingAssignments } from "@/hooks/usePlatform";
import { classesFromAssignments, subjectsForClass } from "@/lib/reportEntry";
import { getInitials } from "@/lib/utils";
import { Loader2, Search, ShieldAlert, Users2 } from "lucide-react";

export default function ClassListPage() {
  const { data: assignments = [], isLoading: loadingAssignments } = useMyTeachingAssignments();

  const [classId, setClassId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [search, setSearch] = useState("");

  // Same derivation Make Report uses: the pickers offer only pairs this teacher
  // actually teaches, so a selection the API would refuse cannot be made here.
  const myClasses = useMemo(() => classesFromAssignments(assignments as any[]), [assignments]);
  const mySubjects = useMemo(() => subjectsForClass(assignments as any[], classId), [assignments, classId]);

  // A subject held from a previous class may not be taught in the new one.
  useEffect(() => {
    if (subjectId && !mySubjects.some((s) => s.id === subjectId)) setSubjectId("");
  }, [mySubjects, subjectId]);

  const ready = !!classId && !!subjectId;
  const { data, isLoading, isError, error } = useClassList({ class_id: classId, subject_id: subjectId });

  const students: any[] = data?.students ?? [];
  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return students;
    return students.filter(
      (s) => (s.name || "").toLowerCase().includes(q) || (s.student_id || "").toLowerCase().includes(q),
    );
  }, [students, search]);

  const denied = isError && (error as any)?.response?.status === 403;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
        <span>Subjects</span><span>/</span>
        <span className="text-brand-600 font-semibold">Class List</span>
      </nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2">
        <Users2 size={22} className="text-brand-600" /> Class List
      </h1>
      <p className="text-slate-500 text-sm mb-5">
        The pupils you teach, for one class and subject. Read-only.
      </p>

      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3 mb-5">
        <div className="min-w-[200px]"><label className="label">Class</label>
          <select value={classId} onChange={(e) => { setClassId(e.target.value); setSubjectId(""); }} className="input">
            <option value="">— Select —</option>
            {myClasses.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div className="min-w-[200px]"><label className="label">Subject</label>
          {/* Dependent on class: the Timetable assigns per class per subject. */}
          <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)} className="input" disabled={!classId}>
            <option value="">{classId ? "— Select —" : "— Pick a class first —"}</option>
            {mySubjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
        {ready && students.length > 0 && (
          <div className="flex-1 min-w-[200px]"><label className="label">Search</label>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name or ID" className="input pl-9" />
            </div>
          </div>
        )}
      </div>

      {loadingAssignments ? (
        <div className="py-16 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : (assignments as any[]).length === 0 ? (
        /* The API derives what you may see from your Timetable rows, so an account
           with none — an administrator included — has nothing to pick. Saying so
           beats two empty dropdowns. */
        <div className="bg-white rounded-xl border border-dashed border-slate-200 py-16 px-6 text-center">
          <Users2 size={30} className="mx-auto mb-3 text-slate-300" />
          <p className="text-sm font-semibold text-slate-600 mb-1">No teaching assignments</p>
          <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
            This page lists the pupils in the classes <span className="font-semibold">you</span> teach,
            taken from the timetable. You aren&apos;t assigned any yet. An administrator
            can assign you on the timetable.
          </p>
        </div>
      ) : !ready ? (
        <div className="bg-white rounded-xl border border-dashed border-slate-200 py-16 text-center text-slate-400">
          <Users2 size={30} className="mx-auto mb-3 opacity-40" />
          <p className="text-sm">Pick a class and subject to see its pupils.</p>
        </div>
      ) : isLoading ? (
        <div className="py-16 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : denied ? (
        <div className="bg-white rounded-xl border border-amber-200 py-14 px-6 text-center">
          <ShieldAlert size={30} className="mx-auto mb-3 text-amber-500" />
          <p className="text-sm font-bold text-slate-800 mb-1">Not your class</p>
          <p className="text-sm text-amber-800">
            {(error as any)?.response?.data?.detail || "You do not teach this subject in this class."}
          </p>
        </div>
      ) : isError ? (
        <p className="text-sm text-slate-500 py-14 text-center bg-white rounded-xl border border-slate-200">
          Couldn&apos;t load this class list. Try again.
        </p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-slate-400 py-14 text-center bg-white rounded-xl border border-slate-200">
          {students.length === 0 ? "No pupils in this class." : "No pupil matches that search."}
        </p>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
            <p className="text-sm font-bold text-slate-800">
              {data.class_name} · {data.subject_name}
            </p>
            <p className="text-xs text-slate-500">
              {rows.length === students.length
                ? `${students.length} pupil${students.length === 1 ? "" : "s"}`
                : `${rows.length} of ${students.length}`}
            </p>
          </div>
          <table className="w-full text-left">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-100">
                {["#", "Pupil", "Student ID", "Gender"].map((h) => (
                  <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {rows.map((s, i) => (
                <tr key={s.id} className="hover:bg-slate-50/50">
                  <td className="px-4 py-2.5 text-xs text-slate-400 tabular-nums">{i + 1}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2.5">
                      {s.photo_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={s.photo_url} alt="" className="w-7 h-7 rounded-full object-cover" />
                      ) : (
                        <span className="w-7 h-7 rounded-full bg-brand-50 text-brand-700 text-[10px] font-bold flex items-center justify-center">
                          {getInitials(s.name || "")}
                        </span>
                      )}
                      <span className="text-sm font-medium text-slate-800">{s.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-sm text-slate-500 tabular-nums">{s.student_id}</td>
                  <td className="px-4 py-2.5 text-sm text-slate-500">{s.gender || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
