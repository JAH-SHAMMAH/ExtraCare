"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { schoolApi } from "@/lib/api";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { ArrowLeft, BookOpen, Loader2, Pencil, Search, X } from "lucide-react";

interface Pair { class_id: string; class_name?: string; subject_id: string; subject_name?: string }
interface Row {
  id: string; name: string; email: string; department: string | null; sections: string[];
  class_teacher_of: { id: string; name: string }[];
  subjects: { id: string; name: string }[];
  assignments: Pair[];
}
interface Catalog {
  sections: { id: string; name: string }[];
  classes: { id: string; name: string; section_id: string | null }[];
  subjects: { id: string; name: string; section_id: string }[];
}

const key = (c: string, s: string) => `${c}|${s}`;

export default function TeachingAssignmentsPage() {
  const canWrite = useHasPermission("settings:write");
  const [section, setSection] = useState("");
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<Row | null>(null);

  const { data, isLoading, isError } = useQuery<{ items: Row[]; catalog: Catalog }>({
    queryKey: ["teacher-assignments", section],
    queryFn: () => schoolApi.teachers.assignments(section || undefined),
  });
  const rows = (data?.items ?? []).filter((r) => {
    const q = search.trim().toLowerCase();
    return !q || r.name.toLowerCase().includes(q) || r.email.toLowerCase().includes(q);
  });
  const catalog = data?.catalog;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <Link href="/dashboard/modules/school/teachers" className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 mb-2"><ArrowLeft size={13} /> View Teachers</Link>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2"><BookOpen size={22} className="text-brand-600" /> Teaching Assignments</h1>
      <p className="text-sm text-slate-500 mb-5">Who teaches which subject in which class. A <b>class teacher</b> leads a class; a <b>subject teacher</b> teaches a subject in the classes listed here. Several teachers can share a subject.</p>

      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4 flex flex-wrap items-center gap-3">
        <select value={section} onChange={(e) => setSection(e.target.value)} className="input w-auto min-w-[200px]">
          <option value="">All sections</option>
          {(catalog?.sections ?? []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <div className="relative flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search teacher…" className="input pl-9" />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>{["Teacher", "Section", "Class teacher of", "Teaches", ""].map((h) => <th key={h} className="px-4 py-2.5 text-left">{h}</th>)}</tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={5} className="px-4 py-10 text-center text-slate-400"><Loader2 className="inline animate-spin" size={16} /></td></tr>}
            {isError && <tr><td colSpan={5} className="px-4 py-10 text-center text-red-600">Could not load assignments.</td></tr>}
            {!isLoading && !isError && rows.length === 0 && <tr><td colSpan={5} className="px-4 py-10 text-center text-slate-400">No teachers found.</td></tr>}
            {rows.map((r) => {
              const bySubject = new Map<string, string[]>();
              r.assignments.forEach((a) => bySubject.set(a.subject_name || "", [...(bySubject.get(a.subject_name || "") ?? []), a.class_name || ""]));
              const legacy = r.subjects.filter((s) => !bySubject.has(s.name));
              const none = bySubject.size === 0 && legacy.length === 0;
              return (
                <tr key={r.id} className="border-t border-slate-100 align-top">
                  <td className="px-4 py-3"><p className="font-semibold text-slate-900">{r.name}</p><p className="text-xs text-slate-400">{r.email}</p></td>
                  <td className="px-4 py-3 text-slate-600">{r.sections.join(", ") || <span className="text-slate-300">—</span>}</td>
                  <td className="px-4 py-3">
                    {r.class_teacher_of.length
                      ? <div className="flex flex-wrap gap-1">{r.class_teacher_of.map((c) => <span key={c.id} className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-xs font-semibold">{c.name}</span>)}</div>
                      : <span className="text-xs text-slate-400">Subject teacher only</span>}
                  </td>
                  <td className="px-4 py-3">
                    {none && <span className="text-xs text-amber-700">Nothing assigned yet</span>}
                    <div className="space-y-1">
                      {[...bySubject.entries()].map(([sub, cls]) => (
                        <p key={sub} className="text-xs"><span className="font-semibold text-slate-800">{sub}</span><span className="text-slate-500"> — {cls.join(", ")}</span></p>
                      ))}
                      {legacy.map((s) => <p key={s.id} className="text-xs"><span className="font-semibold text-slate-800">{s.name}</span><span className="text-slate-500"> — all classes</span></p>)}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {canWrite && <button onClick={() => setEditing(r)} className="btn-secondary gap-1.5 py-1 text-xs"><Pencil size={12} /> Edit</button>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {editing && catalog && <Editor teacher={editing} catalog={catalog} onClose={() => setEditing(null)} />}
    </div>
  );
}

function Editor({ teacher, catalog, onClose }: { teacher: Row; catalog: Catalog; onClose: () => void }) {
  const qc = useQueryClient();
  const [sel, setSel] = useState<Set<string>>(() => new Set(teacher.assignments.map((a) => key(a.class_id, a.subject_id))));
  const [allSections, setAllSections] = useState(false);

  const secIds = useMemo(() => new Set(catalog.sections.filter((s) => teacher.sections.includes(s.name)).map((s) => s.id)), [catalog, teacher]);
  const showAll = allSections || secIds.size === 0;
  const subjects = catalog.subjects.filter((s) => showAll || secIds.has(s.section_id));
  const secName = (id: string | null) => catalog.sections.find((s) => s.id === id)?.name ?? "";

  const save = useMutation({
    mutationFn: () => schoolApi.teachers.setAssignments(teacher.id, [...sel].map((k) => { const [class_id, subject_id] = k.split("|"); return { class_id, subject_id }; })),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["teacher-assignments"] }); toast.success("Assignments saved."); onClose(); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Could not save."),
  });

  const toggle = (k: string) => setSel((p) => { const n = new Set(p); n.has(k) ? n.delete(k) : n.add(k); return n; });
  const setMany = (keys: string[], on: boolean) => setSel((p) => { const n = new Set(p); keys.forEach((k) => (on ? n.add(k) : n.delete(k))); return n; });

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <div className="bg-white w-full max-w-xl h-full overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="sticky top-0 bg-white border-b border-slate-200 px-5 py-4 flex items-start justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">{teacher.name}</h2>
            <p className="text-xs text-slate-500">Tick the classes each subject is taught in. {teacher.sections.join(", ") || "No section set"}</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100"><X size={18} /></button>
        </div>

        <div className="p-5 space-y-4">
          {secIds.size > 0 && (
            <label className="flex items-center gap-2 text-xs text-slate-600">
              <input type="checkbox" checked={allSections} onChange={(e) => setAllSections(e.target.checked)} /> Show subjects from all sections
            </label>
          )}
          {subjects.length === 0 && <p className="text-sm text-slate-500">No subjects set up for this section yet. Add them under Subjects first.</p>}
          {subjects.map((s) => {
            const classes = catalog.classes.filter((c) => c.section_id === s.section_id);
            const keys = classes.map((c) => key(c.id, s.id));
            const on = keys.filter((k) => sel.has(k)).length;
            return (
              <div key={s.id} className="border border-slate-200 rounded-xl p-3">
                <div className="flex items-center justify-between mb-2">
                  <p className="font-semibold text-slate-900 text-sm">{s.name} <span className="text-xs font-normal text-slate-400">{showAll ? secName(s.section_id) : ""}</span></p>
                  <div className="flex gap-2 text-xs">
                    <button type="button" onClick={() => setMany(keys, true)} className="text-brand-600 font-semibold">All</button>
                    <button type="button" onClick={() => setMany(keys, false)} className="text-slate-500 font-semibold">None</button>
                  </div>
                </div>
                {classes.length === 0
                  ? <p className="text-xs text-slate-400">No classes in this section yet.</p>
                  : <div className="flex flex-wrap gap-1.5">
                      {classes.map((c) => {
                        const k = key(c.id, s.id);
                        return (
                          <button type="button" key={c.id} onClick={() => toggle(k)}
                            className={cn("px-2.5 py-1 rounded-lg border text-xs font-semibold transition",
                              sel.has(k) ? "bg-brand-600 border-brand-600 text-white" : "border-slate-200 text-slate-600 hover:bg-slate-50")}>{c.name}</button>
                        );
                      })}
                    </div>}
                <p className="text-[11px] text-slate-400 mt-1.5">{on} of {classes.length} classes</p>
              </div>
            );
          })}
        </div>

        <div className="sticky bottom-0 bg-white border-t border-slate-200 px-5 py-3 flex gap-3">
          <button onClick={onClose} className="btn-secondary flex-1">Cancel</button>
          <button onClick={() => save.mutate()} disabled={save.isPending} className="btn-primary flex-1 gap-2 justify-center">
            {save.isPending && <Loader2 size={15} className="animate-spin" />}Save {sel.size} assignment{sel.size === 1 ? "" : "s"}
          </button>
        </div>
      </div>
    </div>
  );
}
