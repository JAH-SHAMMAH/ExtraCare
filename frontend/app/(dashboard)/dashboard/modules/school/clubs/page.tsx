"use client";

import { useState } from "react";
import {
  useClubs, useCreateClub, useUpdateClub, useDeleteClub,
  useClubSettings, useUpdateClubSettings,
  useClubGrades, useCreateClubGrade, useDeleteClubGrade,
  useClubCoordinators, useCreateClubCoordinator, useDeleteClubCoordinator,
  useClubDeadlines, useCreateClubDeadline, useDeleteClubDeadline,
} from "@/hooks/useSchoolExperience";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn } from "@/lib/utils";
import { Users2, Plus, X, Loader2, Trash2, Edit2, AlertTriangle } from "lucide-react";
import type { Club, ClubGrade, ClubCoordinator, ClubDeadline } from "@/types";

type Tab = "list" | "grade" | "coordinator" | "deadline";
const TABS: [Tab, string][] = [["list", "Club List"], ["grade", "Club Grade"], ["coordinator", "Club Coordinator"], ["deadline", "Enrollment Deadline"]];

function Toggle({ on, onChange, disabled }: { on: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button type="button" disabled={disabled} onClick={() => onChange(!on)}
      className={cn("inline-flex items-center rounded px-3 py-1.5 text-xs font-bold text-white", on ? "bg-emerald-500" : "bg-rose-500", disabled && "opacity-50 cursor-not-allowed")}>
      {on ? "Enabled" : "Disabled"}
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

export default function ManageClubsPage() {
  const canWrite = useHasPermission("school:clubs:write");
  const [tab, setTab] = useState<Tab>("list");

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Home</span><span>/</span><span className="text-brand-600 font-semibold">Clubs</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Manage Clubs</h1>
        <p className="text-slate-500 text-sm mt-0.5">Clubs, grading bands, coordinators, and enrolment deadlines.</p>
      </div>

      <div className="flex items-center gap-1 border-b border-slate-200 mb-6 flex-wrap">
        {TABS.map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)} className={cn("px-4 py-2.5 text-sm font-bold border-b-2 -mb-px uppercase tracking-wide", tab === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-400 hover:text-slate-600")}>{label}</button>
        ))}
      </div>

      {tab === "list" && <ClubListTab canWrite={canWrite} />}
      {tab === "grade" && <GradeTab canWrite={canWrite} />}
      {tab === "coordinator" && <CoordinatorTab canWrite={canWrite} />}
      {tab === "deadline" && <DeadlineTab canWrite={canWrite} />}
    </div>
  );
}

// ── Club List + settings ──────────────────────────────────────────────────────
function ClubListTab({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading, isError, refetch } = useClubs();
  const { data: settings } = useClubSettings();
  const updateSettings = useUpdateClubSettings();
  const create = useCreateClub();
  const update = useUpdateClub();
  const del = useDeleteClub();

  const [limit, setLimit] = useState("");
  const [editing, setEditing] = useState<Club | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ name: "", max_members: "" });

  const clubs: Club[] = data?.items ?? [];
  const limitValue = limit !== "" ? limit : String(settings?.club_limit ?? "");

  const openEdit = (c: Club) => { setEditing(c); setForm({ name: c.name, max_members: c.max_members != null ? String(c.max_members) : "" }); };
  const submit = () => {
    const payload = { name: form.name.trim(), max_members: form.max_members ? Number(form.max_members) : null };
    if (editing) update.mutate({ id: editing.id, data: payload }, { onSuccess: () => setEditing(null) });
    else create.mutate(payload, { onSuccess: () => { setShowNew(false); setForm({ name: "", max_members: "" }); } });
  };

  return (
    <div>
      {/* Settings */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6 space-y-4">
        <h3 className="text-sm font-bold text-slate-800">Club Management</h3>
        <div className="flex items-center gap-3 flex-wrap">
          <label className="text-sm font-semibold text-slate-600 w-52">Set Club Limit:</label>
          <input type="number" value={limitValue} onChange={(e) => setLimit(e.target.value)} disabled={!canWrite} className="input max-w-[200px]" />
          {canWrite && <button onClick={() => updateSettings.mutate({ club_limit: Number(limitValue) })} disabled={updateSettings.isPending} className="btn-primary py-2">Update</button>}
        </div>
        <div className="flex items-center gap-3"><label className="text-sm font-semibold text-slate-600 w-52">Set Auto Approve:</label><Toggle on={!!settings?.auto_approve} disabled={!canWrite} onChange={(v) => updateSettings.mutate({ auto_approve: v })} /></div>
        <div className="flex items-center gap-3"><label className="text-sm font-semibold text-slate-600 w-52">Enable Term Based Activities:</label><Toggle on={!!settings?.term_based_activities} disabled={!canWrite} onChange={(v) => updateSettings.mutate({ term_based_activities: v })} /></div>
      </div>

      {/* Club list */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-black uppercase tracking-widest text-slate-400">List of Clubs</h3>
        {canWrite && <button onClick={() => { setShowNew(true); setForm({ name: "", max_members: "" }); }} className="btn-primary gap-2"><Plus size={15} /> Create New Club</button>}
      </div>
      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["#", "Club Name", "Club Capacity", "Actions"].map((h) => <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 4 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-16" /></td>)}</tr>)
            : isError ? <tr><td colSpan={4} className="py-14 text-center"><AlertTriangle size={26} className="mx-auto mb-2 text-amber-400" /><button onClick={() => refetch()} className="btn-secondary mt-2">Retry</button></td></tr>
            : clubs.length > 0 ? clubs.map((c, i) => (
              <tr key={c.id} className="hover:bg-slate-50/70">
                <td className="px-5 py-3 text-sm text-slate-500">{i + 1}</td>
                <td className="px-5 py-3 text-sm font-semibold text-slate-800">{c.name}</td>
                <td className="px-5 py-3 text-sm text-slate-600">{c.max_members ?? "—"}</td>
                <td className="px-5 py-3">
                  {canWrite && (
                    <div className="flex items-center gap-1">
                      <button onClick={() => openEdit(c)} title="Edit" className="p-1.5 rounded text-amber-600 hover:bg-amber-50"><Edit2 size={15} /></button>
                      <button onClick={() => { if (confirm(`Delete ${c.name}?`)) del.mutate(c.id); }} title="Delete" className="p-1.5 rounded text-rose-500 hover:bg-rose-50"><Trash2 size={15} /></button>
                    </div>
                  )}
                </td>
              </tr>
            )) : <tr><td colSpan={4} className="py-16 text-center text-slate-400"><Users2 size={32} className="mx-auto mb-2 opacity-40" /><p className="font-semibold">No clubs yet</p></td></tr>}
          </tbody>
        </table>
      </div>

      {(showNew || editing) && (
        <Modal title={editing ? `Edit ${editing.name}` : "Create New Club"} onClose={() => { setShowNew(false); setEditing(null); }}>
          <div className="px-6 py-4 space-y-4">
            <div><label className="label">Club Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input" /></div>
            <div><label className="label">Club Capacity</label><input type="number" value={form.max_members} onChange={(e) => setForm({ ...form, max_members: e.target.value })} className="input" placeholder="e.g. 50" /></div>
          </div>
          <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={() => { setShowNew(false); setEditing(null); }} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!form.name.trim() || create.isPending || update.isPending} className="btn-primary gap-2">{(create.isPending || update.isPending) && <Loader2 size={15} className="animate-spin" />}{editing ? "Save" : "Create"}</button></div>
        </Modal>
      )}
    </div>
  );
}

// ── Club Grade ────────────────────────────────────────────────────────────────
function GradeTab({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading } = useClubGrades();
  const create = useCreateClubGrade();
  const del = useDeleteClubGrade();
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ grade_letter: "", grade_point: "", remarks: "" });
  const grades: ClubGrade[] = data?.items ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-3"><h3 className="text-sm font-black uppercase tracking-widest text-slate-400">List of Grade</h3>{canWrite && <button onClick={() => { setShow(true); setForm({ grade_letter: "", grade_point: "", remarks: "" }); }} className="btn-primary gap-2"><Plus size={15} /> Create New Grade</button>}</div>
      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["#", "Grade Letter", "Grade Point", "Remarks", "Actions"].map((h) => <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? <tr><td colSpan={5} className="px-5 py-10 text-center text-slate-400"><Loader2 className="animate-spin mx-auto" /></td></tr>
            : grades.length > 0 ? grades.map((g, i) => (
              <tr key={g.id} className="hover:bg-slate-50/70">
                <td className="px-5 py-3 text-sm text-slate-500">{i + 1}</td>
                <td className="px-5 py-3 text-sm font-semibold text-slate-800">{g.grade_letter}</td>
                <td className="px-5 py-3 text-sm text-slate-600">{g.grade_point ?? "—"}</td>
                <td className="px-5 py-3 text-sm text-slate-600">{g.remarks ?? "—"}</td>
                <td className="px-5 py-3">{canWrite && <button onClick={() => { if (confirm("Delete grade?")) del.mutate(g.id); }} className="p-1.5 rounded text-rose-500 hover:bg-rose-50"><Trash2 size={15} /></button>}</td>
              </tr>
            )) : <tr><td colSpan={5} className="py-14 text-center text-slate-400 font-semibold">No data available in table</td></tr>}
          </tbody>
        </table>
      </div>
      {show && (
        <Modal title="Create New Grade" onClose={() => setShow(false)}>
          <div className="px-6 py-4 space-y-4">
            <div><label className="label">Grade Letter *</label><input value={form.grade_letter} onChange={(e) => setForm({ ...form, grade_letter: e.target.value })} className="input" placeholder="e.g. A" /></div>
            <div><label className="label">Grade Point</label><input type="number" value={form.grade_point} onChange={(e) => setForm({ ...form, grade_point: e.target.value })} className="input" placeholder="e.g. 5" /></div>
            <div><label className="label">Remarks</label><input value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} className="input" placeholder="e.g. Excellent" /></div>
          </div>
          <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={() => setShow(false)} className="btn-secondary">Cancel</button><button onClick={() => create.mutate({ grade_letter: form.grade_letter.trim(), grade_point: form.grade_point ? Number(form.grade_point) : null, remarks: form.remarks || null }, { onSuccess: () => setShow(false) })} disabled={!form.grade_letter.trim() || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create</button></div>
        </Modal>
      )}
    </div>
  );
}

// ── Club Coordinator ──────────────────────────────────────────────────────────
function CoordinatorTab({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading } = useClubCoordinators();
  const { data: clubsData } = useClubs();
  const create = useCreateClubCoordinator();
  const del = useDeleteClubCoordinator();
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ coordinator_id: "", club_id: "" });
  const coordinators: ClubCoordinator[] = data?.items ?? [];
  const clubs: Club[] = clubsData?.items ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-3"><h3 className="text-sm font-black uppercase tracking-widest text-slate-400">List of Coordinators</h3>{canWrite && <button onClick={() => { setShow(true); setForm({ coordinator_id: "", club_id: "" }); }} className="btn-primary gap-2"><Plus size={15} /> Create New Club Coordinator</button>}</div>
      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["#", "Coordinator name", "Club Name", "Actions"].map((h) => <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? <tr><td colSpan={4} className="px-5 py-10 text-center text-slate-400"><Loader2 className="animate-spin mx-auto" /></td></tr>
            : coordinators.length > 0 ? coordinators.map((c, i) => (
              <tr key={c.id} className="hover:bg-slate-50/70">
                <td className="px-5 py-3 text-sm text-slate-500">{i + 1}</td>
                <td className="px-5 py-3 text-sm font-semibold text-slate-800">{c.coordinator_name || c.coordinator_id.slice(0, 8)}</td>
                <td className="px-5 py-3 text-sm text-slate-600">{c.club_name || "—"}</td>
                <td className="px-5 py-3">{canWrite && <button onClick={() => { if (confirm("Remove coordinator?")) del.mutate(c.id); }} className="p-1.5 rounded text-rose-500 hover:bg-rose-50"><Trash2 size={15} /></button>}</td>
              </tr>
            )) : <tr><td colSpan={4} className="py-14 text-center text-slate-400 font-semibold">No data available in table</td></tr>}
          </tbody>
        </table>
      </div>
      {show && (
        <Modal title="Create New Club Coordinator" onClose={() => setShow(false)}>
          <div className="px-6 py-4 space-y-4">
            <div><label className="label">Coordinator (staff) *</label><EntityPicker type="staff" value={form.coordinator_id || null} onChange={(id) => setForm({ ...form, coordinator_id: id || "" })} /></div>
            <div><label className="label">Club *</label><select value={form.club_id} onChange={(e) => setForm({ ...form, club_id: e.target.value })} className="input"><option value="">Select a club…</option>{clubs.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
          </div>
          <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={() => setShow(false)} className="btn-secondary">Cancel</button><button onClick={() => create.mutate({ coordinator_id: form.coordinator_id, club_id: form.club_id }, { onSuccess: () => setShow(false) })} disabled={!form.coordinator_id || !form.club_id || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Assign</button></div>
        </Modal>
      )}
    </div>
  );
}

// ── Enrollment Deadline ───────────────────────────────────────────────────────
function DeadlineTab({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading } = useClubDeadlines();
  const create = useCreateClubDeadline();
  const del = useDeleteClubDeadline();
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ term: "", deadline: "", academic_year: "" });
  const deadlines: ClubDeadline[] = data?.items ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-3"><h3 className="text-sm font-black uppercase tracking-widest text-slate-400">List of Enrollment Deadline</h3>{canWrite && <button onClick={() => { setShow(true); setForm({ term: "", deadline: "", academic_year: "" }); }} className="btn-primary gap-2"><Plus size={15} /> Create New Deadline</button>}</div>
      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["#", "Term", "Deadline", "Actions"].map((h) => <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? <tr><td colSpan={4} className="px-5 py-10 text-center text-slate-400"><Loader2 className="animate-spin mx-auto" /></td></tr>
            : deadlines.length > 0 ? deadlines.map((d, i) => (
              <tr key={d.id} className="hover:bg-slate-50/70">
                <td className="px-5 py-3 text-sm text-slate-500">{i + 1}</td>
                <td className="px-5 py-3 text-sm font-semibold text-slate-800">{d.term}{d.academic_year ? ` · ${d.academic_year}` : ""}</td>
                <td className="px-5 py-3 text-sm text-slate-600">{new Date(d.deadline).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}</td>
                <td className="px-5 py-3">{canWrite && <button onClick={() => { if (confirm("Delete deadline?")) del.mutate(d.id); }} className="p-1.5 rounded text-rose-500 hover:bg-rose-50"><Trash2 size={15} /></button>}</td>
              </tr>
            )) : <tr><td colSpan={4} className="py-14 text-center text-slate-400 font-semibold">No data available in table</td></tr>}
          </tbody>
        </table>
      </div>
      {show && (
        <Modal title="Create New Deadline" onClose={() => setShow(false)}>
          <div className="px-6 py-4 space-y-4">
            <div><label className="label">Term *</label><input value={form.term} onChange={(e) => setForm({ ...form, term: e.target.value })} className="input" placeholder="e.g. SPRING / Term 2" /></div>
            <div><label className="label">Academic Year</label><input value={form.academic_year} onChange={(e) => setForm({ ...form, academic_year: e.target.value })} className="input" placeholder="e.g. 2025/2026" /></div>
            <div><label className="label">Deadline *</label><input type="date" value={form.deadline} onChange={(e) => setForm({ ...form, deadline: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={() => setShow(false)} className="btn-secondary">Cancel</button><button onClick={() => create.mutate({ term: form.term.trim(), deadline: form.deadline, academic_year: form.academic_year || null }, { onSuccess: () => setShow(false) })} disabled={!form.term.trim() || !form.deadline || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Create</button></div>
        </Modal>
      )}
    </div>
  );
}
