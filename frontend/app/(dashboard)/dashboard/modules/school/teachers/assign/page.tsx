"use client";

import { useState } from "react";
import { useTeachers, useAssignTeacherSection } from "@/hooks/useSchool";
import { useSections } from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { getInitials, resolveMediaUrl, cn } from "@/lib/utils";
import { Search, Loader2, Building2 } from "lucide-react";
import type { Teacher, SchoolSection } from "@/types";

/**
 * Assign To School — assign / transfer a teacher to a school section (Educare's
 * "Transfer Teacher"). Each teacher's current section is shown with a dropdown to
 * change it; saving is immediate. Admin/Super-User only (settings gating).
 */
export default function AssignToSchoolPage() {
  const canWrite = useHasPermission("settings:write");
  const [search, setSearch] = useState("");
  const { data, isLoading } = useTeachers({ page: 1, page_size: 100, search: search || undefined });
  const { data: sections } = useSections();
  const assign = useAssignTeacherSection();
  const teachers: Teacher[] = data?.items ?? [];
  const [savingId, setSavingId] = useState<string | null>(null);

  const change = (t: Teacher, sectionId: string) => {
    setSavingId(t.id);
    assign.mutate({ id: t.id, sectionId: sectionId || null }, { onSettled: () => setSavingId(null) });
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Teachers</span><span>/</span><span className="text-brand-600 font-semibold">Assign To School</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2"><Building2 size={22} className="text-brand-600" /> Assign To School</h1>
      <p className="text-slate-500 text-sm mb-5">Assign or transfer a teacher to a school section.</p>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100">
          <div className="relative max-w-xs">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search teachers…" className="input pl-9 py-1.5 text-sm" />
          </div>
        </div>

        {isLoading ? (
          <div className="py-14 flex justify-center"><Loader2 className="w-5 h-5 animate-spin text-slate-400" /></div>
        ) : teachers.length === 0 ? (
          <p className="py-14 text-center text-sm text-slate-400">No teachers found.</p>
        ) : (
          <ul className="divide-y divide-slate-50">
            {teachers.map((t) => (
              <li key={t.id} className="flex items-center gap-3 px-5 py-3 hover:bg-slate-50/70">
                {t.photo_url ? <img src={resolveMediaUrl(t.photo_url)} alt="" className="w-9 h-9 rounded-full object-cover" />
                  : <div className="w-9 h-9 rounded-full bg-slate-200 text-slate-500 flex items-center justify-center text-xs font-bold">{getInitials(`${t.first_name} ${t.last_name}`)}</div>}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-800 truncate">{t.first_name} {t.last_name}</p>
                  <p className="text-xs text-slate-400 truncate">{t.employee_id ? `${t.employee_id} · ` : ""}{t.email}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs text-slate-400 hidden sm:inline">Current: <span className="font-semibold text-slate-600">{t.section_name || "—"}</span></span>
                  <select
                    value={t.section_id || ""}
                    disabled={!canWrite || savingId === t.id}
                    onChange={(e) => change(t, e.target.value)}
                    className={cn("input w-auto py-1.5 text-sm min-w-[150px]", savingId === t.id && "opacity-60")}
                  >
                    <option value="">— Unassigned —</option>
                    {(sections ?? []).map((s: SchoolSection) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                  {savingId === t.id && <Loader2 size={14} className="animate-spin text-slate-400" />}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
      {!canWrite && <p className="text-xs text-slate-400 mt-3">You have view-only access to this page.</p>}
    </div>
  );
}
