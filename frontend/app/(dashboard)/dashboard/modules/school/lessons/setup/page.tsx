"use client";

import { useState } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import {
  useLessonCategories, useCreateLessonCategory, useUpdateLessonCategory, useDeleteLessonCategory,
  useLessonPlannerSettings, useSaveLessonPlannerSettings,
  useLessonSupervisors, useAddLessonSupervisor, useRemoveLessonSupervisor,
  useCloneLessons, useTeachers,
  type LessonCategory, type LessonSupervisor,
} from "@/hooks/useSchool";
import { useWeeks, useGenerateWeeks, useDeleteWeek, useSections } from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import {
  Settings2, Loader2, Plus, Trash2, Save, Pencil, X, Tag, CalendarRange,
  SlidersHorizontal, UserCog, Copy, Check,
} from "lucide-react";
import type { AcademicWeek, SchoolSection } from "@/types";

type Tab = "categories" | "weeks" | "settings" | "supervisors" | "clone";
const TABS: { key: Tab; label: string; icon: any }[] = [
  { key: "categories", label: "Lesson Plan Categories", icon: Tag },
  { key: "weeks", label: "Create Week Entries", icon: CalendarRange },
  { key: "settings", label: "Lesson Planner Settings", icon: SlidersHorizontal },
  { key: "supervisors", label: "Lesson Plan Supervisor", icon: UserCog },
  { key: "clone", label: "Clone Lesson Plans", icon: Copy },
];

export default function LessonPlannerSetupPage() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const canWrite = useHasPermission("school:lessons:write");
  const tab = (params.get("tab") as Tab) || "categories";
  const setTab = (t: Tab) => router.replace(`${pathname}?tab=${t}`, { scroll: false });

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <span>Education</span><span>/</span><span>Lesson Planner</span><span>/</span>
          <span className="text-brand-600 font-semibold">Lesson Planner Setup</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">
          <Settings2 size={22} className="text-brand-600" /> Lesson Planner Setup
        </h1>
        <p className="text-slate-500 text-sm mt-0.5">Configure the taxonomy, term weeks, workflow, supervisors and cloning for lesson plans.</p>
      </div>

      {/* Tab bar */}
      <div className="flex flex-wrap gap-1 border-b border-slate-200 mb-6">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={cn("flex items-center gap-1.5 px-3 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors",
              tab === t.key ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-800")}>
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      {tab === "categories" && <CategoriesTab canWrite={canWrite} />}
      {tab === "weeks" && <WeekEntriesTab canWrite={canWrite} />}
      {tab === "settings" && <SettingsTab canWrite={canWrite} />}
      {tab === "supervisors" && <SupervisorsTab canWrite={canWrite} />}
      {tab === "clone" && <CloneTab canWrite={canWrite} />}
    </div>
  );
}

// ── Categories ────────────────────────────────────────────────────────────────

function CategoriesTab({ canWrite }: { canWrite: boolean }) {
  const { data: categories = [], isLoading } = useLessonCategories();
  const create = useCreateLessonCategory();
  const update = useUpdateLessonCategory();
  const del = useDeleteLessonCategory();
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<{ id: string; name: string } | null>(null);

  const add = () => { if (name.trim()) create.mutate({ name: name.trim() }, { onSuccess: () => setName("") }); };
  const saveEdit = () => { if (editing?.name.trim()) update.mutate({ id: editing.id, name: editing.name.trim() }, { onSuccess: () => setEditing(null) }); };

  return (
    <div className="max-w-xl">
      <p className="text-sm text-slate-500 mb-4">Labels for organising lesson plans (e.g. Theory, Practical, Revision). Optional on a plan.</p>
      {canWrite && (
        <div className="flex gap-2 mb-4">
          <input value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()} placeholder="New category name" className="input" />
          <button onClick={add} disabled={create.isPending || !name.trim()} className="btn-primary gap-1.5 shrink-0"><Plus size={15} /> Add Category</button>
        </div>
      )}
      <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
        {isLoading ? <div className="p-6 text-center"><Loader2 className="animate-spin mx-auto text-slate-400" size={18} /></div>
          : categories.length === 0 ? <div className="p-6 text-center text-sm text-slate-400">No categories yet.</div>
          : categories.map((c: LessonCategory) => (
            <div key={c.id} className="flex items-center gap-2 px-4 py-3">
              {editing?.id === c.id ? (
                <>
                  <input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} onKeyDown={(e) => e.key === "Enter" && saveEdit()} className="input flex-1" autoFocus />
                  <button onClick={saveEdit} disabled={update.isPending} className="btn-primary text-xs py-1 gap-1"><Save size={12} /> Save</button>
                  <button onClick={() => setEditing(null)} className="btn-secondary text-xs py-1"><X size={12} /></button>
                </>
              ) : (
                <>
                  <span className="flex-1 text-sm font-medium text-slate-800">{c.name}</span>
                  {canWrite && <>
                    <button onClick={() => setEditing({ id: c.id, name: c.name })} className="text-slate-400 hover:text-brand-600 p-1"><Pencil size={14} /></button>
                    <button onClick={() => del.mutate(c.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>
                  </>}
                </>
              )}
            </div>
          ))}
      </div>
    </div>
  );
}

// ── Week Entries (reuses the academic-weeks calendar backbone) ────────────────

function WeekEntriesTab({ canWrite }: { canWrite: boolean }) {
  const [form, setForm] = useState({ academic_year: "", term: "", start_date: "", end_date: "" });
  const generate = useGenerateWeeks();
  const del = useDeleteWeek();
  const { data: weeks = [] } = useWeeks(
    form.academic_year || form.term ? { academic_year: form.academic_year || undefined, term: form.term || undefined } : undefined,
  );

  const canGen = form.academic_year && form.term && form.start_date && form.end_date;
  const gen = () => generate.mutate({ ...form });

  return (
    <div>
      <p className="text-sm text-slate-500 mb-4">Define a term&apos;s teaching weeks. These are the shared academic weeks used across the calendar &mdash; generate them once per term.</p>
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-5">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div><label className="label">Academic year</label><input value={form.academic_year} onChange={(e) => setForm({ ...form, academic_year: e.target.value })} placeholder="2025/2026" className="input" /></div>
            <div><label className="label">Term</label><input value={form.term} onChange={(e) => setForm({ ...form, term: e.target.value })} placeholder="Spring" className="input" /></div>
            <div><label className="label">Start date</label><input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} className="input" /></div>
            <div><label className="label">End date</label><input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end mt-3">
            <button onClick={gen} disabled={!canGen || generate.isPending} className="btn-primary gap-2">{generate.isPending ? <Loader2 size={15} className="animate-spin" /> : <CalendarRange size={15} />} Generate weeks</button>
          </div>
        </div>
      )}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">
            {["#", "Term", "Start", "End", "Label", ""].map((h) => <th key={h} className="px-4 py-2.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}
          </tr></thead>
          <tbody className="divide-y divide-slate-50">
            {weeks.length === 0 ? <tr><td colSpan={6} className="px-4 py-8 text-center text-sm text-slate-400">No weeks yet &mdash; enter a year + term above, then generate.</td></tr>
              : weeks.map((w: AcademicWeek) => (
                <tr key={w.id}>
                  <td className="px-4 py-2.5 text-sm font-bold text-slate-700 tabular-nums">{w.week_number}</td>
                  <td className="px-4 py-2.5 text-sm text-slate-600">{w.term}</td>
                  <td className="px-4 py-2.5 text-sm text-slate-600 tabular-nums">{w.start_date}</td>
                  <td className="px-4 py-2.5 text-sm text-slate-600 tabular-nums">{w.end_date}</td>
                  <td className="px-4 py-2.5 text-sm text-slate-500">{w.is_holiday ? "Holiday" : (w.label || "—")}</td>
                  <td className="px-4 py-2.5 text-right">{canWrite && !w.is_locked && <button onClick={() => del.mutate(w.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={13} /></button>}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Settings ──────────────────────────────────────────────────────────────────

function SettingsTab({ canWrite }: { canWrite: boolean }) {
  const { data: settings, isLoading } = useLessonPlannerSettings();
  const save = useSaveLessonPlannerSettings();
  const [form, setForm] = useState<{ require_approval: boolean; default_duration_minutes: number; allow_backdated: boolean } | null>(null);
  const current = form ?? settings ?? null;

  if (isLoading || !current) return <div className="py-12 text-center"><Loader2 className="animate-spin mx-auto text-slate-400" /></div>;
  const patch = (p: Partial<typeof current>) => setForm({ ...current, ...p });

  return (
    <div className="max-w-xl space-y-4">
      <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
        <label className="flex items-center justify-between px-4 py-3.5 cursor-pointer">
          <div><p className="text-sm font-semibold text-slate-800">Require approval</p><p className="text-xs text-slate-500">Plans need a supervisor to approve (publish) rather than teacher self-publish.</p></div>
          <input type="checkbox" checked={current.require_approval} disabled={!canWrite} onChange={(e) => patch({ require_approval: e.target.checked })} className="h-4 w-4 rounded border-slate-300" />
        </label>
        <label className="flex items-center justify-between px-4 py-3.5 cursor-pointer">
          <div><p className="text-sm font-semibold text-slate-800">Allow backdated plans</p><p className="text-xs text-slate-500">Let teachers plan for dates in the past.</p></div>
          <input type="checkbox" checked={current.allow_backdated} disabled={!canWrite} onChange={(e) => patch({ allow_backdated: e.target.checked })} className="h-4 w-4 rounded border-slate-300" />
        </label>
        <div className="flex items-center justify-between px-4 py-3.5">
          <div><p className="text-sm font-semibold text-slate-800">Default lesson duration</p><p className="text-xs text-slate-500">Prefilled minutes on a new plan.</p></div>
          <input type="number" min={5} max={240} step={5} value={current.default_duration_minutes} disabled={!canWrite} onChange={(e) => patch({ default_duration_minutes: Number(e.target.value) || 45 })} className="input w-24" />
        </div>
      </div>
      {canWrite && (
        <div className="flex justify-end">
          <button onClick={() => save.mutate(current, { onSuccess: () => setForm(null) })} disabled={save.isPending || !form} className="btn-primary gap-2">{save.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Save settings</button>
        </div>
      )}
    </div>
  );
}

// ── Supervisors ───────────────────────────────────────────────────────────────

function SupervisorsTab({ canWrite }: { canWrite: boolean }) {
  const { data: supervisors = [], isLoading } = useLessonSupervisors();
  const { data: teachersResp } = useTeachers({ page_size: 100 });
  const { data: sections = [] } = useSections();
  const add = useAddLessonSupervisor();
  const del = useRemoveLessonSupervisor();
  const [supervisorId, setSupervisorId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const teachers = teachersResp?.items ?? [];

  const submit = () => { if (supervisorId) add.mutate({ supervisor_id: supervisorId, section_id: sectionId || null }, { onSuccess: () => { setSupervisorId(""); setSectionId(""); } }); };

  return (
    <div className="max-w-2xl">
      <p className="text-sm text-slate-500 mb-4">Assign staff who review and approve lesson plans. Leave the level blank for an org-wide supervisor.</p>
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-5 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[180px]"><label className="label">Supervisor</label>
            <select value={supervisorId} onChange={(e) => setSupervisorId(e.target.value)} className="input">
              <option value="">Select staff…</option>
              {teachers.map((t: any) => <option key={t.id} value={t.id}>{[t.first_name, t.last_name].filter(Boolean).join(" ") || t.email}</option>)}
            </select>
          </div>
          <div className="flex-1 min-w-[160px]"><label className="label">Level (optional)</label>
            <select value={sectionId} onChange={(e) => setSectionId(e.target.value)} className="input">
              <option value="">All levels</option>
              {sections.map((s: SchoolSection) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <button onClick={submit} disabled={add.isPending || !supervisorId} className="btn-primary gap-1.5"><Plus size={15} /> Assign</button>
        </div>
      )}
      <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
        {isLoading ? <div className="p-6 text-center"><Loader2 className="animate-spin mx-auto text-slate-400" size={18} /></div>
          : supervisors.length === 0 ? <div className="p-6 text-center text-sm text-slate-400">No supervisors assigned.</div>
          : supervisors.map((s: LessonSupervisor) => (
            <div key={s.id} className="flex items-center gap-2 px-4 py-3">
              <UserCog size={15} className="text-slate-400" />
              <span className="flex-1 text-sm font-medium text-slate-800">{s.supervisor_name || s.supervisor_id}</span>
              <span className="badge bg-slate-50 text-slate-600 border-slate-200 text-xs">{s.section_name || "All levels"}</span>
              {canWrite && <button onClick={() => del.mutate(s.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}
            </div>
          ))}
      </div>
    </div>
  );
}

// ── Clone ─────────────────────────────────────────────────────────────────────

function CloneTab({ canWrite }: { canWrite: boolean }) {
  const clone = useCloneLessons();
  const [form, setForm] = useState({ source_start: "", source_end: "", target_start: "", only_mine: false });
  const [result, setResult] = useState<{ cloned: number; skipped: number } | null>(null);
  const ready = form.source_start && form.source_end && form.target_start;

  const run = () => clone.mutate(
    { source_start: form.source_start, source_end: form.source_end, target_start: form.target_start, only_mine: form.only_mine },
    { onSuccess: (res: any) => setResult(res) },
  );

  return (
    <div className="max-w-xl">
      <p className="text-sm text-slate-500 mb-4">Copy plans from one date range to another as new drafts, keeping each plan&apos;s day-offset. A plan already at the target (same class + subject + date + period) is skipped.</p>
      {!canWrite ? <p className="text-sm text-slate-400">You don&apos;t have permission to clone lesson plans.</p> : (
        <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">Copy from (start)</label><input type="date" value={form.source_start} onChange={(e) => setForm({ ...form, source_start: e.target.value })} className="input" /></div>
            <div><label className="label">Copy from (end)</label><input type="date" value={form.source_end} onChange={(e) => setForm({ ...form, source_end: e.target.value })} className="input" /></div>
          </div>
          <div><label className="label">Paste at (target start)</label><input type="date" value={form.target_start} onChange={(e) => setForm({ ...form, target_start: e.target.value })} className="input" /></div>
          <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
            <input type="checkbox" checked={form.only_mine} onChange={(e) => setForm({ ...form, only_mine: e.target.checked })} className="h-4 w-4 rounded border-slate-300" />
            Only my own plans
          </label>
          <div className="flex items-center justify-between">
            {result ? <p className="text-sm text-emerald-700 flex items-center gap-1.5"><Check size={14} /> Cloned {result.cloned}, skipped {result.skipped}.</p> : <span />}
            <button onClick={run} disabled={!ready || clone.isPending} className="btn-primary gap-2">{clone.isPending ? <Loader2 size={15} className="animate-spin" /> : <Copy size={15} />} Clone plans</button>
          </div>
        </div>
      )}
    </div>
  );
}
