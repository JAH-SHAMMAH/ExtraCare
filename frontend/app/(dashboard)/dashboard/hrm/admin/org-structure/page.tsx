"use client";

import { useState } from "react";
import Link from "next/link";
import { useOrgUnits, useCreateOrgUnit, useUpdateOrgUnit, useDeleteOrgUnit, type OrgUnit } from "@/hooks/useHrOrg";
import { useStaff } from "@/hooks/useUsers";
import { cn } from "@/lib/utils";
import {
  Network, Plus, Pencil, Trash2, ChevronRight, ChevronDown, Loader2, AlertTriangle, UserRound,
} from "lucide-react";

const UNIT_TYPES = ["division", "department", "unit", "team"];
type Node = OrgUnit & { children: Node[] };

function buildTree(units: OrgUnit[]): Node[] {
  const byId = new Map<string, Node>();
  units.forEach((u) => byId.set(u.id, { ...u, children: [] }));
  const roots: Node[] = [];
  byId.forEach((n) => {
    const parent = n.parent_id ? byId.get(n.parent_id) : undefined;
    if (parent) parent.children.push(n); else roots.push(n);
  });
  return roots;
}

const blank = { name: "", unit_type: "", parent_id: "", head_user_id: "", description: "" };

export default function OrgStructurePage() {
  const { data, isLoading, isError, refetch } = useOrgUnits();
  const { data: staff } = useStaff();
  const create = useCreateOrgUnit();
  const update = useUpdateOrgUnit();
  const del = useDeleteOrgUnit();

  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [f, setF] = useState({ ...blank });
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const units = data ?? [];
  const tree = buildTree(units);
  const staffList: any[] = (staff as any[]) ?? [];

  const openCreate = (parentId = "") => { setEditingId(null); setF({ ...blank, parent_id: parentId }); setFormOpen(true); };
  const openEdit = (u: OrgUnit) => {
    setEditingId(u.id);
    setF({ name: u.name, unit_type: u.unit_type ?? "", parent_id: u.parent_id ?? "", head_user_id: u.head_user_id ?? "", description: u.description ?? "" });
    setFormOpen(true);
  };
  const close = () => { setFormOpen(false); setEditingId(null); setF({ ...blank }); };

  const submit = () => {
    if (!f.name.trim()) return;
    const payload = {
      name: f.name.trim(),
      unit_type: f.unit_type || null,
      parent_id: f.parent_id || null,
      head_user_id: f.head_user_id || null,
      description: f.description || null,
    };
    if (editingId) update.mutate({ id: editingId, data: payload }, { onSuccess: close });
    else create.mutate(payload, { onSuccess: close });
  };

  const toggle = (id: string) => setCollapsed((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const busy = create.isPending || update.isPending;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><Link href="/dashboard/hrm/admin" className="hover:text-brand-600">Admin</Link><span>/</span><span className="text-brand-600 font-semibold">Organization Structure</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Organization Structure</h1>
          <p className="text-slate-500 text-sm mt-0.5">Your reporting hierarchy — divisions, departments, units and teams.</p>
        </div>
        <button onClick={() => openCreate()} className="btn-primary gap-2"><Plus size={15} /> Add Unit</button>
      </div>

      {formOpen && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
          <h2 className="text-sm font-bold text-slate-800 mb-3">{editingId ? "Edit unit" : "New unit"}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div><label className="label">Name *</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="e.g. Academics" /></div>
            <div><label className="label">Type</label><input list="org-unit-types" value={f.unit_type} onChange={(e) => setF({ ...f, unit_type: e.target.value })} className="input" placeholder="division / department / unit / team" />
              <datalist id="org-unit-types">{UNIT_TYPES.map((t) => <option key={t} value={t} />)}</datalist>
            </div>
            <div><label className="label">Reports to</label>
              <select value={f.parent_id} onChange={(e) => setF({ ...f, parent_id: e.target.value })} className="input">
                <option value="">— Top level —</option>
                {units.filter((u) => u.id !== editingId).map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </select>
            </div>
            <div><label className="label">Head</label>
              <select value={f.head_user_id} onChange={(e) => setF({ ...f, head_user_id: e.target.value })} className="input">
                <option value="">— None —</option>
                {staffList.map((u) => <option key={u.id} value={u.id}>{u.full_name || u.email}</option>)}
              </select>
            </div>
            <div className="md:col-span-2"><label className="label">Description</label><input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className="input" placeholder="Optional" /></div>
          </div>
          <div className="flex justify-end gap-3">
            <button onClick={close} className="btn-secondary">Cancel</button>
            <button onClick={submit} disabled={!f.name.trim() || busy} className="btn-primary gap-2">{busy && <Loader2 size={15} className="animate-spin" />}{editingId ? "Save" : "Create"}</button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-12 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center">
          <AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" />
          <p className="text-sm font-semibold text-slate-600">Couldn’t load the structure.</p>
          <button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button>
        </div>
      ) : tree.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400">
          <Network size={34} className="mb-3 opacity-40" /><p className="font-semibold">No units yet</p>
          <p className="text-xs mt-1">Add your first division or department above.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 p-2">
          {tree.map((n) => <Row key={n.id} node={n} depth={0} collapsed={collapsed} toggle={toggle} onAddChild={openCreate} onEdit={openEdit} onDelete={(id) => { if (confirm("Remove this unit?")) del.mutate(id); }} />)}
        </div>
      )}
    </div>
  );
}

function Row({ node, depth, collapsed, toggle, onAddChild, onEdit, onDelete }: {
  node: Node; depth: number; collapsed: Set<string>;
  toggle: (id: string) => void; onAddChild: (parentId: string) => void; onEdit: (u: OrgUnit) => void; onDelete: (id: string) => void;
}) {
  const hasKids = node.children.length > 0;
  const isCollapsed = collapsed.has(node.id);
  return (
    <>
      <div className="group flex items-center gap-2 px-2 py-2 rounded-lg hover:bg-slate-50" style={{ paddingLeft: depth * 22 + 8 }}>
        <button onClick={() => hasKids && toggle(node.id)} className={cn("text-slate-400 shrink-0", !hasKids && "invisible")}>
          {isCollapsed ? <ChevronRight size={15} /> : <ChevronDown size={15} />}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-800 truncate">{node.name}</span>
            {node.unit_type && <span className="badge bg-slate-100 text-slate-500 border-slate-200 capitalize">{node.unit_type}</span>}
          </div>
          {node.head_name && <p className="text-xs text-slate-400 flex items-center gap-1"><UserRound size={11} /> {node.head_name}</p>}
        </div>
        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
          <button onClick={() => onAddChild(node.id)} className="text-slate-400 hover:text-brand-600 p-1.5" title="Add sub-unit"><Plus size={14} /></button>
          <button onClick={() => onEdit(node)} className="text-slate-400 hover:text-brand-600 p-1.5" title="Edit"><Pencil size={14} /></button>
          <button onClick={() => onDelete(node.id)} className="text-slate-400 hover:text-red-600 p-1.5" title="Remove"><Trash2 size={14} /></button>
        </div>
      </div>
      {!isCollapsed && node.children.map((c) => (
        <Row key={c.id} node={c} depth={depth + 1} collapsed={collapsed} toggle={toggle} onAddChild={onAddChild} onEdit={onEdit} onDelete={onDelete} />
      ))}
    </>
  );
}
