"use client";

import { useState } from "react";
import {
  useTalentCandidates, useCreateCandidate, useUpdateCandidate, useDeleteCandidate,
} from "@/hooks/usePeople";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import {
  Star, Plus, X, Loader2, Edit2, Trash2, AlertTriangle, Search, Briefcase,
} from "lucide-react";
import type { TalentCandidate } from "@/types";

const STAGES = ["applied", "screening", "interview", "offer", "hired", "rejected"];

const STAGE_STYLE: Record<string, string> = {
  applied: "bg-slate-50 text-slate-600 border-slate-200",
  screening: "bg-blue-50 text-blue-700 border-blue-200",
  interview: "bg-indigo-50 text-indigo-700 border-indigo-200",
  offer: "bg-amber-50 text-amber-700 border-amber-200",
  hired: "bg-emerald-50 text-emerald-700 border-emerald-200",
  rejected: "bg-rose-50 text-rose-700 border-rose-200",
};

const EMPTY = {
  full_name: "", email: "", phone: "", role_applied: "", source: "",
  stage: "applied", rating: "", notes: "",
};

export default function TalentPoolPage() {
  const canWrite = useHasPermission("hr:write");
  const [search, setSearch] = useState("");
  const [stageFilter, setStageFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<TalentCandidate | null>(null);
  const [form, setForm] = useState({ ...EMPTY });

  const params: { search?: string; stage?: string } = {};
  if (search.trim()) params.search = search.trim();
  if (stageFilter) params.stage = stageFilter;
  const { data, isLoading, isError, refetch } = useTalentCandidates(
    Object.keys(params).length ? params : undefined,
  );
  const createC = useCreateCandidate();
  const updateC = useUpdateCandidate();
  const deleteC = useDeleteCandidate();

  const reset = () => { setForm({ ...EMPTY }); setEditing(null); setShowForm(false); };
  const openNew = () => { setForm({ ...EMPTY }); setEditing(null); setShowForm(true); };
  const openEdit = (c: TalentCandidate) => {
    setForm({
      full_name: c.full_name,
      email: c.email ?? "",
      phone: c.phone ?? "",
      role_applied: c.role_applied ?? "",
      source: c.source ?? "",
      stage: c.stage,
      rating: c.rating?.toString() ?? "",
      notes: c.notes ?? "",
    });
    setEditing(c);
    setShowForm(true);
  };

  const submit = () => {
    const payload = {
      full_name: form.full_name.trim(),
      email: form.email || null,
      phone: form.phone || null,
      role_applied: form.role_applied || null,
      source: form.source || null,
      stage: form.stage,
      rating: form.rating ? Number(form.rating) : null,
      notes: form.notes || null,
    };
    if (editing) {
      updateC.mutate({ id: editing.id, data: payload }, { onSuccess: reset });
    } else {
      createC.mutate(payload, { onSuccess: reset });
    }
  };

  const rows = data?.items;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>People &amp; HR</span><span>/</span>
            <span className="text-brand-600 font-semibold">Talent Pool</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Talent Pool</h1>
          <p className="text-slate-500 text-sm mt-0.5">Recruitment pipeline for prospective staff.</p>
        </div>
        {canWrite && (
          <button onClick={openNew} className="btn-primary gap-2"><Plus size={15} /> Add Candidate</button>
        )}
      </div>

      <div className="flex flex-wrap gap-3 mb-5">
        <div className="relative max-w-xs flex-1 min-w-[200px]">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name, email, role…" className="input pl-9" />
        </div>
        <select value={stageFilter} onChange={(e) => setStageFilter(e.target.value)} className="input max-w-[180px] capitalize">
          <option value="">All stages</option>
          {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">{editing ? "Edit Candidate" : "New Candidate"}</h2>
            <button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Full Name *</label>
              <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Role Applied</label>
              <input value={form.role_applied} onChange={(e) => setForm({ ...form, role_applied: e.target.value })} className="input" placeholder="e.g. Mathematics Teacher" />
            </div>
            <div>
              <label className="label">Email</label>
              <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Phone</label>
              <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Source</label>
              <input value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} className="input" placeholder="referral / job board / walk-in" />
            </div>
            <div>
              <label className="label">Stage</label>
              <select value={form.stage} onChange={(e) => setForm({ ...form, stage: e.target.value })} className="input capitalize">
                {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Rating</label>
              <select value={form.rating} onChange={(e) => setForm({ ...form, rating: e.target.value })} className="input">
                <option value="">—</option>
                {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n} / 5</option>)}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="label">Notes</label>
              <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="input" rows={3} />
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={reset} className="btn-secondary">Cancel</button>
            <button onClick={submit} disabled={!form.full_name.trim() || createC.isPending || updateC.isPending} className="btn-primary gap-2">
              {(createC.isPending || updateC.isPending) && <Loader2 size={15} className="animate-spin" />}
              {editing ? "Update" : "Add"}
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-slate-50/80 border-b border-slate-100">
              {["Candidate", "Role", "Stage", "Rating", "Source", ""].map((h) => (
                <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i}>{Array.from({ length: 6 }).map((_, j) => (
                  <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>
                ))}</tr>
              ))
            ) : isError ? (
              <tr>
                <td colSpan={6} className="py-14 text-center">
                  <AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" />
                  <p className="text-sm font-semibold text-slate-600">Couldn’t load candidates.</p>
                  <button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button>
                </td>
              </tr>
            ) : rows && rows.length > 0 ? (
              rows.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4">
                    <p className="text-sm font-semibold text-slate-800">{c.full_name}</p>
                    <p className="text-xs text-slate-500">{c.email || c.phone || "—"}</p>
                  </td>
                  <td className="px-5 py-4"><span className="text-sm text-slate-600">{c.role_applied || "—"}</span></td>
                  <td className="px-5 py-4">
                    {canWrite ? (
                      <select
                        value={c.stage}
                        onChange={(e) => updateC.mutate({ id: c.id, data: { stage: e.target.value } })}
                        className={cn("input py-1 text-xs capitalize w-32 border", STAGE_STYLE[c.stage] || "")}
                      >
                        {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                    ) : (
                      <span className={cn("badge capitalize", STAGE_STYLE[c.stage] || "")}>{c.stage}</span>
                    )}
                  </td>
                  <td className="px-5 py-4">
                    {c.rating ? (
                      <span className="inline-flex items-center gap-1 text-sm text-slate-700">
                        <Star size={13} className="text-amber-500" fill="currentColor" /> {c.rating}/5
                      </span>
                    ) : <span className="text-slate-300">—</span>}
                  </td>
                  <td className="px-5 py-4"><span className="text-xs text-slate-500">{c.source || "—"}</span></td>
                  <td className="px-5 py-4">
                    {canWrite && (
                      <div className="flex items-center gap-1">
                        <button onClick={() => openEdit(c)} className="text-slate-400 hover:text-brand-600 p-1" title="Edit"><Edit2 size={14} /></button>
                        <button onClick={() => { if (confirm("Remove this candidate?")) deleteC.mutate(c.id); }} className="text-slate-400 hover:text-red-600 p-1" title="Delete"><Trash2 size={14} /></button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6} className="py-16 text-center text-slate-400">
                  <Briefcase size={36} className="mx-auto mb-3 opacity-40" />
                  <p className="font-semibold">No candidates yet</p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
