"use client";

import { useState } from "react";
import { useCustomFields, useCreateField, useDeleteField } from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { FolderOpen, Plus, X, Loader2, Trash2, AlertTriangle } from "lucide-react";

const ENTITIES = ["student", "staff", "teacher"];
const TYPES = ["text", "number", "date", "boolean", "select"];

export default function CustomFieldsPage() {
  const canWrite = useHasPermission("settings:write");
  const [entity, setEntity] = useState("student");
  const { data, isLoading, isError, refetch } = useCustomFields(entity);
  const create = useCreateField();
  const del = useDeleteField();
  const [show, setShow] = useState(false);
  const [f, setF] = useState({ field_key: "", label: "", field_type: "text", options: "", required: false });
  const reset = () => { setF({ field_key: "", label: "", field_type: "text", options: "", required: false }); setShow(false); };

  const submit = () => create.mutate({
    entity_type: entity, field_key: f.field_key.trim(), label: f.label.trim(), field_type: f.field_type,
    options: f.field_type === "select" && f.options ? f.options.split(",").map((s) => s.trim()).filter(Boolean) : null, required: f.required,
  }, { onSuccess: reset });

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Administration</span><span>/</span><span className="text-brand-600 font-semibold">Custom Fields</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Custom Fields</h1>
          <p className="text-slate-500 text-sm mt-0.5">Define extra fields per entity type.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Field</button>}
      </div>

      <div className="mb-5"><select value={entity} onChange={(e) => setEntity(e.target.value)} className="input max-w-[180px] capitalize">{ENTITIES.map((x) => <option key={x} value={x}>{x}</option>)}</select></div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New Field — {entity}</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div><label className="label">Key *</label><input value={f.field_key} onChange={(e) => setF({ ...f, field_key: e.target.value })} className="input" placeholder="blood_group" /></div>
            <div><label className="label">Label *</label><input value={f.label} onChange={(e) => setF({ ...f, label: e.target.value })} className="input" placeholder="Blood Group" /></div>
            <div><label className="label">Type</label><select value={f.field_type} onChange={(e) => setF({ ...f, field_type: e.target.value })} className="input capitalize">{TYPES.map((t) => <option key={t} value={t}>{t}</option>)}</select></div>
            {f.field_type === "select" && <div><label className="label">Options (comma-sep)</label><input value={f.options} onChange={(e) => setF({ ...f, options: e.target.value })} className="input" placeholder="A+, A-, O+" /></div>}
            <div className="flex items-center gap-2 mt-6"><input id="req" type="checkbox" checked={f.required} onChange={(e) => setF({ ...f, required: e.target.checked })} /><label htmlFor="req" className="text-xs font-medium text-slate-700">Required</label></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!f.field_key.trim() || !f.label.trim() || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create</button></div>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-12 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load fields.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : (data ?? []).length > 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {data!.map((d) => (
            <div key={d.id} className="flex items-center gap-3 px-5 py-3">
              <span className="text-sm font-semibold text-slate-800">{d.label}</span>
              <span className="text-xs font-mono text-slate-400">{d.field_key}</span>
              <span className="badge bg-slate-50 text-slate-600 border-slate-200 capitalize">{d.field_type}</span>
              {d.required && <span className="badge bg-rose-50 text-rose-700 border-rose-200">required</span>}
              {canWrite && <button onClick={() => del.mutate(d.id)} className="text-slate-400 hover:text-red-600 p-1 ml-auto"><Trash2 size={14} /></button>}
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><FolderOpen size={36} className="mb-3 opacity-40" /><p className="font-semibold">No custom fields for {entity}</p></div>
      )}
    </div>
  );
}
