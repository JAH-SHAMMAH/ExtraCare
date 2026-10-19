"use client";

import { useState } from "react";
import {
  useDisciplinaryCases, useCreateDisciplinaryCase, useUpdateDisciplinaryCase, useDeleteDisciplinaryCase,
  useDisciplinaryActions, useCommittees, useSanctionGroups,
} from "@/hooks/usePastoral";
import { useSessions, useSections } from "@/hooks/usePlatform";
import { useClasses, useYearGroups } from "@/hooks/useSchool";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn } from "@/lib/utils";
import { Loader2, Gavel, Trash2, Plus, X, Download, Search } from "lucide-react";

const STATUSES = ["pending", "resolved", "dismissed"];
const STATUS_STYLE: Record<string, string> = {
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  resolved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  dismissed: "bg-slate-50 text-slate-500 border-slate-200",
};

export default function BehaviourSanctionPage() {
  const canWrite = useHasPermission("school:behaviour:write");
  const [statusFilter, setStatusFilter] = useState("");
  // Educare-style filter bar: Session / School / Year Group / Class + Filter button.
  const [draft, setDraft] = useState({ session: "", section: "", yearGroup: "", classId: "" });
  const [applied, setApplied] = useState(draft);
  const [search, setSearch] = useState("");
  const [perPage, setPerPage] = useState(25);
  const { data: sessions = [] } = useSessions();
  const { data: sections = [] } = useSections();
  const { data: yearGroups = [] } = useYearGroups();
  const { data: classData } = useClasses({ page_size: 200 } as any);
  const classList: any[] = (classData as any)?.items || [];
  const { data: rawCases = [], isLoading } = useDisciplinaryCases({
    ...(statusFilter ? { status: statusFilter } : {}),
    ...(applied.classId ? { class_id: applied.classId } : {}),
    ...(applied.section ? { section_id: applied.section } : {}),
  });
  const sess: any = (sessions as any[]).find((x) => x.id === applied.session);
  const cases = (rawCases as any[]).filter((c) => {
    if (sess?.start_date && c.case_date && c.case_date < sess.start_date) return false;
    if (sess?.end_date && c.case_date && c.case_date > sess.end_date) return false;
    if (applied.yearGroup) {
      const yg = ((yearGroups as any[]).find((y) => y.id === applied.yearGroup)?.name || "").toLowerCase();
      if (yg && !(c.class_name || "").toLowerCase().startsWith(yg)) return false;
    }
    const q = search.trim().toLowerCase();
    return !q || [c.student_name, c.offence, c.sanction, c.class_name, c.action_name].some((v: any) => (v || "").toLowerCase().includes(q));
  }).slice(0, perPage);
  const exportCsv = () => {
    const rows = [["Student", "Class", "Date", "Action", "Committee", "Offence", "Sanction", "Status"],
      ...cases.map((c: any) => [c.student_name, c.class_name, c.case_date, c.action_name, c.committee_name, c.offence, c.sanction, c.status])];
    const csv = rows.map((r) => r.map((v: any) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" }));
    const a = document.createElement("a"); a.href = url; a.download = "disciplinary-cases.csv"; a.click(); URL.revokeObjectURL(url);
  };
  const { data: actions = [] } = useDisciplinaryActions();
  const { data: committees = [] } = useCommittees();
  const { data: groups = [] } = useSanctionGroups();
  const create = useCreateDisciplinaryCase();
  const update = useUpdateDisciplinaryCase();
  const del = useDeleteDisciplinaryCase();

  const [show, setShow] = useState(false);
  const empty = { student_id: "", committee_id: "", action_id: "", sanction_group_id: "", offence: "", sanction: "", status: "pending", case_date: "" };
  const [f, setF] = useState(empty);

  const submit = () => {
    if (!f.student_id) return;
    create.mutate(
      {
        student_id: f.student_id, committee_id: f.committee_id || null, action_id: f.action_id || null,
        sanction_group_id: f.sanction_group_id || null, offence: f.offence || null, sanction: f.sanction || null,
        status: f.status, case_date: f.case_date || null,
      },
      { onSuccess: () => { setF(empty); setShow(false); } },
    );
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Pastoral</span><span>/</span><span className="text-brand-600 font-semibold">Pastoral Discipline</span></nav>
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2"><Gavel size={22} className="text-brand-600" /> Pastoral Discipline</h1>
          <p className="text-slate-500 text-sm">Disciplinary cases: the offence, the sanction applied, the handling committee, and status.</p>
        </div>
        {canWrite && <button onClick={() => setShow((s) => !s)} className="btn-primary gap-2 shrink-0"><Plus size={15} /> Register New Case</button>}
      </div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New Disciplinary Case</h2><button onClick={() => { setShow(false); setF(empty); }} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div><label className="label">Student *</label><EntityPicker type="student" value={f.student_id || null} onChange={(id) => setF({ ...f, student_id: id || "" })} /></div>
            <div><label className="label">Date</label><input type="date" value={f.case_date} onChange={(e) => setF({ ...f, case_date: e.target.value })} className="input" /></div>
            <div><label className="label">Action</label><select value={f.action_id} onChange={(e) => setF({ ...f, action_id: e.target.value })} className="input"><option value="">—</option>{(actions as any[]).filter((a) => a.is_active).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></div>
            <div><label className="label">Committee</label><select value={f.committee_id} onChange={(e) => setF({ ...f, committee_id: e.target.value })} className="input"><option value="">—</option>{(committees as any[]).filter((c) => c.is_active).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
            <div><label className="label">Sanction Group</label><select value={f.sanction_group_id} onChange={(e) => setF({ ...f, sanction_group_id: e.target.value })} className="input"><option value="">—</option>{(groups as any[]).filter((g) => g.is_active).map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</select></div>
            <div><label className="label">Status</label><select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })} className="input capitalize">{STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}</select></div>
            <div className="md:col-span-2"><label className="label">Offence</label><textarea value={f.offence} onChange={(e) => setF({ ...f, offence: e.target.value })} className="input" rows={2} /></div>
            <div className="md:col-span-2"><label className="label">Sanction / notes</label><textarea value={f.sanction} onChange={(e) => setF({ ...f, sanction: e.target.value })} className="input" rows={2} /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={() => { setShow(false); setF(empty); }} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!f.student_id || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />} Record Case</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4 flex flex-wrap items-end gap-3">
        <div><label className="label">Session</label><select aria-label="Session" value={draft.session} onChange={(e) => setDraft({ ...draft, session: e.target.value })} className="input w-auto"><option value="">All</option>{(sessions as any[]).map((x) => <option key={x.id} value={x.id}>{x.name}{x.term ? ` · ${x.term}` : ""}</option>)}</select></div>
        <div><label className="label">School</label><select aria-label="School" value={draft.section} onChange={(e) => setDraft({ ...draft, section: e.target.value })} className="input w-auto"><option value="">All</option>{(sections as any[]).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></div>
        <div><label className="label">Year Group</label><select aria-label="Year Group" value={draft.yearGroup} onChange={(e) => setDraft({ ...draft, yearGroup: e.target.value })} className="input w-auto"><option value="">All</option>{(yearGroups as any[]).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></div>
        <div><label className="label">Class</label><select aria-label="Class" value={draft.classId} onChange={(e) => setDraft({ ...draft, classId: e.target.value })} className="input w-auto"><option value="">All</option>{classList.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></div>
        <div><label className="label">Status</label><select aria-label="Status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input w-auto capitalize"><option value="">All</option>{STATUSES.map((x) => <option key={x} value={x}>{x}</option>)}</select></div>
        <button onClick={() => setApplied(draft)} className="btn-primary">Filter</button>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <h2 className="text-sm font-bold text-slate-800">Disciplinary Cases</h2>
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={exportCsv} disabled={!cases.length} className="btn-secondary gap-2"><Download size={14} /> Export</button>
          <select aria-label="Records per page" value={perPage} onChange={(e) => setPerPage(Number(e.target.value))} className="input w-auto">{[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n} records</option>)}</select>
          <div className="relative"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search" className="input pl-9 w-44" /></div>
        </div>
      </div>

      {isLoading ? (
        <div className="py-16 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
      ) : cases.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center text-slate-400"><Gavel size={30} className="mx-auto mb-3 opacity-40" /><p className="text-sm">No disciplinary cases.</p></div>
      ) : (
        <div className="space-y-3">
          {cases.map((c: any) => (
            <div key={c.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="text-sm font-bold text-slate-900">{c.student_name}</h3>
                  <p className="text-xs text-slate-400 mt-0.5">{[c.class_name, c.action_name, c.committee_name, c.case_date].filter(Boolean).join(" · ") || "—"}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {canWrite ? (
                    <select value={c.status} onChange={(e) => update.mutate({ id: c.id, data: { status: e.target.value } })} className={cn("text-xs font-semibold rounded-full border px-2.5 py-1 capitalize cursor-pointer", STATUS_STYLE[c.status] || STATUS_STYLE.dismissed)}>
                      {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  ) : <span className={cn("badge capitalize", STATUS_STYLE[c.status])}>{c.status}</span>}
                  {canWrite && <button onClick={() => { if (confirm("Delete this case?")) del.mutate(c.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>}
                </div>
              </div>
              {c.offence && <p className="text-sm text-slate-600 mt-3"><span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Offence </span>{c.offence}</p>}
              {c.sanction && <p className="text-sm text-slate-600 mt-1.5"><span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Sanction </span>{c.sanction}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
