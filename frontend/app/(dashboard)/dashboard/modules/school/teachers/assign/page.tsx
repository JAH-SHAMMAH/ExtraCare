"use client";

import { useState } from "react";
import { useTeachers, useAssignTeacherSection } from "@/hooks/useSchool";
import { useSections } from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { getInitials, resolveMediaUrl, cn } from "@/lib/utils";
import { Search, Loader2, Building2, UserPlus, ArrowRight } from "lucide-react";
import type { Teacher, SchoolSection } from "@/types";

/**
 * Assign To School — Educare's "Transfer Teacher": choose a destination school
 * ("Select Current School") and a source school ("Add From"), then move each of
 * the source's teachers over with an "Add Teacher" button. Admin/Super-User only.
 */
export default function AssignToSchoolPage() {
  const canWrite = useHasPermission("settings:write");
  const { data: sections } = useSections();
  const [toId, setToId] = useState("");     // Select Current School (destination)
  const [fromId, setFromId] = useState("");  // Add From (source)
  const [search, setSearch] = useState("");
  const [pageSize, setPageSize] = useState(10);

  const ready = !!toId && !!fromId && toId !== fromId;
  const { data, isLoading, isFetching } = useTeachers(
    { page: 1, page_size: pageSize, search: search || undefined, section: fromId || undefined },
  );
  const assign = useAssignTeacherSection();
  const [movingId, setMovingId] = useState<string | null>(null);

  const teachers: Teacher[] = ready ? (data?.items ?? []) : [];
  const nameOf = (id: string) => sections?.find((s) => s.id === id)?.name ?? "";

  const addTeacher = (t: Teacher) => {
    setMovingId(t.id);
    assign.mutate({ id: t.id, sectionId: toId }, { onSettled: () => setMovingId(null) });
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Teachers</span><span>/</span><span className="text-brand-600 font-semibold">Assign To School</span></nav>

      {/* Transfer Teacher */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden mb-5">
        <div className="px-5 py-3 bg-brand-700 text-white text-sm font-bold flex items-center gap-2"><Building2 size={16} /> Transfer Teacher</div>
        <div className="p-6 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-[160px_1fr] items-center gap-3">
            <label className="text-sm font-semibold text-slate-600 md:text-right">Select Current School</label>
            <select value={toId} onChange={(e) => setToId(e.target.value)} className="input">
              <option value="">— Select destination —</option>
              {(sections ?? []).map((s: SchoolSection) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-[160px_1fr] items-center gap-3">
            <label className="text-sm font-semibold text-slate-600 md:text-right">Add From</label>
            <select value={fromId} onChange={(e) => setFromId(e.target.value)} className="input">
              <option value="">— Select source —</option>
              {(sections ?? []).filter((s: SchoolSection) => s.id !== toId).map((s: SchoolSection) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
        </div>
      </div>

      {!ready ? (
        <div className="bg-white rounded-xl border border-dashed border-slate-200 p-10 text-center text-slate-400">
          <ArrowRight size={28} className="mx-auto mb-3 opacity-40" />
          <p className="text-sm font-medium text-slate-600">Choose a destination and a source school.</p>
          <p className="text-xs mt-1">Then add teachers from the source into the destination.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-5 py-3 bg-brand-700 text-white text-sm font-bold flex items-center gap-2">
            <Building2 size={16} /> Add teacher from {nameOf(fromId)} to {nameOf(toId)}.
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
            <label className="text-xs text-slate-500 flex items-center gap-2">
              <select value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))} className="input w-auto py-1 text-sm">
                {[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
              records
            </label>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search…" className="input pl-9 py-1.5 text-sm" />
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead><tr className="bg-slate-50/80 border-y border-slate-100">
                {["ID", "Photo", "Full Name", "Actions"].map((h) => (
                  <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>
                ))}
              </tr></thead>
              <tbody className="divide-y divide-slate-50">
                {isLoading || isFetching ? (
                  <tr><td colSpan={4} className="py-12 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></td></tr>
                ) : teachers.length === 0 ? (
                  <tr><td colSpan={4} className="py-12 text-center text-sm text-slate-400">No teachers in {nameOf(fromId)}.</td></tr>
                ) : teachers.map((t, i) => (
                  <tr key={t.id} className="hover:bg-slate-50/70">
                    <td className="px-5 py-3 text-sm text-slate-500">{i + 1}</td>
                    <td className="px-5 py-3">
                      {t.photo_url ? <img src={resolveMediaUrl(t.photo_url)} alt="" className="w-11 h-11 rounded object-cover" />
                        : <div className="w-11 h-11 rounded bg-slate-200 text-slate-500 flex items-center justify-center text-sm font-bold">{getInitials(`${t.first_name} ${t.last_name}`)}</div>}
                    </td>
                    <td className="px-5 py-3 text-sm font-semibold text-slate-800">{t.first_name} {t.last_name}{t.other_names ? ` ${t.other_names}` : ""}</td>
                    <td className="px-5 py-3">
                      <button
                        onClick={() => addTeacher(t)}
                        disabled={!canWrite || movingId === t.id}
                        className="inline-flex items-center gap-1.5 bg-brand-600 text-white text-xs font-semibold px-3 py-1.5 rounded-full hover:bg-brand-700 disabled:opacity-50"
                      >
                        {movingId === t.id ? <Loader2 size={13} className="animate-spin" /> : <UserPlus size={13} />} Add Teacher
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {!canWrite && <p className="text-xs text-slate-400 mt-3">You have view-only access to this page.</p>}
    </div>
  );
}
