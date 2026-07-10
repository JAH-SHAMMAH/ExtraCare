"use client";

import { useState } from "react";
import Link from "next/link";
import { useCrmContacts, useSaveCrmContact, useDeleteCrmContact } from "@/hooks/useFeedbackExtras";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { ArrowLeft, Plus, Loader2, Edit2, Trash2, X, Contact } from "lucide-react";
import type { CRMContact } from "@/types";

const STAGES = ["new", "contacted", "engaged", "converted", "lost"];
const TYPES = ["prospective_parent", "vendor", "partner", "other"];
const STAGE_STYLE: Record<string, string> = {
  new: "bg-slate-50 text-slate-600 border-slate-200",
  contacted: "bg-blue-50 text-blue-700 border-blue-200",
  engaged: "bg-indigo-50 text-indigo-700 border-indigo-200",
  converted: "bg-emerald-50 text-emerald-700 border-emerald-200",
  lost: "bg-rose-50 text-rose-700 border-rose-200",
};
const BLANK = { name: "", email: "", phone: "", contact_type: "prospective_parent", stage: "new", source: "", notes: "" };

export default function CrmPage() {
  const canWrite = useHasPermission("school:write");
  const [stageFilter, setStageFilter] = useState("");
  const { data, isLoading } = useCrmContacts(stageFilter ? { stage: stageFilter } : undefined);
  const save = useSaveCrmContact();
  const remove = useDeleteCrmContact();
  const contacts: CRMContact[] = data?.items || [];

  const [editing, setEditing] = useState<string | null>(null);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState(BLANK);

  const reset = () => { setForm(BLANK); setEditing(null); setShow(false); };
  const startEdit = (c: CRMContact) => {
    setForm({ name: c.name, email: c.email || "", phone: c.phone || "", contact_type: c.contact_type, stage: c.stage, source: c.source || "", notes: c.notes || "" });
    setEditing(c.id); setShow(true);
  };
  const submit = () => {
    const payload = { name: form.name, email: form.email || null, phone: form.phone || null, contact_type: form.contact_type, stage: form.stage, source: form.source || null, notes: form.notes || null };
    save.mutate({ id: editing || undefined, data: payload }, { onSuccess: reset });
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <Link href="/dashboard/modules/school/feedback" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Feedback</Link>
      <div className="flex items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Feedback</span><span>/</span><span className="text-brand-600 font-semibold">CRM</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">CRM</h1>
          <p className="text-slate-500 text-sm mt-0.5">A light relationship pipeline — prospective parents, vendors and partners.</p>
        </div>
        {canWrite && !show && <button onClick={() => setShow(true)} className="btn-primary gap-2"><Plus size={16} /> New contact</button>}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4">
        <select value={stageFilter} onChange={(e) => setStageFilter(e.target.value)} className="input max-w-48 capitalize"><option value="">All stages</option>{STAGES.map((s) => <option key={s} value={s}>{s}</option>)}</select>
      </div>

      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">{editing ? "Edit contact" : "New contact"}</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={18} /></button></div>
          <div className="grid md:grid-cols-2 gap-4">
            <div><label className="label">Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" /></div>
            <div><label className="label">Type</label><select value={form.contact_type} onChange={(e) => setForm({ ...form, contact_type: e.target.value })} className="input capitalize">{TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}</select></div>
            <div><label className="label">Email</label><input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="input" /></div>
            <div><label className="label">Phone</label><input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="input" /></div>
            <div><label className="label">Stage</label><select value={form.stage} onChange={(e) => setForm({ ...form, stage: e.target.value })} className="input capitalize">{STAGES.map((s) => <option key={s} value={s}>{s}</option>)}</select></div>
            <div><label className="label">Source</label><input value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} className="input" placeholder="e.g. referral, walk-in" /></div>
            <div className="md:col-span-2"><label className="label">Notes</label><textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="input" rows={2} /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.name || save.isPending} className="btn-primary gap-2">{save.isPending && <Loader2 size={15} className="animate-spin" />}Save</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        {isLoading ? (
          <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
        ) : contacts.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-sm"><Contact size={30} className="mx-auto mb-2 opacity-50" />No contacts yet.</div>
        ) : (
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Name", "Type", "Contact", "Stage", ""].map((h) => (<th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>))}</tr></thead>
            <tbody className="divide-y divide-slate-50">
              {contacts.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-3 text-sm font-bold text-slate-900">{c.name}{c.source && <p className="text-xs font-normal text-slate-400">via {c.source}</p>}</td>
                  <td className="px-5 py-3 text-sm text-slate-600 capitalize">{c.contact_type.replace("_", " ")}</td>
                  <td className="px-5 py-3 text-xs text-slate-500">{c.email || "—"}{c.phone ? <span className="block">{c.phone}</span> : null}</td>
                  <td className="px-5 py-3"><span className={cn("badge capitalize", STAGE_STYLE[c.stage] || "bg-slate-50 text-slate-600 border-slate-200")}>{c.stage}</span></td>
                  <td className="px-5 py-3">
                    {canWrite ? (
                      <div className="flex items-center gap-3">
                        <button onClick={() => startEdit(c)} className="text-xs text-brand-600 font-semibold hover:underline inline-flex items-center gap-1"><Edit2 size={13} />Edit</button>
                        <button onClick={() => { if (confirm(`Delete "${c.name}"?`)) remove.mutate(c.id); }} className="text-xs text-rose-600 font-semibold hover:underline inline-flex items-center gap-1"><Trash2 size={13} />Delete</button>
                      </div>
                    ) : <span className="text-xs text-slate-300">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
