"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { adminListBySlug } from "@/components/hrm/hrNav";
import {
  useHrList, useCreateHrItem, useUpdateHrItem, useDeleteHrItem, type HrListItem,
} from "@/hooks/useHrAdmin";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import {
  Plus, Loader2, Trash2, Pencil, Check, X, AlertTriangle, ListChecks, Lock,
} from "lucide-react";

export default function AdminListPage() {
  const params = useParams();
  const slug = String(params.list ?? "");
  const meta = adminListBySlug(slug);
  const canWrite = useHasPermission("hr:write");

  if (!meta) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center">
          <AlertTriangle size={30} className="mx-auto mb-3 text-amber-400" />
          <p className="text-sm font-semibold text-slate-600">That admin list doesn’t exist.</p>
          <Link href="/dashboard/hrm/admin" className="mt-3 inline-block btn-secondary">Back to Admin</Link>
        </div>
      </div>
    );
  }
  return <ListManager meta={meta} canWrite={canWrite} />;
}

function ListManager({ meta, canWrite }: { meta: NonNullable<ReturnType<typeof adminListBySlug>>; canWrite: boolean }) {
  const { data, isLoading, isError, refetch } = useHrList(meta.type);
  const create = useCreateHrItem(meta.type);
  const [f, setF] = useState({ name: "", code: "", description: "" });
  const reset = () => setF({ name: "", code: "", description: "" });

  const submit = () => {
    if (!f.name.trim()) return;
    create.mutate(
      { name: f.name.trim(), code: f.code.trim() || null, description: f.description.trim() || null },
      { onSuccess: reset },
    );
  };

  const rows = data ?? [];
  const section = meta.section ?? { label: "Admin", href: "/dashboard/hrm/admin" };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <span>HR Manager</span><span>/</span>
          <Link href={section.href} className="hover:text-brand-600">{section.label}</Link><span>/</span>
          <span className="text-brand-600 font-semibold">{meta.label}</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">{meta.label}</h1>
        <p className="text-slate-500 text-sm mt-0.5">{meta.hint}</p>
      </div>

      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-5 flex flex-wrap gap-2 items-end">
          <div className="flex-1 min-w-[180px]">
            <label className="label">Name *</label>
            <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })}
              onKeyDown={(e) => e.key === "Enter" && submit()} className="input" placeholder={`Add a ${meta.label.replace(/s$/, "").toLowerCase()}…`} />
          </div>
          <div className="min-w-[110px]">
            <label className="label">Code</label>
            <input value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })}
              onKeyDown={(e) => e.key === "Enter" && submit()} className="input" placeholder="Optional" />
          </div>
          <div className="flex-1 min-w-[180px]">
            <label className="label">Description</label>
            <input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })}
              onKeyDown={(e) => e.key === "Enter" && submit()} className="input" placeholder="Optional" />
          </div>
          <button onClick={submit} disabled={!f.name.trim() || create.isPending} className="btn-primary gap-1.5">
            {create.isPending ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />} Add
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-12 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center">
          <AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" />
          <p className="text-sm font-semibold text-slate-600">Couldn’t load this list.</p>
          <button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button>
        </div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400">
          <ListChecks size={34} className="mb-3 opacity-40" />
          <p className="font-semibold">No entries yet</p>
          {canWrite && <p className="text-xs mt-1">Add your first {meta.label.toLowerCase()} above.</p>}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {rows.map((it) => <Row key={it.id} item={it} listType={meta.type} canWrite={canWrite} />)}
        </div>
      )}

      {!canWrite && <p className="text-xs text-slate-400 mt-4 flex items-center gap-1"><Lock size={12} /> HR admin lists are read-only for your role.</p>}
    </div>
  );
}

function Row({ item, listType, canWrite }: { item: HrListItem; listType: string; canWrite: boolean }) {
  const update = useUpdateHrItem(listType);
  const del = useDeleteHrItem(listType);
  const [editing, setEditing] = useState(false);
  const [e, setE] = useState({ name: item.name, code: item.code ?? "", description: item.description ?? "" });

  const save = () => {
    if (!e.name.trim()) return;
    update.mutate(
      { id: item.id, data: { name: e.name.trim(), code: e.code.trim() || null, description: e.description.trim() || null } },
      { onSuccess: () => setEditing(false) },
    );
  };

  if (editing) {
    return (
      <div className="flex flex-wrap items-end gap-2 px-4 py-3 bg-slate-50/60">
        <div className="flex-1 min-w-[160px]"><label className="label">Name</label><input value={e.name} onChange={(ev) => setE({ ...e, name: ev.target.value })} className="input" /></div>
        <div className="min-w-[100px]"><label className="label">Code</label><input value={e.code} onChange={(ev) => setE({ ...e, code: ev.target.value })} className="input" /></div>
        <div className="flex-1 min-w-[160px]"><label className="label">Description</label><input value={e.description} onChange={(ev) => setE({ ...e, description: ev.target.value })} className="input" /></div>
        <button onClick={save} disabled={update.isPending} className="btn-primary gap-1">{update.isPending ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} Save</button>
        <button onClick={() => { setEditing(false); setE({ name: item.name, code: item.code ?? "", description: item.description ?? "" }); }} className="btn-secondary gap-1"><X size={14} /> Cancel</button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className={cn("text-sm font-semibold truncate", item.is_active ? "text-slate-800" : "text-slate-400 line-through")}>{item.name}</p>
          {item.code && <span className="badge bg-slate-100 text-slate-500 border-slate-200">{item.code}</span>}
        </div>
        {item.description && <p className="text-xs text-slate-400 truncate mt-0.5">{item.description}</p>}
      </div>

      {canWrite ? (
        <button
          onClick={() => update.mutate({ id: item.id, data: { is_active: !item.is_active } })}
          title={item.is_active ? "Active — click to deactivate" : "Inactive — click to activate"}
          className={cn("text-[11px] font-bold uppercase tracking-wide px-2 py-1 rounded-full border transition-colors",
            item.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100" : "bg-slate-100 text-slate-400 border-slate-200 hover:bg-slate-200")}
        >
          {item.is_active ? "Active" : "Inactive"}
        </button>
      ) : (
        <span className={cn("text-[11px] font-bold uppercase tracking-wide px-2 py-1 rounded-full border", item.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-400 border-slate-200")}>{item.is_active ? "Active" : "Inactive"}</span>
      )}

      {canWrite && (
        <div className="flex items-center gap-0.5">
          <button onClick={() => setEditing(true)} className="text-slate-400 hover:text-brand-600 p-1.5" title="Edit"><Pencil size={14} /></button>
          <button onClick={() => { if (confirm(`Remove “${item.name}”?`)) del.mutate(item.id); }} className="text-slate-400 hover:text-red-600 p-1.5" title="Remove"><Trash2 size={14} /></button>
        </div>
      )}
    </div>
  );
}
