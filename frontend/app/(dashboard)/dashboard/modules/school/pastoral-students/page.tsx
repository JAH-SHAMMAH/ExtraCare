"use client";

import { useState } from "react";
import {
  usePastoralStudents, useAssignPastoralStudent, useBulkAssignPastoralStudents, useSyncPastoralStudents,
} from "@/hooks/usePastoral";
import { useHouses, useSections } from "@/hooks/usePlatform";
import { pastoralApi } from "@/lib/api";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { Search, Download, RefreshCw, Loader2, UserCog, X, Users2 } from "lucide-react";
import type { SchoolSection } from "@/types";

type Row = {
  student_id: string; student_name: string | null; class_name: string | null;
  house_id: string | null; house_name: string | null; mentor_id: string | null; mentor_name: string | null; is_leader: boolean;
};

export default function PastoralStudentsPage() {
  const canWrite = useHasPermission("school:hostel:write");
  const [section, setSection] = useState("");
  const [house, setHouse] = useState("");
  const [search, setSearch] = useState("");
  const { data: sections = [] } = useSections();
  const { data: houses = [] } = useHouses();
  const { data: rows = [], isLoading } = usePastoralStudents({ section: section || undefined, house: house || undefined, search: search || undefined });

  const assign = useAssignPastoralStudent();
  const bulk = useBulkAssignPastoralStudents();
  const sync = useSyncPastoralStudents();

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [mentorFor, setMentorFor] = useState<Row | null>(null);
  const toggleSel = (id: string) => setSelected((p) => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const allSel = rows.length > 0 && rows.every((r: Row) => selected.has(r.student_id));

  const download = async () => {
    try {
      const blob = await pastoralApi.students.exportCsv(section || undefined);
      const url = URL.createObjectURL(blob); const a = document.createElement("a");
      a.href = url; a.download = "student-house.csv"; a.click(); URL.revokeObjectURL(url);
    } catch { toast.error("Export failed."); }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Pastoral</span><span>/</span><span className="text-brand-600 font-semibold">Pastoral Students</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2"><Users2 size={22} className="text-brand-600" /> Pastoral Students</h1>
      <p className="text-slate-500 text-sm mb-5">Assign mentors, houses and leaders across your students.</p>

      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-4 flex flex-wrap items-center gap-3">
        <select value={section} onChange={(e) => setSection(e.target.value)} className="input w-auto min-w-[150px]">
          <option value="">All Schools</option>
          {(sections as SchoolSection[]).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <select value={house} onChange={(e) => setHouse(e.target.value)} className="input w-auto min-w-[130px]">
          <option value="">All Houses</option>
          {houses.map((h: any) => <option key={h.id} value={h.id}>{h.name}</option>)}
        </select>
        <div className="relative flex-1 min-w-[180px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search students…" className="input pl-9" />
        </div>
        <div className="flex items-center gap-2 ml-auto">
          {canWrite && <button onClick={() => sync.mutate()} disabled={sync.isPending} className="btn-secondary gap-1.5 py-1.5">{sync.isPending ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} Sync Students</button>}
          <button onClick={download} className="btn-secondary gap-1.5 py-1.5"><Download size={14} /> Export Student House</button>
        </div>
      </div>

      {canWrite && selected.size > 0 && (
        <div className="bg-brand-50 border border-brand-200 rounded-xl px-4 py-2.5 mb-3 flex flex-wrap items-center gap-3">
          <span className="text-sm font-semibold text-brand-700">{selected.size} selected</span>
          <select onChange={(e) => { if (e.target.value) { bulk.mutate({ student_ids: [...selected], house_id: e.target.value }); setSelected(new Set()); } e.target.value = ""; }} className="input w-auto py-1 text-sm">
            <option value="">Assign to house…</option>
            {houses.map((h: any) => <option key={h.id} value={h.id}>{h.name}</option>)}
          </select>
          <button onClick={() => { bulk.mutate({ student_ids: [...selected], is_leader: true }); setSelected(new Set()); }} className="btn-secondary py-1 text-xs">Mark as Leaders</button>
          <button onClick={() => { bulk.mutate({ student_ids: [...selected], is_leader: false }); setSelected(new Set()); }} className="btn-secondary py-1 text-xs">Unmark Leaders</button>
          <button onClick={() => setSelected(new Set())} className="text-xs text-slate-500 hover:text-slate-700 ml-auto">Clear</button>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">
            {canWrite && <th className="px-4 py-3 w-10"><input type="checkbox" checked={allSel} onChange={(e) => setSelected(e.target.checked ? new Set(rows.map((r: Row) => r.student_id)) : new Set())} /></th>}
            {["Student", "Class", "House", "Mentor", "Leader"].map((h) => <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}
          </tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              <tr><td colSpan={6} className="py-12 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={6} className="py-12 text-center text-sm text-slate-400">No students match.</td></tr>
            ) : rows.map((r: Row) => (
              <tr key={r.student_id} className="hover:bg-slate-50/70">
                {canWrite && <td className="px-4 py-3"><input type="checkbox" checked={selected.has(r.student_id)} onChange={() => toggleSel(r.student_id)} /></td>}
                <td className="px-4 py-3 text-sm font-semibold text-slate-800">{r.student_name}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{r.class_name || "—"}</td>
                <td className="px-4 py-3">
                  {canWrite ? (
                    <select value={r.house_id || ""} onChange={(e) => assign.mutate({ studentId: r.student_id, data: { house_id: e.target.value || null } })} className="input w-auto py-1 text-sm min-w-[120px]">
                      <option value="">—</option>
                      {houses.map((h: any) => <option key={h.id} value={h.id}>{h.name}</option>)}
                    </select>
                  ) : <span className="text-sm text-slate-600">{r.house_name || "—"}</span>}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-600">{r.mentor_name || "None"}</span>
                    {canWrite && <button onClick={() => setMentorFor(r)} className="text-slate-400 hover:text-brand-600 p-1" title="Set mentor"><UserCog size={14} /></button>}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <input type="checkbox" checked={r.is_leader} disabled={!canWrite} onChange={(e) => assign.mutate({ studentId: r.student_id, data: { is_leader: e.target.checked } })} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {mentorFor && (
        <MentorModal row={mentorFor} onClose={() => setMentorFor(null)}
          onAssign={(mentorId) => { assign.mutate({ studentId: mentorFor.student_id, data: { mentor_id: mentorId } }); setMentorFor(null); }} />
      )}
    </div>
  );
}

function MentorModal({ row, onClose, onAssign }: { row: Row; onClose: () => void; onAssign: (id: string | null) => void }) {
  const [id, setId] = useState<string>("");
  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">Set mentor · {row.student_name}</h3><button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
        <div className="p-5 space-y-3">
          <div><label className="label">Mentor (staff)</label><EntityPicker type="staff" value={id || null} onChange={(v) => setId(v || "")} /></div>
          <div className="flex justify-between">
            <button onClick={() => onAssign(null)} className="text-xs text-slate-500 hover:text-red-600">Clear mentor</button>
            <div className="flex gap-2">
              <button onClick={onClose} className="btn-secondary">Cancel</button>
              <button onClick={() => onAssign(id || null)} disabled={!id} className="btn-primary">Assign</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
