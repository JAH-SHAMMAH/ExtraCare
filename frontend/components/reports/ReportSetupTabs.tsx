"use client";

import { useEffect, useState } from "react";
import {
  useSessions, useTerms, useSubTerms,
  useBootstrapTerms, useCreateTerm, useUpdateTerm, useDeleteTerm,
  useCreateSubTerm, useUpdateSubTerm, useDeleteSubTerm,
  useTermPeriods, useUpsertTermPeriod, useDeleteTermPeriod,
  useReportDeadlines, useCreateDeadline, useUpdateDeadline, useDeleteDeadline,
  useCommentTypes, useCreateCommentType, useUpdateCommentType, useDeleteCommentType,
  useDefaultComments, useCreateDefaultComment, useDeleteDefaultComment,
  useGradingScales, useCreateScale, useUpdateScale, useReplaceScaleBands, useDeleteScale,
  useReportBranding, useUpdateReportBranding,
  useLevelSettings, useUpsertLevelSetting,
  useSubjectExclusions, useCreateSubjectExclusion, useDeleteSubjectExclusion,
} from "@/hooks/usePlatform";
import { useYearGroups, useSubjects } from "@/hooks/useSchool";
import { cn } from "@/lib/utils";
import { Plus, Trash2, Loader2, Power, Check, X, Sparkles } from "lucide-react";

// ── Terms & Sub-term ─────────────────────────────────────────────────────────

export function TermsTab({ canWrite }: { canWrite: boolean }) {
  const { data: terms = [], isLoading } = useTerms();
  const { data: subs = [] } = useSubTerms();
  const bootstrap = useBootstrapTerms();
  const createTerm = useCreateTerm();
  const updateTerm = useUpdateTerm();
  const deleteTerm = useDeleteTerm();
  const [f, setF] = useState({ name: "", alias: "", position: "" });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold text-slate-800">Terms</h2>
        {canWrite && terms.length === 0 && (
          <button onClick={() => bootstrap.mutate({})} disabled={bootstrap.isPending} className="btn-secondary gap-2">
            {bootstrap.isPending ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />} Seed Autumn/Spring/Summer
          </button>
        )}
      </div>

      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[160px]"><label className="label">Term name</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="e.g. Autumn" /></div>
          <div><label className="label">Alias</label><input value={f.alias} onChange={(e) => setF({ ...f, alias: e.target.value })} className="input w-28" /></div>
          <div><label className="label">Order</label><input type="number" value={f.position} onChange={(e) => setF({ ...f, position: e.target.value })} className="input w-20" /></div>
          <button onClick={() => f.name.trim() && createTerm.mutate({ name: f.name.trim(), alias: f.alias || null, position: f.position ? Number(f.position) : 0 }, { onSuccess: () => setF({ name: "", alias: "", position: "" }) })} disabled={!f.name.trim() || createTerm.isPending} className="btn-primary gap-2"><Plus size={15} /> Add Term</button>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["S/N", "Term", "Alias", "Active", "Active Sub-term", ""].map((h) => <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? <tr><td colSpan={6} className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></td></tr>
              : terms.length === 0 ? <tr><td colSpan={6} className="py-8 text-center text-sm text-slate-400">No terms yet.</td></tr>
              : terms.map((t: any, i: number) => (
                <tr key={t.id} className="hover:bg-slate-50/70">
                  <td className="px-4 py-3 text-sm text-slate-500">{i + 1}</td>
                  <td className="px-4 py-3 text-sm font-semibold text-slate-800">{t.name}</td>
                  <td className="px-4 py-3 text-sm text-slate-500">{t.alias || "—"}</td>
                  <td className="px-4 py-3">
                    <button disabled={!canWrite} onClick={() => updateTerm.mutate({ id: t.id, data: { is_active: !t.is_active } })}
                      className={cn("inline-flex items-center justify-center w-8 h-6 rounded-md", t.is_active ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-400")}>
                      {t.is_active ? <Check size={14} /> : <X size={14} />}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    {canWrite ? (
                      <select value={t.active_sub_term_id || ""} onChange={(e) => updateTerm.mutate({ id: t.id, data: { active_sub_term_id: e.target.value || null } })} className="input py-1 text-sm w-auto min-w-[120px]">
                        <option value="">—</option>
                        {(subs as any[]).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                      </select>
                    ) : <span className="text-sm text-slate-600">{t.active_sub_term_name || "—"}</span>}
                  </td>
                  <td className="px-4 py-3">{canWrite && <button onClick={() => { if (confirm(`Delete ${t.name}?`)) deleteTerm.mutate(t.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      <SubTermsPanel canWrite={canWrite} />
    </div>
  );
}

function SubTermsPanel({ canWrite }: { canWrite: boolean }) {
  const { data: subs = [], isLoading } = useSubTerms();
  const create = useCreateSubTerm();
  const update = useUpdateSubTerm();
  const del = useDeleteSubTerm();
  const [f, setF] = useState({ name: "", position: "" });

  return (
    <div className="space-y-3">
      <h2 className="text-sm font-bold text-slate-800">Sub-terms <span className="text-xs font-normal text-slate-400">(Half-Term / Full-Term)</span></h2>
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[160px]"><label className="label">Sub-term name</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="e.g. Half-Term" /></div>
          <div><label className="label">Order</label><input type="number" value={f.position} onChange={(e) => setF({ ...f, position: e.target.value })} className="input w-20" /></div>
          <button onClick={() => f.name.trim() && create.mutate({ name: f.name.trim(), position: f.position ? Number(f.position) : 0 }, { onSuccess: () => setF({ name: "", position: "" }) })} disabled={!f.name.trim() || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add Sub-term</button>
        </div>
      )}
      {isLoading ? <div className="py-6 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
        : (subs as any[]).length === 0 ? <p className="text-sm text-slate-400 py-4 text-center bg-white rounded-xl border border-slate-200">No sub-terms.</p>
        : (
          <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
            {(subs as any[]).map((s) => (
              <div key={s.id} className="flex items-center justify-between px-5 py-3">
                <span className="text-sm font-semibold text-slate-800">{s.name} <span className="text-xs font-normal text-slate-400">· #{s.position}</span></span>
                <div className="flex items-center gap-2">
                  <span className={cn("badge", s.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200")}>{s.is_active ? "Active" : "Inactive"}</span>
                  {canWrite && <>
                    <button onClick={() => update.mutate({ id: s.id, data: { is_active: !s.is_active } })} className="text-slate-400 hover:text-amber-600 p-1"><Power size={15} /></button>
                    <button onClick={() => { if (confirm(`Delete ${s.name}?`)) del.mutate(s.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>
                  </>}
                </div>
              </div>
            ))}
          </div>
        )}
    </div>
  );
}

// ── Session picker + period rows (shared by Term Dates / Attendance) ─────────

function useSessionPicker() {
  const { data: sessions = [] } = useSessions();
  const [sessionId, setSessionId] = useState("");
  useEffect(() => { if (!sessionId && sessions.length) setSessionId((sessions as any[]).find((s) => s.is_current)?.id || sessions[0].id); }, [sessions, sessionId]);
  return { sessions, sessionId, setSessionId };
}

function SessionSelect({ sessions, sessionId, setSessionId }: any) {
  return (
    <div className="mb-5">
      <label className="label">Session</label>
      <select value={sessionId} onChange={(e) => setSessionId(e.target.value)} className="input max-w-xs">
        {(sessions as any[]).map((s) => <option key={s.id} value={s.id}>{s.name}{s.is_current ? " (current)" : ""}</option>)}
      </select>
    </div>
  );
}

function AddPeriodRow({ sessionId, canWrite }: { sessionId: string; canWrite: boolean }) {
  const { data: terms = [] } = useTerms();
  const { data: subs = [] } = useSubTerms();
  const upsert = useUpsertTermPeriod();
  const [termId, setTermId] = useState("");
  const [subId, setSubId] = useState("");
  if (!canWrite) return null;
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3 mb-4">
      <div><label className="label">Term</label><select value={termId} onChange={(e) => setTermId(e.target.value)} className="input"><option value="">—</option>{(terms as any[]).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
      <div><label className="label">Sub-term</label><select value={subId} onChange={(e) => setSubId(e.target.value)} className="input"><option value="">—</option>{(subs as any[]).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
      <button onClick={() => termId && subId && upsert.mutate({ session_id: sessionId, term_id: termId, sub_term_id: subId }, { onSuccess: () => { setTermId(""); setSubId(""); } })} disabled={!termId || !subId || upsert.isPending} className="btn-primary gap-2"><Plus size={15} /> Add Period</button>
    </div>
  );
}

const FIELD_SETS = {
  dates: [["end_date", "Term/Sub Ends", "date"], ["next_term_begins", "Next Begins", "date"], ["published_date", "Published", "date"]],
  attendance: [["begin_date", "Begin", "date"], ["end_date", "End", "date"], ["excluded_days", "Excluded", "number"], ["total_days", "Total", "number"]],
} as const;

function PeriodTable({ sessionId, mode, canWrite }: { sessionId: string; mode: "dates" | "attendance"; canWrite: boolean }) {
  const { data: rows = [], isLoading } = useTermPeriods(sessionId);
  const upsert = useUpsertTermPeriod();
  const del = useDeleteTermPeriod();
  const fields = FIELD_SETS[mode];

  // Send the FULL existing row + the patch so editing a "dates" field never nulls
  // the "attendance" fields (both tabs share one TermPeriod row; upsert overwrites).
  const save = (row: any, patch: Record<string, any>) =>
    upsert.mutate({
      session_id: sessionId, term_id: row.term_id, sub_term_id: row.sub_term_id,
      begin_date: row.begin_date, end_date: row.end_date, next_term_begins: row.next_term_begins,
      published_date: row.published_date, excluded_days: row.excluded_days, total_days: row.total_days,
      ...patch,
    });

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
      <table className="w-full text-left">
        <thead><tr className="bg-slate-50/80 border-b border-slate-100">
          {["Term", "Sub-term", ...fields.map((f) => f[1]), ""].map((h, i) => <th key={i} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}
        </tr></thead>
        <tbody className="divide-y divide-slate-50">
          {isLoading ? <tr><td colSpan={fields.length + 3} className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></td></tr>
            : (rows as any[]).length === 0 ? <tr><td colSpan={fields.length + 3} className="py-8 text-center text-sm text-slate-400">No periods for this session yet.</td></tr>
            : (rows as any[]).map((r) => (
              <tr key={r.id} className="hover:bg-slate-50/70">
                <td className="px-4 py-3 text-sm font-semibold text-slate-800">{r.term_name}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{r.sub_term_name}</td>
                {fields.map(([key, , type]) => (
                  <td key={key} className="px-4 py-2">
                    <input type={type} defaultValue={r[key] ?? ""} disabled={!canWrite}
                      onBlur={(e) => { const v = e.target.value; const nv = type === "number" ? (v === "" ? null : Number(v)) : (v || null); if (nv !== (r[key] ?? null)) save(r, { [key]: nv }); }}
                      className="input py-1 text-sm w-32" />
                  </td>
                ))}
                <td className="px-4 py-2">{canWrite && <button onClick={() => { if (confirm("Delete this period?")) del.mutate(r.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}

export function TermDatesTab({ canWrite }: { canWrite: boolean }) {
  const picker = useSessionPicker();
  return (
    <div>
      <SessionSelect {...picker} />
      <AddPeriodRow sessionId={picker.sessionId} canWrite={canWrite} />
      {picker.sessionId && <PeriodTable sessionId={picker.sessionId} mode="dates" canWrite={canWrite} />}
    </div>
  );
}

export function AttendanceTab({ canWrite }: { canWrite: boolean }) {
  const picker = useSessionPicker();
  return (
    <div>
      <p className="text-xs text-slate-400 mb-4">The <b>Total</b> days is the attendance % denominator; <b>Excluded</b> days are non-school days in the window. Shares each row with Term Begins/Ends.</p>
      <SessionSelect {...picker} />
      <AddPeriodRow sessionId={picker.sessionId} canWrite={canWrite} />
      {picker.sessionId && <PeriodTable sessionId={picker.sessionId} mode="attendance" canWrite={canWrite} />}
    </div>
  );
}

// ── Deadline ─────────────────────────────────────────────────────────────────

export function DeadlineTab({ canWrite }: { canWrite: boolean }) {
  const picker = useSessionPicker();
  const { data: terms = [] } = useTerms();
  const { data: subs = [] } = useSubTerms();
  const { data: rows = [], isLoading } = useReportDeadlines(picker.sessionId);
  const create = useCreateDeadline();
  const update = useUpdateDeadline();
  const del = useDeleteDeadline();
  const [f, setF] = useState({ term_id: "", sub_term_id: "", submission_deadline: "" });

  return (
    <div>
      <SessionSelect {...picker} />
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3 mb-4">
          <div><label className="label">Term</label><select value={f.term_id} onChange={(e) => setF({ ...f, term_id: e.target.value })} className="input"><option value="">—</option>{(terms as any[]).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
          <div><label className="label">Sub-term</label><select value={f.sub_term_id} onChange={(e) => setF({ ...f, sub_term_id: e.target.value })} className="input"><option value="">—</option>{(subs as any[]).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
          <div><label className="label">Deadline</label><input type="date" value={f.submission_deadline} onChange={(e) => setF({ ...f, submission_deadline: e.target.value })} className="input" /></div>
          <button onClick={() => f.term_id && picker.sessionId && create.mutate({ session_id: picker.sessionId, term_id: f.term_id, sub_term_id: f.sub_term_id || null, submission_deadline: f.submission_deadline || null, status: "open" }, { onSuccess: () => setF({ term_id: "", sub_term_id: "", submission_deadline: "" }) })} disabled={!f.term_id || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add Deadline</button>
        </div>
      )}
      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Term", "Sub-term", "Status", "Submission Deadline", ""].map((h) => <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? <tr><td colSpan={5} className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></td></tr>
              : (rows as any[]).length === 0 ? <tr><td colSpan={5} className="py-8 text-center text-sm text-slate-400">No deadlines for this session.</td></tr>
              : (rows as any[]).map((d) => (
                <tr key={d.id} className="hover:bg-slate-50/70">
                  <td className="px-4 py-3 text-sm font-semibold text-slate-800">{d.term_name}</td>
                  <td className="px-4 py-3 text-sm text-slate-600">{d.sub_term_name || "—"}</td>
                  <td className="px-4 py-3">
                    {canWrite ? (
                      <select value={d.status} onChange={(e) => update.mutate({ id: d.id, data: { session_id: d.session_id, term_id: d.term_id, status: e.target.value } })} className="input py-1 text-sm w-auto capitalize"><option value="open">open</option><option value="closed">closed</option></select>
                    ) : <span className="badge capitalize bg-slate-50 text-slate-600 border-slate-200">{d.status}</span>}
                  </td>
                  <td className="px-4 py-2"><input type="date" defaultValue={d.submission_deadline ?? ""} disabled={!canWrite} onBlur={(e) => { const v = e.target.value || null; if (v !== (d.submission_deadline ?? null)) update.mutate({ id: d.id, data: { session_id: d.session_id, term_id: d.term_id, submission_deadline: v } }); }} className="input py-1 text-sm w-36" /></td>
                  <td className="px-4 py-2">{canWrite && <button onClick={() => del.mutate(d.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── S-1a: Comment types ──────────────────────────────────────────────────────

export function CommentTab({ canWrite }: { canWrite: boolean }) {
  const { data: rows = [], isLoading } = useCommentTypes();
  const create = useCreateCommentType();
  const update = useUpdateCommentType();
  const del = useDeleteCommentType();
  const [f, setF] = useState({ name: "", comment_type: "short", max_length: "" });

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-400">Named comment slots on the report card. Short for a phrase; Long for a paragraph (with an optional character cap).</p>
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[180px]"><label className="label">Comment name</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="e.g. Teacher Comment" /></div>
          <div><label className="label">Type</label><select value={f.comment_type} onChange={(e) => setF({ ...f, comment_type: e.target.value })} className="input"><option value="short">Short</option><option value="long">Long</option></select></div>
          <div><label className="label">Max length</label><input type="number" value={f.max_length} onChange={(e) => setF({ ...f, max_length: e.target.value })} className="input w-24" placeholder="—" /></div>
          <button onClick={() => f.name.trim() && create.mutate({ name: f.name.trim(), comment_type: f.comment_type, max_length: f.max_length ? Number(f.max_length) : null }, { onSuccess: () => setF({ name: "", comment_type: "short", max_length: "" }) })} disabled={!f.name.trim() || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add Comment Type</button>
        </div>
      )}
      {isLoading ? <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
        : (rows as any[]).length === 0 ? <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">No comment types yet.</p>
        : (
          <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
            {(rows as any[]).map((c) => (
              <div key={c.id} className="flex items-center justify-between px-5 py-3">
                <div><p className="text-sm font-semibold text-slate-800">{c.name}</p><p className="text-xs text-slate-400 capitalize">{c.comment_type}{c.max_length ? " · max " + c.max_length : ""}</p></div>
                <div className="flex items-center gap-2">
                  <span className={cn("badge", c.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200")}>{c.is_active ? "Active" : "Inactive"}</span>
                  {canWrite ? (
                    <>
                      <button onClick={() => update.mutate({ id: c.id, data: { is_active: !c.is_active } })} className="text-slate-400 hover:text-amber-600 p-1"><Power size={15} /></button>
                      <button onClick={() => { if (confirm("Delete " + c.name + "?")) del.mutate(c.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>
                    </>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}
    </div>
  );
}

// ── S-1a: Result Default Comment bank ────────────────────────────────────────

const TEACHER_TYPES: [string, string][] = [["subject", "Subject Teacher"], ["class", "Class Teacher"], ["head", "Head Teacher"]];

export function DefaultCommentTab({ canWrite }: { canWrite: boolean }) {
  const { data: scales = [] } = useGradingScales();
  const [filter, setFilter] = useState({ teacher_type: "", grading_scale_id: "", year_group: "" });
  const params = { teacher_type: filter.teacher_type || undefined, grading_scale_id: filter.grading_scale_id || undefined, year_group: filter.year_group || undefined };
  const { data: rows = [], isLoading } = useDefaultComments(params);
  const create = useCreateDefaultComment();
  const del = useDeleteDefaultComment();
  const empty = { teacher_type: "class", grading_scale_id: "", year_group: "", min_score: "", max_score: "", comment: "" };
  const [f, setF] = useState(empty);

  const submit = () => {
    if (!f.comment.trim()) return;
    create.mutate({
      teacher_type: f.teacher_type, grading_scale_id: f.grading_scale_id || null, year_group: f.year_group || null,
      min_score: f.min_score ? Number(f.min_score) : null, max_score: f.max_score ? Number(f.max_score) : null, comment: f.comment.trim(),
    }, { onSuccess: () => setF(empty) });
  };

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-400">Auto-fill comments by score band — when a score falls in [min, max] for the chosen teacher role, this comment pre-fills the report.</p>

      <div className="flex flex-wrap gap-3">
        <select value={filter.teacher_type} onChange={(e) => setFilter({ ...filter, teacher_type: e.target.value })} className="input w-auto"><option value="">All roles</option>{TEACHER_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        <select value={filter.grading_scale_id} onChange={(e) => setFilter({ ...filter, grading_scale_id: e.target.value })} className="input w-auto"><option value="">All scales</option>{(scales as any[]).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
        <input value={filter.year_group} onChange={(e) => setFilter({ ...filter, year_group: e.target.value })} className="input w-auto" placeholder="Year group filter" />
      </div>

      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          <div><label className="label">Teacher type</label><select value={f.teacher_type} onChange={(e) => setF({ ...f, teacher_type: e.target.value })} className="input">{TEACHER_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
          <div><label className="label">Grade system</label><select value={f.grading_scale_id} onChange={(e) => setF({ ...f, grading_scale_id: e.target.value })} className="input"><option value="">— Any —</option>{(scales as any[]).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
          <div><label className="label">Year group</label><input value={f.year_group} onChange={(e) => setF({ ...f, year_group: e.target.value })} className="input" placeholder="e.g. YEAR 7 (blank = all)" /></div>
          <div className="grid grid-cols-2 gap-2"><div><label className="label">Min score</label><input type="number" value={f.min_score} onChange={(e) => setF({ ...f, min_score: e.target.value })} className="input" /></div><div><label className="label">Max score</label><input type="number" value={f.max_score} onChange={(e) => setF({ ...f, max_score: e.target.value })} className="input" /></div></div>
          <div className="md:col-span-2"><label className="label">Comment</label><textarea value={f.comment} onChange={(e) => setF({ ...f, comment: e.target.value })} className="input" rows={2} /></div>
          <div className="md:col-span-2 flex justify-end"><button onClick={submit} disabled={!f.comment.trim() || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add Comment</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Role", "Scale", "Year", "Band", "Comment", ""].map((h) => <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? <tr><td colSpan={6} className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></td></tr>
              : (rows as any[]).length === 0 ? <tr><td colSpan={6} className="py-8 text-center text-sm text-slate-400">No default comments.</td></tr>
              : (rows as any[]).map((d) => (
                <tr key={d.id} className="hover:bg-slate-50/70 align-top">
                  <td className="px-4 py-3 text-sm text-slate-700 capitalize">{d.teacher_type}</td>
                  <td className="px-4 py-3 text-sm text-slate-500">{d.grading_scale_name || "—"}</td>
                  <td className="px-4 py-3 text-sm text-slate-500">{d.year_group || "All"}</td>
                  <td className="px-4 py-3 text-sm text-slate-500 tabular-nums">{d.min_score != null || d.max_score != null ? (d.min_score ?? "") + "–" + (d.max_score ?? "") : "—"}</td>
                  <td className="px-4 py-3 text-sm text-slate-700 max-w-md">{d.comment}</td>
                  <td className="px-4 py-3">{canWrite ? <button onClick={() => del.mutate(d.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button> : null}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── S-1b: Grading System ─────────────────────────────────────────────────────

const PURPOSES: [string, string][] = [["grade", "Main Grade"], ["keys", "Keys / Legend"], ["cumulative", "Cumulative"], ["mock", "Mock"]];

export function GradingSystemTab({ canWrite }: { canWrite: boolean }) {
  const { data: scales = [], isLoading } = useGradingScales();
  const create = useCreateScale();
  const update = useUpdateScale();
  const del = useDeleteScale();
  const [f, setF] = useState({ name: "", scale_type: "numeric", purpose: "grade" });

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-400">Grading scales used on the report. <b>Scored</b> scales map a percentage to a grade; <b>Non-Scored</b> scales are descriptor labels. <b>Show in table</b> prints the scale legend on the report.</p>
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[160px]"><label className="label">Grading name</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="e.g. Grading Scale" /></div>
          <div><label className="label">Type</label><select value={f.scale_type} onChange={(e) => setF({ ...f, scale_type: e.target.value })} className="input"><option value="numeric">Scored</option><option value="descriptor">Non-Scored</option></select></div>
          <div><label className="label">Purpose</label><select value={f.purpose} onChange={(e) => setF({ ...f, purpose: e.target.value })} className="input">{PURPOSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
          <button onClick={() => f.name.trim() && create.mutate({ name: f.name.trim(), scale_type: f.scale_type, purpose: f.purpose, bands: [] }, { onSuccess: () => setF({ name: "", scale_type: "numeric", purpose: "grade" }) })} disabled={!f.name.trim() || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add Grading</button>
        </div>
      )}
      {isLoading ? <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
        : (scales as any[]).length === 0 ? <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">No grading scales yet.</p>
        : <div className="space-y-3">{(scales as any[]).map((sc) => <GradingScaleRow key={sc.id} scale={sc} canWrite={canWrite} update={update} del={del} />)}</div>}
    </div>
  );
}

function GradingScaleRow({ scale, canWrite, update, del }: { scale: any; canWrite: boolean; update: any; del: any }) {
  const [open, setOpen] = useState(false);
  const replace = useReplaceScaleBands();
  const numeric = scale.scale_type === "numeric";
  const [bands, setBands] = useState<any[]>(scale.bands || []);

  const addBand = () => setBands((b) => [...b, { grade: "", min_score: "", max_score: "", remark: "", position: b.length }]);
  const setBand = (i: number, k: string, v: string) => setBands((b) => b.map((x, j) => j === i ? { ...x, [k]: v } : x));
  const rmBand = (i: number) => setBands((b) => b.filter((_, j) => j !== i));
  const saveBands = () => replace.mutate({ id: scale.id, bands: bands.map((b, i) => ({
    grade: b.grade, min_score: b.min_score === "" ? null : Number(b.min_score),
    max_score: b.max_score === "" ? null : Number(b.max_score), remark: b.remark || null, position: i,
  })) }, { onSuccess: () => setOpen(false) });

  return (
    <div className="bg-white rounded-xl border border-slate-200">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
        <div className="min-w-0">
          <p className="text-sm font-bold text-slate-800">{scale.name} {scale.is_provisional && <span className="badge bg-amber-50 text-amber-700 border-amber-200">provisional</span>}</p>
          <p className="text-xs text-slate-400">{numeric ? "Scored" : "Non-Scored"} · {(scale.bands || []).length} bands</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {canWrite ? (
            <select value={scale.purpose} onChange={(e) => update.mutate({ id: scale.id, data: { purpose: e.target.value } })} className="input py-1 text-sm w-auto">{PURPOSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          ) : <span className="badge bg-slate-50 text-slate-600 border-slate-200 capitalize">{scale.purpose}</span>}
          <button disabled={!canWrite} onClick={() => update.mutate({ id: scale.id, data: { show_in_table: !scale.show_in_table } })}
            className={cn("text-xs font-semibold rounded-md px-2.5 py-1", scale.show_in_table ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-400")}>
            {scale.show_in_table ? "In table" : "Hidden"}
          </button>
          <button onClick={() => { setBands(scale.bands || []); setOpen((o) => !o); }} className="btn-secondary py-1 text-sm">Bands</button>
          {canWrite && <button onClick={() => { if (confirm("Delete " + scale.name + "?")) del.mutate(scale.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>}
        </div>
      </div>
      {open && (
        <div className="border-t border-slate-100 p-4 space-y-2">
          {bands.map((b, i) => (
            <div key={i} className="flex flex-wrap items-center gap-2">
              <input value={b.grade} onChange={(e) => setBand(i, "grade", e.target.value)} className="input w-24 py-1 text-sm" placeholder="Grade" disabled={!canWrite} />
              {numeric && <><input value={b.min_score ?? ""} onChange={(e) => setBand(i, "min_score", e.target.value)} className="input w-20 py-1 text-sm" placeholder="Min" disabled={!canWrite} />
              <input value={b.max_score ?? ""} onChange={(e) => setBand(i, "max_score", e.target.value)} className="input w-20 py-1 text-sm" placeholder="Max" disabled={!canWrite} /></>}
              <input value={b.remark ?? ""} onChange={(e) => setBand(i, "remark", e.target.value)} className="input flex-1 min-w-[120px] py-1 text-sm" placeholder="Remark" disabled={!canWrite} />
              {canWrite && <button onClick={() => rmBand(i)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}
            </div>
          ))}
          {canWrite && (
            <div className="flex items-center gap-3 pt-2">
              <button onClick={addBand} className="btn-secondary py-1 text-sm gap-1"><Plus size={14} /> Add band</button>
              <button onClick={saveBands} disabled={replace.isPending} className="btn-primary py-1 text-sm gap-1">{replace.isPending && <Loader2 size={13} className="animate-spin" />} Save bands</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── S-1b: School Motto, Seal & Sponsor (report branding) ─────────────────────

const BRAND_TEXT: [string, string, string][] = [
  ["school_motto", "School Motto", "text"],
  ["school_name_alias", "School Name Alias", "text"],
  ["school_head_title", "School Head Title", "text"],
  ["school_head_name", "School Head Full Name", "text"],
  ["class_teacher_title", "Class Teacher Title", "text"],
  ["school_address", "School Address", "text"],
  ["school_email", "School Email", "text"],
  ["school_website", "School Website", "text"],
  ["school_phone", "School Phone Number", "text"],
  ["promotion_comment", "Promotion Comment", "text"],
  ["demotion_comment", "Demotion Comment", "text"],
];
const BRAND_NUM: [string, string][] = [
  ["full_term_passmark", "Full Term Passmark"],
  ["mid_term_passmark", "Mid Term Passmark"],
  ["min_average_honours", "Min Average For Honours Roll"],
];
const BRAND_IMG: [string, string][] = [
  ["logo_url", "School Logo (image URL)"],
  ["head_signature_url", "School Head Signature (image URL)"],
  ["logo_background_url", "School Logo Background (image URL)"],
  ["sponsor_url", "School Sponsor (image URL)"],
];

export function BrandingTab({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading } = useReportBranding();
  const save = useUpdateReportBranding();
  const [form, setForm] = useState<any>(null);
  useEffect(() => { if (data && !form) setForm({ ...data }); }, [data, form]);

  if (isLoading || !form) return <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>;
  const set = (k: string, v: string) => setForm((p: any) => ({ ...p, [k]: v }));

  const submit = () => {
    const payload: any = {};
    for (const [k] of BRAND_TEXT) payload[k] = form[k] || null;
    for (const [k] of BRAND_IMG) payload[k] = form[k] || null;
    for (const [k] of BRAND_NUM) payload[k] = form[k] === "" || form[k] == null ? null : Number(form[k]);
    save.mutate(payload);
  };

  return (
    <div className="space-y-5">
      <p className="text-xs text-slate-400">The branding block printed at the top of the report card. Passmarks feed the pass/fail on the card. Images take a URL (upload the image elsewhere, then paste its address).</p>
      <div className="bg-white rounded-xl border border-slate-200 p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        {BRAND_TEXT.map(([k, label]) => (
          <div key={k}><label className="label">{label}</label><input value={form[k] ?? ""} onChange={(e) => set(k, e.target.value)} className="input" disabled={!canWrite} /></div>
        ))}
        {BRAND_NUM.map(([k, label]) => (
          <div key={k}><label className="label">{label}</label><input type="number" value={form[k] ?? ""} onChange={(e) => set(k, e.target.value)} className="input" disabled={!canWrite} /></div>
        ))}
      </div>
      <div className="bg-white rounded-xl border border-slate-200 p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        <h3 className="md:col-span-2 text-sm font-bold text-slate-800">Seal &amp; Sponsor images</h3>
        {BRAND_IMG.map(([k, label]) => (
          <div key={k}><label className="label">{label}</label><input value={form[k] ?? ""} onChange={(e) => set(k, e.target.value)} className="input" placeholder="https://…" disabled={!canWrite} /></div>
        ))}
      </div>
      {canWrite && <div className="flex justify-end"><button onClick={submit} disabled={save.isPending} className="btn-primary gap-2">{save.isPending && <Loader2 size={15} className="animate-spin" />} Save Branding</button></div>}
    </div>
  );
}

// ── S-1c: Result Type + Result Photo (per year-group level settings) ─────────

function useLevelSettingHelpers() {
  const { data: years = [] } = useYearGroups();
  const { data: settings = [] } = useLevelSettings();
  const upsert = useUpsertLevelSetting();
  const byYear: Record<string, any> = {};
  for (const s of settings as any[]) byYear[s.year_group] = s;
  const settingFor = (yg: string) => byYear[yg] || { year_group: yg, result_type: "junior", show_position: true, show_photo: true };
  const save = (yg: string, patch: any) => { const cur = settingFor(yg); upsert.mutate({ year_group: yg, result_type: cur.result_type, show_position: cur.show_position, show_photo: cur.show_photo, ...patch }); };
  return { years: years as any[], settingFor, save, saving: upsert.isPending };
}

export function ResultTypeTab({ canWrite }: { canWrite: boolean }) {
  const { years, settingFor, save } = useLevelSettingHelpers();
  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-400">Per year group: classify the result as <b>Junior</b> or <b>Senior</b>, and choose whether the pupil&apos;s <b>position in class</b> is printed on the report.</p>
      {years.length === 0 ? <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">No year groups defined yet. Add year groups under Classes/YearGroups first.</p> : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Year group", "Result type", "Position in class"].map((h) => <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-slate-50">
              {years.map((y) => { const s = settingFor(y.name); return (
                <tr key={y.id || y.name} className="hover:bg-slate-50/70">
                  <td className="px-4 py-3 text-sm font-semibold text-slate-800">{y.name}</td>
                  <td className="px-4 py-3">
                    {canWrite ? <select value={s.result_type} onChange={(e) => save(y.name, { result_type: e.target.value })} className="input py-1 text-sm w-auto"><option value="junior">Junior</option><option value="senior">Senior</option></select>
                      : <span className="text-sm capitalize text-slate-600">{s.result_type}</span>}
                  </td>
                  <td className="px-4 py-3">
                    <button disabled={!canWrite} onClick={() => save(y.name, { show_position: !s.show_position })} className={cn("text-xs font-semibold rounded-md px-2.5 py-1", s.show_position ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-400")}>{s.show_position ? "Shown" : "Hidden"}</button>
                  </td>
                </tr>
              ); })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function ResultPhotoTab({ canWrite }: { canWrite: boolean }) {
  const { years, settingFor, save } = useLevelSettingHelpers();
  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-400">Per year group: choose whether the pupil&apos;s photo appears on the printed report.</p>
      {years.length === 0 ? <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">No year groups defined yet.</p> : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {years.map((y) => { const s = settingFor(y.name); return (
            <div key={y.id || y.name} className="flex items-center justify-between px-5 py-3">
              <span className="text-sm font-semibold text-slate-800">{y.name}</span>
              <button disabled={!canWrite} onClick={() => save(y.name, { show_photo: !s.show_photo })} className={cn("text-xs font-semibold rounded-md px-2.5 py-1", s.show_photo ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-400")}>{s.show_photo ? "Enabled" : "Disabled"}</button>
            </div>
          ); })}
        </div>
      )}
    </div>
  );
}

// ── S-1c: Subjects For Score Exclusion ───────────────────────────────────────

export function ExclusionTab({ canWrite }: { canWrite: boolean }) {
  const { data: years = [] } = useYearGroups();
  const subjectsData: any = useSubjects({ page_size: 200 }).data;
  const subjects: any[] = subjectsData?.items ?? subjectsData ?? [];
  const [yearGroup, setYearGroup] = useState("");
  const { data: rows = [], isLoading } = useSubjectExclusions(yearGroup || undefined);
  const create = useCreateSubjectExclusion();
  const del = useDeleteSubjectExclusion();
  const [subjectId, setSubjectId] = useState("");

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-400">Subjects listed here still appear on the report but do <b>not</b> count toward totals or class position, for the chosen year group.</p>
      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
        <div><label className="label">Year group</label>
          <select value={yearGroup} onChange={(e) => setYearGroup(e.target.value)} className="input">
            <option value="">— Select —</option>
            {(years as any[]).map((y) => <option key={y.id || y.name} value={y.name}>{y.name}</option>)}
          </select>
        </div>
        {canWrite && yearGroup && (
          <>
            <div className="flex-1 min-w-[180px]"><label className="label">Subject</label>
              <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)} className="input">
                <option value="">— Select —</option>
                {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <button onClick={() => subjectId && create.mutate({ year_group: yearGroup, subject_id: subjectId }, { onSuccess: () => setSubjectId("") })} disabled={!subjectId || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Exclude</button>
          </>
        )}
      </div>

      {!yearGroup ? <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">Select a year group to view its excluded subjects.</p>
        : isLoading ? <div className="py-8 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
        : (rows as any[]).length === 0 ? <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">No excluded subjects for this year group.</p>
        : (
          <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
            {(rows as any[]).map((r) => (
              <div key={r.id} className="flex items-center justify-between px-5 py-3">
                <span className="text-sm font-semibold text-slate-800">{r.subject_name || r.subject_id.slice(0, 8)}</span>
                {canWrite && <button onClick={() => del.mutate(r.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>}
              </div>
            ))}
          </div>
        )}
    </div>
  );
}
