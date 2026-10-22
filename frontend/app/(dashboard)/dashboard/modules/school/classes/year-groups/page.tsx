"use client";

import { useEffect, useMemo, useState } from "react";
import { useSections } from "@/hooks/usePlatform";
import {
  useYearGroups, useCreateYearGroup, useUpdateYearGroup, useDeleteYearGroup, useReorderYearGroups,
  type YearGroup,
} from "@/hooks/useSchool";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Loader2, Plus, Save, Pencil, Trash2, X, ChevronUp, ChevronDown, Layers } from "lucide-react";

const CATEGORIES = [
  { value: "active", label: "Active" },
  { value: "alumni", label: "Alumni" },
  { value: "prospective", label: "Prospective" },
];
const catBadge = (c: string) => c === "alumni" ? "bg-slate-100 text-slate-600 border-slate-200" : c === "prospective" ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-emerald-50 text-emerald-700 border-emerald-200";

export default function ManageYearGroupsPage() {
  const canWrite = useHasPermission("school:write");
  const { data: sections = [] } = useSections();
  const orderedSections = useMemo(() => [...sections].sort((a, b) => a.position - b.position), [sections]);
  const [schoolId, setSchoolId] = useState("");
  useEffect(() => { if (!schoolId && orderedSections.length) setSchoolId(orderedSections[0].id); }, [orderedSections, schoolId]);
  const schoolName = orderedSections.find((x) => x.id === schoolId)?.name ?? "";
  const { data: fetched = [], isLoading } = useYearGroups(schoolId || undefined);
  const create = useCreateYearGroup();
  const del = useDeleteYearGroup();
  const reorder = useReorderYearGroups();

  const [form, setForm] = useState({ name: "", short_code: "", category: "active", is_mock: false });
  const [editing, setEditing] = useState<string | null>(null);
  // Local order for the reorder-then-save flow.
  const [order, setOrder] = useState<YearGroup[]>([]);
  useEffect(() => { setOrder(fetched); }, [fetched]);
  const dirty = order.map((y) => y.id).join(",") !== fetched.map((y) => y.id).join(",");

  const add = () => {
    if (!form.name.trim()) return;
    create.mutate({ name: form.name.trim(), short_code: form.short_code.trim() || null, category: form.category, is_mock: form.is_mock, section_id: schoolId || null },
      { onSuccess: () => setForm({ name: "", short_code: "", category: "active", is_mock: false }) });
  };
  const move = (i: number, dir: -1 | 1) => {
    const j = i + dir;
    if (j < 0 || j >= order.length) return;
    const next = [...order];
    [next[i], next[j]] = [next[j], next[i]];
    setOrder(next);
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <nav className="flex flex-wrap items-center gap-x-2 text-sm font-bold text-slate-900 mb-5">
        <span>Home</span><span className="text-slate-300">•</span><span>Classes/YearGroups</span><span className="text-slate-300">•</span><span>Manage YearGroups</span>
      </nav>

      <section className="rounded-lg border border-emerald-900/70 bg-white overflow-hidden mb-6">
        <h2 className="bg-emerald-800 text-white font-bold tracking-wide px-4 py-3 text-lg uppercase">Select School to Create Levels For {schoolName}</h2>
        <div className="p-4">
          <label className="block text-xs font-extrabold uppercase tracking-widest text-slate-600 mb-2">Select School</label>
          <select value={schoolId} onChange={(e) => setSchoolId(e.target.value)} className="input uppercase">
            {orderedSections.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </div>
      </section>

      {/* Add form */}
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-5">
          <h2 className="text-sm font-bold text-slate-800 mb-3 uppercase">Add New Year Group For {schoolName}</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="md:col-span-2"><label className="label">Year group name</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} onKeyDown={(e) => e.key === "Enter" && add()} placeholder="e.g. Year 7" className="input" /></div>
            <div><label className="label">Short code</label><input value={form.short_code} onChange={(e) => setForm({ ...form, short_code: e.target.value })} placeholder="e.g. Y7, PN" className="input" /></div>
            <div><label className="label">Category</label><select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="input">{CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}</select></div>
          </div>
          <div className="flex items-center justify-between mt-3">
            <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer"><input type="checkbox" checked={form.is_mock} onChange={(e) => setForm({ ...form, is_mock: e.target.checked })} className="h-4 w-4 rounded border-slate-300" /> This is a mock class</label>
            <button onClick={add} disabled={create.isPending || !form.name.trim()} className="btn-primary gap-2">{create.isPending ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />} Add Year Group</button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-800">All Year Groups — {schoolName} ({order.length})</h2>
          {canWrite && dirty && <button onClick={() => reorder.mutate(order.map((y) => y.id))} disabled={reorder.isPending} className="btn-primary text-xs py-1.5 gap-1.5">{reorder.isPending ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Save order</button>}
        </div>
        <table className="w-full text-left min-w-[640px]">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["S/N", "Name", "Category", "Position", "Short Code", "Mock", ""].map((h) => <th key={h} className="px-4 py-2.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? <tr><td colSpan={7} className="px-4 py-8 text-center"><Loader2 className="animate-spin mx-auto text-slate-400" /></td></tr>
              : order.length === 0 ? <tr><td colSpan={7} className="px-4 py-10 text-center text-sm text-slate-400">No year groups yet.</td></tr>
                : order.map((y, i) => editing === y.id ? (
                  <EditRow key={y.id} yg={y} onDone={() => setEditing(null)} />
                ) : (
                  <tr key={y.id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 w-14 text-sm text-slate-400 tabular-nums">{i + 1}</td>
                    <td className="px-4 py-3 text-sm font-semibold text-slate-800">{y.name}</td>
                    <td className="px-4 py-3"><span className={cn("badge text-[10px] capitalize", catBadge(y.category))}>{y.category}</span></td>
                    <td className="px-4 py-3 text-sm text-slate-500 tabular-nums">
                      <div className="flex items-center gap-2">
                        <span>{i + 1}</span>
                        {canWrite && (
                          <div className="flex flex-col -my-1">
                            <button onClick={() => move(i, -1)} disabled={i === 0} className="text-slate-300 hover:text-brand-600 disabled:opacity-30" aria-label="Move up"><ChevronUp size={14} /></button>
                            <button onClick={() => move(i, 1)} disabled={i === order.length - 1} className="text-slate-300 hover:text-brand-600 disabled:opacity-30" aria-label="Move down"><ChevronDown size={14} /></button>
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-500">{y.short_code || "—"}</td>
                    <td className="px-4 py-3 text-sm text-slate-500">{y.is_mock ? "Yes" : "—"}</td>
                    <td className="px-4 py-3">
                      {canWrite && <div className="flex items-center justify-end gap-1.5">
                        <button onClick={() => setEditing(y.id)} className="text-slate-400 hover:text-brand-600 p-1"><Pencil size={14} /></button>
                        <button onClick={() => { if (confirm(`Delete "${y.name}"?`)) del.mutate(y.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>
                      </div>}
                    </td>
                  </tr>
                ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EditRow({ yg, onDone }: { yg: YearGroup; onDone: () => void }) {
  const update = useUpdateYearGroup();
  const [f, setF] = useState({ name: yg.name, short_code: yg.short_code || "", category: yg.category, is_mock: yg.is_mock });
  const save = () => {
    if (!f.name.trim()) return;
    update.mutate({ id: yg.id, data: { name: f.name.trim(), short_code: f.short_code.trim() || null, category: f.category, is_mock: f.is_mock } }, { onSuccess: onDone });
  };
  return (
    <tr className="bg-brand-50/30">
      <td className="px-4 py-2" />
      <td className="px-4 py-2"><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" autoFocus /></td>
      <td className="px-4 py-2"><select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} className="input">{CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}</select></td>
      <td className="px-4 py-2" />
      <td className="px-4 py-2"><input value={f.short_code} onChange={(e) => setF({ ...f, short_code: e.target.value })} className="input w-24" placeholder="Code" /></td>
      <td className="px-4 py-2"><label className="flex items-center gap-1.5 text-xs text-slate-600"><input type="checkbox" checked={f.is_mock} onChange={(e) => setF({ ...f, is_mock: e.target.checked })} className="h-4 w-4 rounded border-slate-300" /> Mock</label></td>
      <td className="px-4 py-2"><div className="flex items-center justify-end gap-1.5">
        <button onClick={save} disabled={update.isPending} className="btn-primary text-xs py-1 gap-1">{update.isPending ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />} Save</button>
        <button onClick={onDone} className="btn-secondary text-xs py-1"><X size={12} /></button>
      </div></td>
    </tr>
  );
}
