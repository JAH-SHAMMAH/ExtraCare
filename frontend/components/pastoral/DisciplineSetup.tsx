"use client";

import { useState } from "react";
import {
  useSanctionGroups, useCreateSanctionGroup, useUpdateSanctionGroup, useDeleteSanctionGroup,
  useDisciplinaryActions, useCreateDisciplinaryAction, useUpdateDisciplinaryAction, useDeleteDisciplinaryAction,
  useCommittees, useCreateCommittee, useDeleteCommittee, useAddCommitteeMember, useRemoveCommitteeMember,
} from "@/hooks/usePastoral";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn } from "@/lib/utils";
import { Plus, Trash2, Loader2, Power, UserPlus, Users } from "lucide-react";

type Sub = "groups" | "actions" | "committees";
const SUBS: [Sub, string][] = [["groups", "Sanction Groups"], ["actions", "Actions"], ["committees", "Committees"]];
const SEVERITIES = ["minor", "major", "severe"];

export function DisciplineSetup({ canWrite }: { canWrite: boolean }) {
  const [sub, setSub] = useState<Sub>("groups");
  return (
    <div>
      <div className="inline-flex gap-1 bg-slate-100 rounded-lg p-1 mb-5">
        {SUBS.map(([k, l]) => (
          <button key={k} onClick={() => setSub(k)} className={cn("px-3 py-1.5 text-xs font-semibold rounded-md transition", sub === k ? "bg-white text-brand-700 shadow-sm" : "text-slate-500 hover:text-slate-700")}>{l}</button>
        ))}
      </div>
      {sub === "groups" ? <Groups canWrite={canWrite} /> : sub === "actions" ? <Actions canWrite={canWrite} /> : <Committees canWrite={canWrite} />}
    </div>
  );
}

function Groups({ canWrite }: { canWrite: boolean }) {
  const { data: rows = [], isLoading } = useSanctionGroups();
  const create = useCreateSanctionGroup();
  const update = useUpdateSanctionGroup();
  const del = useDeleteSanctionGroup();
  const [f, setF] = useState({ name: "", description: "" });

  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[160px]"><label className="label">Group name</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="e.g. Major" /></div>
          <div className="flex-1 min-w-[160px]"><label className="label">Description</label><input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className="input" /></div>
          <button onClick={() => f.name.trim() && create.mutate({ name: f.name.trim(), description: f.description || null }, { onSuccess: () => setF({ name: "", description: "" }) })} disabled={!f.name.trim() || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add Group</button>
        </div>
      )}
      <SimpleList loading={isLoading} rows={rows} canWrite={canWrite} label={(r) => r.name} sub={(r) => r.description}
        onToggle={(r) => update.mutate({ id: r.id, data: { is_active: !r.is_active } })} onDelete={(r) => del.mutate(r.id)} />
    </div>
  );
}

function Actions({ canWrite }: { canWrite: boolean }) {
  const { data: rows = [], isLoading } = useDisciplinaryActions();
  const { data: groups = [] } = useSanctionGroups();
  const create = useCreateDisciplinaryAction();
  const update = useUpdateDisciplinaryAction();
  const del = useDeleteDisciplinaryAction();
  const [f, setF] = useState({ name: "", severity: "minor", sanction_group_id: "", description: "" });

  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[150px]"><label className="label">Action name</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="e.g. Detention" /></div>
          <div><label className="label">Severity</label><select value={f.severity} onChange={(e) => setF({ ...f, severity: e.target.value })} className="input capitalize">{SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}</select></div>
          <div><label className="label">Group</label><select value={f.sanction_group_id} onChange={(e) => setF({ ...f, sanction_group_id: e.target.value })} className="input"><option value="">—</option>{(groups as any[]).map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</select></div>
          <button onClick={() => f.name.trim() && create.mutate({ name: f.name.trim(), severity: f.severity, sanction_group_id: f.sanction_group_id || null, description: f.description || null }, { onSuccess: () => setF({ name: "", severity: "minor", sanction_group_id: "", description: "" }) })} disabled={!f.name.trim() || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add Action</button>
        </div>
      )}
      <SimpleList loading={isLoading} rows={rows} canWrite={canWrite}
        label={(r) => <>{r.name} <span className={cn("badge ml-1", r.severity === "severe" ? "bg-red-50 text-red-700 border-red-200" : r.severity === "major" ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-slate-50 text-slate-500 border-slate-200")}>{r.severity}</span></>}
        sub={(r) => r.sanction_group_name}
        onToggle={(r) => update.mutate({ id: r.id, data: { is_active: !r.is_active } })} onDelete={(r) => del.mutate(r.id)} />
    </div>
  );
}

function Committees({ canWrite }: { canWrite: boolean }) {
  const { data: committees = [], isLoading } = useCommittees();
  const create = useCreateCommittee();
  const del = useDeleteCommittee();
  const addMember = useAddCommitteeMember();
  const removeMember = useRemoveCommitteeMember();
  const [f, setF] = useState({ name: "", description: "" });
  const [memberDraft, setMemberDraft] = useState<Record<string, { user_id: string | null; role: string }>>({});

  const draft = (cid: string) => memberDraft[cid] || { user_id: null, role: "" };

  return (
    <div className="space-y-4">
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[160px]"><label className="label">Committee name</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="e.g. Senior Discipline Panel" /></div>
          <div className="flex-1 min-w-[160px]"><label className="label">Description</label><input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className="input" /></div>
          <button onClick={() => f.name.trim() && create.mutate({ name: f.name.trim(), description: f.description || null }, { onSuccess: () => setF({ name: "", description: "" }) })} disabled={!f.name.trim() || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add Committee</button>
        </div>
      )}
      {isLoading ? (
        <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : (committees as any[]).length === 0 ? (
        <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">No committees yet.</p>
      ) : (
        <div className="space-y-3">
          {(committees as any[]).map((c) => (
            <div key={c.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-start justify-between mb-3">
                <div><h3 className="text-sm font-bold text-slate-900 flex items-center gap-2"><Users size={15} className="text-slate-400" /> {c.name}</h3>{c.description && <p className="text-xs text-slate-400 mt-0.5">{c.description}</p>}</div>
                {canWrite && <button onClick={() => { if (confirm(`Delete ${c.name}?`)) del.mutate(c.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>}
              </div>
              <div className="space-y-1.5">
                {(c.members || []).length === 0 ? <p className="text-xs text-slate-400">No members.</p> : (c.members as any[]).map((m) => (
                  <div key={m.id} className="flex items-center justify-between text-sm bg-slate-50 rounded-lg px-3 py-1.5">
                    <span className="text-slate-700">{m.user_name || m.user_id.slice(0, 8)}{m.role_label ? <span className="text-slate-400"> · {m.role_label}</span> : null}</span>
                    {canWrite && <button onClick={() => removeMember.mutate(m.id)} className="text-slate-400 hover:text-red-600"><Trash2 size={13} /></button>}
                  </div>
                ))}
              </div>
              {canWrite && (
                <div className="flex flex-wrap items-end gap-2 mt-3 pt-3 border-t border-slate-100">
                  <div className="flex-1 min-w-[180px]"><label className="label">Add member</label><EntityPicker type="staff" value={draft(c.id).user_id} onChange={(id) => setMemberDraft((p) => ({ ...p, [c.id]: { ...draft(c.id), user_id: id } }))} /></div>
                  <input value={draft(c.id).role} onChange={(e) => setMemberDraft((p) => ({ ...p, [c.id]: { ...draft(c.id), role: e.target.value } }))} className="input w-32" placeholder="Role (opt.)" />
                  <button onClick={() => { const d = draft(c.id); if (d.user_id) addMember.mutate({ id: c.id, data: { user_id: d.user_id, role_label: d.role || null } }, { onSuccess: () => setMemberDraft((p) => ({ ...p, [c.id]: { user_id: null, role: "" } })) }); }} disabled={!draft(c.id).user_id || addMember.isPending} className="btn-secondary gap-1.5"><UserPlus size={14} /> Add</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SimpleList({ loading, rows, label, sub, onToggle, onDelete, canWrite }: {
  loading: boolean; rows: any[]; label: (r: any) => React.ReactNode; sub: (r: any) => React.ReactNode;
  onToggle: (r: any) => void; onDelete: (r: any) => void; canWrite: boolean;
}) {
  if (loading) return <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>;
  if (rows.length === 0) return <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">Nothing configured yet.</p>;
  return (
    <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
      {rows.map((r) => (
        <div key={r.id} className="flex items-center justify-between px-5 py-3 gap-3">
          <div className="min-w-0"><p className="text-sm font-semibold text-slate-800">{label(r)}</p>{sub(r) && <p className="text-xs text-slate-400 truncate">{sub(r)}</p>}</div>
          <div className="flex items-center gap-2 shrink-0">
            <span className={cn("badge", r.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200")}>{r.is_active ? "Active" : "Inactive"}</span>
            {canWrite && <>
              <button onClick={() => onToggle(r)} className="text-slate-400 hover:text-amber-600 p-1"><Power size={15} /></button>
              <button onClick={() => { if (confirm("Delete this?")) onDelete(r); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>
            </>}
          </div>
        </div>
      ))}
    </div>
  );
}
