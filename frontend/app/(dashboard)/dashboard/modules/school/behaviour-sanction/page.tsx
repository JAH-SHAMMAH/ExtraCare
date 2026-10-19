"use client";

import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  useDisciplinaryCases, useUpdateDisciplinaryCase, useDeleteDisciplinaryCase,
  useDisciplinaryActions, useCommittees,
} from "@/hooks/usePastoral";
import { useSessions, useSections, useCurrentSession } from "@/hooks/usePlatform";
import { useClasses, useYearGroups, useStudents } from "@/hooks/useSchool";
import { pastoralApi } from "@/lib/api";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Loader2, Gavel, Trash2, Plus, X, Download, Search, Users2, Pencil, ChevronUp, ChevronDown } from "lucide-react";

const STATUSES = ["pending", "resolved", "dismissed"];
const STATUS_STYLE: Record<string, string> = {
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  resolved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  dismissed: "bg-slate-50 text-slate-500 border-slate-200",
};
type SortKey = "n" | "student" | "by" | "action" | "dstatus" | "recv" | "status" | "date";
const fmtDate = (d?: string | null) => (d ? new Date(d).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) : "—");

export default function PastoralDisciplinePage() {
  const canWrite = useHasPermission("school:behaviour:write");
  const qc = useQueryClient();

  // ── Filter bar: Session / School / Year Group / Class + Filter ──
  const { data: cur } = useCurrentSession();
  const { data: sessions = [] } = useSessions();
  const { data: sections = [] } = useSections();
  const { data: yearGroups = [] } = useYearGroups();
  const { data: classData } = useClasses({ page_size: 300 } as any);
  const classList: any[] = (classData as any)?.items || [];
  const [draft, setDraft] = useState({ session: "", section: "", yearGroup: "", classId: "" });
  const [applied, setApplied] = useState(draft);
  const curId: string = (cur as any)?.session?.id || "";
  useEffect(() => { if (curId) { setDraft((d) => (d.session ? d : { ...d, session: curId })); setApplied((d) => (d.session ? d : { ...d, session: curId })); } }, [curId]);
  const ygName = (id: string) => ((yearGroups as any[]).find((y) => y.id === id)?.name || "").toLowerCase();
  const classChoices = classList.filter((c) => (!draft.section || c.section_id === draft.section) && (!draft.yearGroup || (c.name || "").toLowerCase().startsWith(ygName(draft.yearGroup))));

  const { data: raw = [], isLoading } = useDisciplinaryCases({
    ...(applied.classId ? { class_id: applied.classId } : {}),
    ...(applied.section ? { section_id: applied.section } : {}),
  });
  const update = useUpdateDisciplinaryCase();
  const del = useDeleteDisciplinaryCase();
  const { data: actions = [] } = useDisciplinaryActions();
  const { data: committees = [] } = useCommittees();

  // ── Table: search, sort, paginate ──
  const [search, setSearch] = useState("");
  const [perPage, setPerPage] = useState(10);
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "date", dir: -1 });
  const sess: any = (sessions as any[]).find((x) => x.id === applied.session);

  const rows = useMemo(() => {
    let r = (raw as any[]).map((c, i) => ({ ...c, _n: i + 1 }));
    r = r.filter((c) => {
      if (sess?.start_date && c.case_date && c.case_date < sess.start_date) return false;
      if (sess?.end_date && c.case_date && c.case_date > sess.end_date) return false;
      if (applied.yearGroup && !(c.class_name || "").toLowerCase().startsWith(ygName(applied.yearGroup))) return false;
      const q = search.trim().toLowerCase();
      return !q || [c.student_name, c.offence, c.sanction, c.class_name, c.action_name, c.committee_name, c.recorded_by_name, c.status].some((v: any) => (v || "").toLowerCase().includes(q));
    });
    const val = (c: any): string | number => ({
      n: c._n, student: c.student_name || "", by: c.recorded_by_name || "", action: c.action_name || "",
      dstatus: c.status || "", recv: c.committee_name || "", status: c.status === "pending" ? "open" : "closed", date: c.created_at || c.case_date || "",
    } as Record<SortKey, string | number>)[sort.key];
    return [...r].sort((a, b) => (val(a) > val(b) ? 1 : val(a) < val(b) ? -1 : 0) * sort.dir);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [raw, search, sort, applied, sess, yearGroups]);
  useEffect(() => setPage(1), [search, perPage, applied]);
  const pages = Math.max(1, Math.ceil(rows.length / perPage));
  const start = (page - 1) * perPage;
  const view = rows.slice(start, start + perPage);

  const exportCsv = () => {
    const out = [["#", "Student Full Name", "Class", "Reported By", "Disciplinary Action", "Disciplinary Status", "Received By", "Status", "Created Date", "Offence", "Sanction"],
      ...rows.map((c: any, i: number) => [i + 1, c.student_name, c.class_name, c.recorded_by_name, c.action_name, c.status, c.committee_name, c.status === "pending" ? "Open" : "Closed", fmtDate(c.created_at || c.case_date), c.offence, c.sanction])];
    const csv = out.map((r) => r.map((v: any) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" }));
    const a = document.createElement("a"); a.href = url; a.download = "disciplinary-cases.csv"; a.click(); URL.revokeObjectURL(url);
  };

  const [report, setReport] = useState(false);
  const [editing, setEditing] = useState<any | null>(null);

  const Th = ({ k, children }: { k: SortKey; children: React.ReactNode }) => (
    <th className="px-3 py-3 text-left text-xs font-bold text-slate-700 whitespace-nowrap cursor-pointer select-none" onClick={() => setSort((s) => ({ key: k, dir: s.key === k ? (s.dir === 1 ? -1 : 1) : 1 }))} aria-sort={sort.key === k ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
      <span className="inline-flex items-center gap-1">{children}
        <span className="inline-flex flex-col leading-none text-[8px] text-slate-300"><ChevronUp size={10} className={sort.key === k && sort.dir === 1 ? "text-brand-600" : ""} /><ChevronDown size={10} className={sort.key === k && sort.dir === -1 ? "text-brand-600" : ""} /></span>
      </span>
    </th>
  );

  return (
    <div className="p-4 sm:p-8 max-w-6xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-3"><span>Home</span><span>•</span><span>Pastoral</span><span>•</span><span className="text-brand-600 font-semibold">Pastoral Discipline</span></nav>

      <div className="bg-slate-50 rounded-xl border border-slate-200 p-4 mb-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 items-end">
          <div><label className="label">Session</label><select aria-label="Session" value={draft.session} onChange={(e) => setDraft({ ...draft, session: e.target.value })} className="input"><option value="">All</option>{(sessions as any[]).map((x) => <option key={x.id} value={x.id}>{x.name}{x.term ? ` · ${x.term}` : ""}</option>)}</select></div>
          <div><label className="label">School</label><select aria-label="School" value={draft.section} onChange={(e) => setDraft({ ...draft, section: e.target.value, classId: "" })} className="input"><option value="">All</option>{(sections as any[]).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></div>
          <div><label className="label">Year Group</label><select aria-label="Year Group" value={draft.yearGroup} onChange={(e) => setDraft({ ...draft, yearGroup: e.target.value, classId: "" })} className="input"><option value="">All</option>{(yearGroups as any[]).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></div>
          <div><label className="label">Class</label><select aria-label="Class" value={draft.classId} onChange={(e) => setDraft({ ...draft, classId: e.target.value })} className="input"><option value="">Select</option>{classChoices.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></div>
        </div>
        <div className="flex justify-end mt-3"><button onClick={() => setApplied(draft)} className="btn-primary bg-emerald-600 hover:bg-emerald-700">Filter</button></div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <h1 className="text-lg font-black text-slate-900 flex items-center gap-2"><Users2 size={20} className="text-slate-700" /> Disciplinary Cases</h1>
        <div className="flex gap-2">
          {canWrite && <button onClick={() => setReport(true)} className="btn-primary gap-2 bg-emerald-600 hover:bg-emerald-700"><Plus size={15} /> Register New Case</button>}
          <button onClick={exportCsv} disabled={!rows.length} className="btn-secondary gap-2 bg-sky-50 text-sky-700 border-sky-200"><Download size={14} /> Export</button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-3">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3 text-sm text-slate-600">
          <label className="flex items-center gap-2"><select aria-label="Records per page" value={perPage} onChange={(e) => setPerPage(Number(e.target.value))} className="input w-auto py-1">{[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n}</option>)}</select> records</label>
          <label className="flex items-center gap-2">Search: <input aria-label="Search cases" value={search} onChange={(e) => setSearch(e.target.value)} className="input w-44 py-1" /></label>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200">
              <tr>
                <Th k="n">#</Th><Th k="student">Student Full Name</Th><Th k="by">Reported By</Th><Th k="action">Disciplinary Action</Th>
                <Th k="dstatus">Disciplinary Status</Th><Th k="recv">Received By</Th><Th k="status">Status</Th><Th k="date">Created Date</Th>
                <th className="px-3 py-3 text-left text-xs font-bold text-slate-700">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading ? (
                <tr><td colSpan={9} className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></td></tr>
              ) : view.length === 0 ? (
                <tr><td colSpan={9} className="py-8 text-center text-slate-500 bg-slate-50">No data available in table</td></tr>
              ) : view.map((c: any) => (
                <tr key={c.id} className="hover:bg-slate-50">
                  <td className="px-3 py-2 text-slate-400">{c._n}</td>
                  <td className="px-3 py-2 font-medium text-slate-800">{c.student_name}{c.class_name && <span className="block text-[11px] font-normal text-slate-400">{c.class_name}</span>}</td>
                  <td className="px-3 py-2">{c.recorded_by_name || "—"}</td>
                  <td className="px-3 py-2">{c.action_name || "—"}</td>
                  <td className="px-3 py-2"><span className={cn("badge capitalize", STATUS_STYLE[c.status] || STATUS_STYLE.dismissed)}>{c.status}</span></td>
                  <td className="px-3 py-2">{c.committee_name || "—"}</td>
                  <td className="px-3 py-2">{c.status === "pending" ? "Open" : "Closed"}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{fmtDate(c.created_at || c.case_date)}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1">
                      <button aria-label="View or update case" title="View / update" onClick={() => setEditing(c)} className="p-1.5 rounded hover:bg-brand-50 text-slate-400 hover:text-brand-600"><Pencil size={14} /></button>
                      {canWrite && <button aria-label="Delete case" title="Delete" onClick={() => { if (confirm("Delete this case?")) del.mutate(c.id); }} className="p-1.5 rounded hover:bg-red-50 text-slate-400 hover:text-red-600"><Trash2 size={14} /></button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 mt-3 text-sm text-slate-600">
          <span>Showing {rows.length ? start + 1 : 0} to {Math.min(start + perPage, rows.length)} of {rows.length} entries</span>
          <div className="flex gap-1">
            {[["First", () => setPage(1), page === 1], ["Prev", () => setPage((p) => Math.max(1, p - 1)), page === 1], ["Next", () => setPage((p) => Math.min(pages, p + 1)), page >= pages], ["Last", () => setPage(pages), page >= pages]].map(([l, f, dis]) => (
              <button key={l as string} onClick={f as () => void} disabled={dis as boolean} className="px-3 py-1.5 rounded border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-50">{l as string}</button>
            ))}
          </div>
        </div>
      </div>

      {report && <ReportCaseModal onClose={() => setReport(false)} onDone={() => { qc.invalidateQueries({ queryKey: ["disciplinary-cases"] }); setReport(false); }} sections={sections as any[]} classList={classList} />}
      {editing && (
        <CaseDetailModal c={editing} canWrite={canWrite} actions={actions as any[]} committees={committees as any[]} onClose={() => setEditing(null)}
          onSave={(data: object) => update.mutate({ id: editing.id, data }, { onSuccess: () => setEditing(null) })} saving={update.isPending} />
      )}
    </div>
  );
}

// ── Report New Disciplinary Case: SELECT USERS (Level / Class / Gender / Filter) ──
function ReportCaseModal({ onClose, onDone, sections, classList }: { onClose: () => void; onDone: () => void; sections: any[]; classList: any[] }) {
  const [level, setLevel] = useState("");
  const [classId, setClassId] = useState("");
  const [gender, setGender] = useState("");
  const [applied, setApplied] = useState({ level: "", classId: "" });
  const [q, setQ] = useState("");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [statement, setStatement] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [busy, setBusy] = useState(false);
  const [appliedGender, setAppliedGender] = useState("");

  const enabled = !!(applied.level || applied.classId);
  const { data, isLoading } = useStudents({ page_size: 500, ...(applied.classId ? { class_id: applied.classId } : {}), ...(applied.level ? { section_id: applied.level } : {}) });
  const students: any[] = enabled ? ((data as any)?.items || []) : [];
  const list = students.filter((s) => (!appliedGender || s.gender === appliedGender) &&
    (!q.trim() || `${s.first_name} ${s.last_name} ${s.student_id}`.toLowerCase().includes(q.trim().toLowerCase())));
  const classes = classList.filter((c) => !level || c.section_id === level);
  const allSelected = list.length > 0 && list.every((s) => picked.has(s.id));
  const toggleAll = () => setPicked((p) => { const n = new Set(p); if (allSelected) list.forEach((s) => n.delete(s.id)); else list.forEach((s) => n.add(s.id)); return n; });

  const submit = async () => {
    setBusy(true);
    let ok = 0; let fail = 0;
    for (const id of picked) {
      try { await pastoralApi.disciplinaryCases.create({ student_id: id, offence: statement.trim(), case_date: date, status: "pending" }); ok++; }
      catch { fail++; }
    }
    setBusy(false);
    if (ok) toast.success(`${ok} case${ok === 1 ? "" : "s"} reported.`);
    if (fail) toast.error(`${fail} case${fail === 1 ? "" : "s"} failed.`);
    if (ok) onDone();
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 flex items-start justify-center p-3 overflow-y-auto" onClick={onClose} role="dialog" aria-label="Report New Disciplinary Case">
      <div className="bg-white rounded-xl w-full max-w-2xl my-4 shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="bg-emerald-950 text-white px-5 py-4 flex items-start justify-between"><h2 className="text-xl font-light">Report New Disciplinary Case</h2><button aria-label="Close" onClick={onClose} className="text-white/60 hover:text-white"><X size={20} /></button></div>
        <div className="p-5 space-y-4">
          <div className="border border-slate-800 rounded-lg overflow-hidden">
            <div className="bg-emerald-700 text-white px-4 py-2.5 font-bold text-sm flex items-center gap-2"><Users2 size={15} /> SELECT USERS</div>
            <div className="p-4 space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div><label className="label">Select Level:</label><select aria-label="Select Level" value={level} onChange={(e) => { setLevel(e.target.value); setClassId(""); }} className="input"><option value="">All</option>{sections.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
                <div><label className="label">Select Class:</label><select aria-label="Select Class" value={classId} onChange={(e) => setClassId(e.target.value)} className="input"><option value="">Select</option>{classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
                <div><label className="label">Select Gender:</label><select aria-label="Select Gender" value={gender} onChange={(e) => setGender(e.target.value)} className="input"><option value="">All</option><option value="male">Male</option><option value="female">Female</option></select></div>
              </div>
              <div className="flex justify-end"><button onClick={() => { setApplied({ level, classId }); setAppliedGender(gender); }} className="btn-primary bg-emerald-600 hover:bg-emerald-700">Filter</button></div>
              <input aria-label="Search list" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search list..." className="input w-full" />
              <div className="flex items-center justify-end gap-3 text-sm">
                <button onClick={toggleAll} disabled={!list.length} className="btn-primary bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50">Select/Deselect All</button>
                <span className="text-slate-700">{picked.size} of {students.length} selected</span>
              </div>
              <div>
                <p className="font-bold text-sm text-slate-800 mb-1">Users List</p>
                <div className="border border-slate-200 rounded-lg h-56 overflow-y-auto divide-y divide-slate-100">
                  {!enabled ? <p className="p-4 text-sm text-slate-400">Choose a level or class, then press Filter.</p>
                    : isLoading ? <div className="p-6 text-center"><Loader2 className="animate-spin mx-auto text-slate-400" size={18} /></div>
                    : list.length === 0 ? <p className="p-4 text-sm text-slate-400">No students found.</p>
                    : list.map((s) => (
                      <label key={s.id} className="flex items-center gap-3 px-3 py-2 hover:bg-slate-50 cursor-pointer text-sm">
                        <input type="checkbox" checked={picked.has(s.id)} onChange={() => setPicked((p) => { const n = new Set(p); n.has(s.id) ? n.delete(s.id) : n.add(s.id); return n; })} />
                        <span className="font-medium text-slate-800">{s.first_name} {s.last_name}</span>
                        <span className="text-xs text-slate-400 ml-auto">{s.class_name || ""}</span>
                      </label>
                    ))}
                </div>
              </div>
            </div>
          </div>
          <div><label className="label">Case Statement *</label><textarea aria-label="Case Statement" value={statement} onChange={(e) => setStatement(e.target.value)} rows={5} className="input w-full" /></div>
          <div><label className="label">Report Date *</label><input aria-label="Report Date" type="date" value={date} onChange={(e) => setDate(e.target.value)} className="input w-full" /></div>
        </div>
        <div className="border-t border-slate-200 px-5 py-3 flex justify-end gap-2">
          <button onClick={submit} disabled={busy || !picked.size || !statement.trim() || !date} className="btn-primary gap-2 bg-emerald-600 hover:bg-emerald-700">{busy && <Loader2 size={14} className="animate-spin" />} Submit</button>
          <button onClick={onClose} className="btn-secondary bg-sky-700 text-white hover:bg-sky-800 border-sky-700">Cancel</button>
        </div>
      </div>
    </div>
  );
}

// ── View / update a case: action, committee ("received by"), sanction, status ──
function CaseDetailModal({ c, canWrite, actions, committees, onClose, onSave, saving }: { c: any; canWrite: boolean; actions: any[]; committees: any[]; onClose: () => void; onSave: (d: object) => void; saving: boolean }) {
  const [f, setF] = useState({ action_id: c.action_id || "", committee_id: c.committee_id || "", sanction: c.sanction || "", status: c.status || "pending" });
  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 flex items-center justify-center p-4" onClick={onClose} role="dialog" aria-label="Disciplinary case">
      <div className="bg-white rounded-xl w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl p-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3"><h2 className="font-bold text-slate-900 flex items-center gap-2"><Gavel size={16} /> {c.student_name}</h2><button aria-label="Close" onClick={onClose} className="text-slate-400"><X size={18} /></button></div>
        <p className="text-xs text-slate-400 mb-3">{[c.class_name, `Reported by ${c.recorded_by_name || "—"}`, fmtDate(c.created_at || c.case_date)].filter(Boolean).join(" · ")}</p>
        {c.offence && <p className="text-sm text-slate-700 mb-4 whitespace-pre-wrap"><span className="text-xs font-semibold text-slate-400 uppercase">Case statement </span><br />{c.offence}</p>}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div><label className="label">Disciplinary Action</label><select disabled={!canWrite} value={f.action_id} onChange={(e) => setF({ ...f, action_id: e.target.value })} className="input"><option value="">—</option>{actions.filter((a) => a.is_active).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></div>
          <div><label className="label">Received By (committee)</label><select disabled={!canWrite} value={f.committee_id} onChange={(e) => setF({ ...f, committee_id: e.target.value })} className="input"><option value="">—</option>{committees.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></div>
          <div className="sm:col-span-2"><label className="label">Disciplinary Status</label><select disabled={!canWrite} value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })} className="input capitalize">{STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}</select></div>
          <div className="sm:col-span-2"><label className="label">Sanction / notes</label><textarea disabled={!canWrite} value={f.sanction} onChange={(e) => setF({ ...f, sanction: e.target.value })} rows={3} className="input w-full" /></div>
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="btn-secondary">Close</button>
          {canWrite && <button onClick={() => onSave({ action_id: f.action_id || null, committee_id: f.committee_id || null, sanction: f.sanction || null, status: f.status })} disabled={saving} className="btn-primary gap-2">{saving && <Loader2 size={14} className="animate-spin" />} Save</button>}
        </div>
      </div>
    </div>
  );
}
