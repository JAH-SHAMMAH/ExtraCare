"use client";

import { useState, useEffect } from "react";
import { useCreateAssessment, useUpdateAssessment, useAssessmentCriteria } from "@/hooks/usePeople";
import { useCurrentSession } from "@/hooks/usePlatform";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import Link from "next/link";
import { Loader2 } from "lucide-react";
import type { StaffAssessment } from "@/types";

const STATUSES = ["draft", "finalized"];

/**
 * Shared create/edit form for a staff assessment. When active rubric criteria
 * exist, the reviewer scores each and the overall rating is derived server-side
 * (weighted average); with no criteria it falls back to a manual overall rating.
 */
export function AssessmentForm({ initial, onDone, onCancel }: {
  initial?: StaffAssessment | null;
  onDone?: () => void;
  onCancel?: () => void;
}) {
  const create = useCreateAssessment();
  const update = useUpdateAssessment();
  const { data: critData } = useAssessmentCriteria();
  const initialScoreIds = (initial?.scores || []).map((s) => s.criterion_id);
  const criteria = (critData?.items || []).filter((c) => c.is_active || initialScoreIds.includes(c.id));

  const { data: cur } = useCurrentSession();
  const currentPeriod = [cur?.name, cur?.term].filter(Boolean).join(" ");

  const [form, setForm] = useState({
    staff_user_id: initial?.staff_user_id || "",
    period: initial?.period || "",
    review_date: initial?.review_date || "",
    overall_rating: initial?.overall_rating?.toString() || "",
    strengths: initial?.strengths || "",
    improvements: initial?.improvements || "",
    goals: initial?.goals || "",
    status: initial?.status || "draft",
  });
  const [scores, setScores] = useState<Record<string, string>>(
    Object.fromEntries((initial?.scores || []).map((s) => [s.criterion_id, String(s.score)])),
  );
  useEffect(() => {
    if (!initial && currentPeriod) setForm((f) => (f.period ? f : { ...f, period: currentPeriod }));
  }, [currentPeriod, initial]);

  const busy = create.isPending || update.isPending;
  const usingCriteria = criteria.length > 0;

  const submit = () => {
    const scoreList = Object.entries(scores)
      .filter(([, v]) => v !== "")
      .map(([criterion_id, v]) => ({ criterion_id, score: Number(v) }));
    const payload: Record<string, unknown> = {
      period: form.period,
      review_date: form.review_date || null,
      strengths: form.strengths || null,
      improvements: form.improvements || null,
      goals: form.goals || null,
      status: form.status,
    };
    if (usingCriteria) payload.scores = scoreList;               // overall derived server-side
    else payload.overall_rating = form.overall_rating ? Number(form.overall_rating) : null;
    if (initial) {
      update.mutate({ id: initial.id, data: payload }, { onSuccess: onDone });
    } else {
      payload.staff_user_id = form.staff_user_id.trim();
      create.mutate(payload, { onSuccess: onDone });
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {!initial && (
        <div>
          <label className="label">Staff Member *</label>
          <EntityPicker type="staff" value={form.staff_user_id || null} onChange={(id) => setForm({ ...form, staff_user_id: id || "" })} />
        </div>
      )}
      <div>
        <label className="label">Review Period *</label>
        <input value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })} className="input" placeholder="e.g. 2025/2026 Term 1" />
      </div>
      <div>
        <label className="label">Review Date</label>
        <input type="date" value={form.review_date} onChange={(e) => setForm({ ...form, review_date: e.target.value })} className="input" />
      </div>
      <div>
        <label className="label">Status</label>
        <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className="input capitalize">
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {usingCriteria ? (
        <div className="md:col-span-2">
          <label className="label">Rubric scores <span className="text-slate-400 font-normal">— overall rating is the weighted average</span></label>
          <div className="rounded-xl border border-slate-200 divide-y divide-slate-50">
            {criteria.map((c) => (
              <div key={c.id} className="flex items-center gap-3 px-4 py-2.5">
                <div className="flex-1">
                  <p className="text-sm font-semibold text-slate-800">{c.name}{c.category ? <span className="text-slate-400 font-normal"> · {c.category}</span> : null}</p>
                  {c.description && <p className="text-xs text-slate-400">{c.description}</p>}
                </div>
                <span className="text-[11px] text-slate-400">×{c.weight}</span>
                <select
                  value={scores[c.id] ?? ""}
                  onChange={(e) => setScores((s) => ({ ...s, [c.id]: e.target.value }))}
                  className="input w-28 text-sm"
                >
                  <option value="">—</option>
                  {Array.from({ length: c.max_score }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n} / {c.max_score}</option>)}
                </select>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div>
          <label className="label">Overall Rating</label>
          <select value={form.overall_rating} onChange={(e) => setForm({ ...form, overall_rating: e.target.value })} className="input">
            <option value="">—</option>
            {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n} / 5</option>)}
          </select>
          <p className="text-[11px] text-slate-400 mt-1">No rubric configured. Define criteria under <Link href="/dashboard/modules/school/staff-assessment/setup" className="text-brand-600 font-semibold hover:underline">Setup</Link> to score against a rubric.</p>
        </div>
      )}

      <div className="md:col-span-2">
        <label className="label">Strengths</label>
        <textarea value={form.strengths} onChange={(e) => setForm({ ...form, strengths: e.target.value })} className="input" rows={2} />
      </div>
      <div className="md:col-span-2">
        <label className="label">Areas for Improvement</label>
        <textarea value={form.improvements} onChange={(e) => setForm({ ...form, improvements: e.target.value })} className="input" rows={2} />
      </div>
      <div className="md:col-span-2">
        <label className="label">Goals</label>
        <textarea value={form.goals} onChange={(e) => setForm({ ...form, goals: e.target.value })} className="input" rows={2} />
      </div>

      <div className="md:col-span-2 flex justify-end gap-3 mt-2">
        {onCancel && <button onClick={onCancel} className="btn-secondary">Cancel</button>}
        <button
          onClick={submit}
          disabled={(!initial && !form.staff_user_id.trim()) || !form.period.trim() || busy}
          className="btn-primary gap-2"
        >
          {busy && <Loader2 size={15} className="animate-spin" />}
          {initial ? "Update" : "Create"}
        </button>
      </div>
    </div>
  );
}
