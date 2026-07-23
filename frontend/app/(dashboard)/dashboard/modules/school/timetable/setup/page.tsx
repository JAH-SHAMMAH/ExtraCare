"use client";

import { useEffect, useState } from "react";
import {
  useTimetableSettings, useUpdateTimetableSettings,
  usePeriodGroups, useCreatePeriodGroup, useUpdatePeriodGroup, useDeletePeriodGroup,
  useSubjectGroups, useCreateSubjectGroup, useDeleteSubjectGroup,
} from "@/hooks/useTimetableModule";
import { useSubjects } from "@/hooks/useSchool";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Clock, Plus, X, Loader2, Trash2, Edit2, Save } from "lucide-react";
import type { PeriodGroup, SubjectGroup } from "@/types";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
type Tab = "general" | "subject" | "period";
const TABS: [Tab, string][] = [["general", "General Setup"], ["subject", "Subject Group Setup"], ["period", "Period Group Setup"]];

function OnOff({ on, onChange, disabled }: { on: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button type="button" disabled={disabled} onClick={() => onChange(!on)}
      className={cn("inline-flex items-center rounded px-4 py-1.5 text-xs font-bold text-white w-16 justify-center", on ? "bg-emerald-500" : "bg-rose-500", disabled && "opacity-50 cursor-not-allowed")}>
      {on ? "ON" : "OFF"}
    </button>
  );
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">{title}</h3><button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
        {children}
      </div>
    </div>
  );
}

export default function TimetableSetupPage() {
  const canWrite = useHasPermission("school:timetable:write");
  const [tab, setTab] = useState<Tab>("general");
  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>TimeTable</span><span>/</span><span className="text-brand-600 font-semibold">TimeTable Setup</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">TimeTable Setup</h1>
      </div>
      <div className="flex items-center gap-1 border-b border-slate-200 mb-6 flex-wrap">
        {TABS.map(([k, label]) => <button key={k} onClick={() => setTab(k)} className={cn("px-4 py-2.5 text-sm font-bold border-b-2 -mb-px", tab === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-400 hover:text-slate-600")}>{label}</button>)}
      </div>
      {tab === "general" && <GeneralTab canWrite={canWrite} />}
      {tab === "subject" && <SubjectGroupTab canWrite={canWrite} />}
      {tab === "period" && <PeriodGroupTab canWrite={canWrite} />}
    </div>
  );
}

function GeneralTab({ canWrite }: { canWrite: boolean }) {
  const { data } = useTimetableSettings();
  const { data: pgData } = usePeriodGroups();
  const update = useUpdateTimetableSettings();
  const [f, setF] = useState<any>(null);
  const s = f ?? data ?? { enable_even_odd_week: false, enable_subject_grouping: false, default_period_group_id: "", subject_group_type: "", week_start_day: "Monday" };
  const groups: PeriodGroup[] = pgData?.items ?? [];
  const save = () => update.mutate({ enable_even_odd_week: s.enable_even_odd_week, enable_subject_grouping: s.enable_subject_grouping, default_period_group_id: s.default_period_group_id || null, subject_group_type: s.subject_group_type || null, week_start_day: s.week_start_day });

  return (
    <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100 max-w-2xl">
      <div className="px-6 py-4 flex items-center justify-between"><span className="text-sm font-semibold text-slate-700">Enable Even / Odd Week</span><OnOff on={!!s.enable_even_odd_week} disabled={!canWrite} onChange={(v) => setF({ ...s, enable_even_odd_week: v })} /></div>
      <div className="px-6 py-4 flex items-center justify-between"><span className="text-sm font-semibold text-slate-700">Enable Subject Grouping</span><OnOff on={!!s.enable_subject_grouping} disabled={!canWrite} onChange={(v) => setF({ ...s, enable_subject_grouping: v })} /></div>
      <div className="px-6 py-4 flex items-center justify-between gap-4"><span className="text-sm font-semibold text-slate-700">Default Period Group</span><select value={s.default_period_group_id || ""} onChange={(e) => setF({ ...s, default_period_group_id: e.target.value })} disabled={!canWrite} className="input max-w-[240px]"><option value="">—</option>{groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</select></div>
      <div className="px-6 py-4 flex items-center justify-between gap-4"><span className="text-sm font-semibold text-slate-700">Subject Group Type</span><input value={s.subject_group_type || ""} onChange={(e) => setF({ ...s, subject_group_type: e.target.value })} disabled={!canWrite} className="input max-w-[240px]" placeholder="optional" /></div>
      <div className="px-6 py-4 flex items-center justify-between gap-4"><span className="text-sm font-semibold text-slate-700">Week Start Day</span><select value={s.week_start_day} onChange={(e) => setF({ ...s, week_start_day: e.target.value })} disabled={!canWrite} className="input max-w-[240px]">{DAYS.map((d) => <option key={d} value={d}>{d}</option>)}</select></div>
      {canWrite && <div className="px-6 py-4 flex justify-center"><button onClick={save} disabled={update.isPending} className="btn-primary gap-2">{update.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Save Settings</button></div>}
    </div>
  );
}

function SubjectGroupTab({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading } = useSubjectGroups();
  const { data: subjectsData } = useSubjects({ page_size: 200 });
  const create = useCreateSubjectGroup();
  const del = useDeleteSubjectGroup();
  const [show, setShow] = useState(false);
  const [form, setForm] = useState<{ name: string; year_group: string; subject_ids: string[] }>({ name: "", year_group: "", subject_ids: [] });
  const groups: SubjectGroup[] = data?.items ?? [];
  const subjects = subjectsData?.items ?? [];
  const nameOf = (id: string) => subjects.find((x: any) => x.id === id)?.name || id;

  return (
    <div>
      <div className="flex items-center justify-between mb-3"><h3 className="text-sm font-black uppercase tracking-widest text-slate-400">Subject Group Manager</h3>{canWrite && <button onClick={() => { setShow(true); setForm({ name: "", year_group: "", subject_ids: [] }); }} className="btn-primary gap-2"><Plus size={15} /> New Group</button>}</div>
      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Group Name", "Year Group", "Subjects", ""].map((h) => <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? <tr><td colSpan={4} className="px-5 py-10 text-center text-slate-400"><Loader2 className="animate-spin mx-auto" /></td></tr>
            : groups.length > 0 ? groups.map((g) => (
              <tr key={g.id} className="hover:bg-slate-50/70">
                <td className="px-5 py-3 text-sm font-semibold text-slate-800">{g.name}</td>
                <td className="px-5 py-3 text-sm text-slate-600">{g.year_group || "—"}</td>
                <td className="px-5 py-3 text-sm text-slate-600">{(g.subject_ids || []).map(nameOf).join(", ") || "—"}</td>
                <td className="px-5 py-3">{canWrite && <button onClick={() => { if (confirm("Delete group?")) del.mutate(g.id); }} className="p-1.5 rounded text-rose-500 hover:bg-rose-50"><Trash2 size={15} /></button>}</td>
              </tr>
            )) : <tr><td colSpan={4} className="py-14 text-center text-slate-400 font-semibold">No data available in table</td></tr>}
          </tbody>
        </table>
      </div>
      {show && (
        <Modal title="New Subject Group" onClose={() => setShow(false)}>
          <div className="px-6 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
            <div><label className="label">Group Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" /></div>
            <div><label className="label">Year Group</label><input value={form.year_group} onChange={(e) => setForm({ ...form, year_group: e.target.value })} className="input" placeholder="e.g. YEAR 11" /></div>
            <div>
              <label className="label">Subjects</label>
              <div className="border border-slate-200 rounded-lg p-2 max-h-48 overflow-y-auto space-y-1">
                {subjects.map((sub: any) => (
                  <label key={sub.id} className="flex items-center gap-2 text-sm px-2 py-1 rounded hover:bg-slate-50 cursor-pointer">
                    <input type="checkbox" checked={form.subject_ids.includes(sub.id)} onChange={(e) => setForm({ ...form, subject_ids: e.target.checked ? [...form.subject_ids, sub.id] : form.subject_ids.filter((x) => x !== sub.id) })} />
                    {sub.name}
                  </label>
                ))}
                {subjects.length === 0 && <p className="text-xs text-slate-400 px-2 py-1">No subjects yet.</p>}
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={() => setShow(false)} className="btn-secondary">Cancel</button><button onClick={() => create.mutate({ name: form.name.trim(), year_group: form.year_group || null, subject_ids: form.subject_ids }, { onSuccess: () => setShow(false) })} disabled={!form.name.trim() || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create</button></div>
        </Modal>
      )}
    </div>
  );
}

function PeriodGroupTab({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading } = usePeriodGroups();
  const create = useCreatePeriodGroup();
  const update = useUpdatePeriodGroup();
  const del = useDeletePeriodGroup();
  const [editing, setEditing] = useState<PeriodGroup | null>(null);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ name: "", year_group: "" });
  const groups: PeriodGroup[] = data?.items ?? [];

  const submit = () => {
    const payload = { name: form.name.trim(), year_group: form.year_group || null };
    if (editing) update.mutate({ id: editing.id, data: payload }, { onSuccess: () => setEditing(null) });
    else create.mutate(payload, { onSuccess: () => { setShow(false); setForm({ name: "", year_group: "" }); } });
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-3"><h3 className="text-sm font-black uppercase tracking-widest text-slate-400">Period Group Manager</h3>{canWrite && <button onClick={() => { setShow(true); setForm({ name: "", year_group: "" }); }} className="btn-primary gap-2"><Plus size={15} /> New Period Group</button>}</div>
      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Group Name", "Year Group", ""].map((h) => <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? <tr><td colSpan={3} className="px-5 py-10 text-center text-slate-400"><Loader2 className="animate-spin mx-auto" /></td></tr>
            : groups.length > 0 ? groups.map((g) => (
              <tr key={g.id} className="hover:bg-slate-50/70">
                <td className="px-5 py-3 text-sm font-semibold text-slate-800">{g.name}</td>
                <td className="px-5 py-3 text-sm text-slate-600">{g.year_group || "All Year Group"}</td>
                <td className="px-5 py-3">
                  {canWrite && <div className="flex items-center gap-1">
                    <button onClick={() => { setEditing(g); setForm({ name: g.name, year_group: g.year_group || "" }); }} className="p-1.5 rounded text-amber-600 hover:bg-amber-50"><Edit2 size={15} /></button>
                    <button onClick={() => { if (confirm("Delete period group?")) del.mutate(g.id); }} className="p-1.5 rounded text-rose-500 hover:bg-rose-50"><Trash2 size={15} /></button>
                  </div>}
                </td>
              </tr>
            )) : <tr><td colSpan={3} className="py-14 text-center text-slate-400 font-semibold">No data available in table</td></tr>}
          </tbody>
        </table>
      </div>
      {(show || editing) && (
        <Modal title={editing ? "Edit Period Group" : "New Period Group"} onClose={() => { setShow(false); setEditing(null); }}>
          <div className="px-6 py-4 space-y-4">
            <div><label className="label">Group Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" placeholder="e.g. SECONDARY" /></div>
            <div><label className="label">Year Group</label><input value={form.year_group} onChange={(e) => setForm({ ...form, year_group: e.target.value })} className="input" placeholder="e.g. All Year Group" /></div>
          </div>
          <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={() => { setShow(false); setEditing(null); }} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.name.trim() || create.isPending || update.isPending} className="btn-primary gap-2">{(create.isPending || update.isPending) && <Loader2 size={15} className="animate-spin" />}{editing ? "Save" : "Create"}</button></div>
        </Modal>
      )}
    </div>
  );
}
