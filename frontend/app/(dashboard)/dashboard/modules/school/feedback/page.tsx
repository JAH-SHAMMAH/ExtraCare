"use client";

import { useState } from "react";
import Link from "next/link";
import { useFeedbackList, useSubmitFeedback } from "@/hooks/useSchoolExperience";
import { useFeedbackSettings } from "@/hooks/useFeedbackExtras";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { formatDate } from "@/lib/utils";
import { Loader2, CheckCircle2, ListChecks } from "lucide-react";
import type { FeedbackItem, FeedbackCategory } from "@/types";

const CATEGORY_LABEL: Record<FeedbackCategory, string> = {
  general: "General", facilities: "Facilities", teaching: "Teaching",
  bullying: "Bullying", suggestion: "Suggestion", other: "Other",
};

export default function FeedbackFormPage() {
  const canManage = useHasPermission("school:feedback:write");
  const submitFeedback = useSubmitFeedback();
  const { data: settings } = useFeedbackSettings();
  const { data: mineData } = useFeedbackList({ mine: true, page: 1, page_size: 5 });
  const recent = (mineData?.items as FeedbackItem[] | undefined) || [];

  const [form, setForm] = useState({ subject: "", message: "", category: "general" as FeedbackCategory, is_anonymous: false, student_id: "" });
  const reset = () => setForm({ subject: "", message: "", category: "general", is_anonymous: false, student_id: "" });
  const submit = () => submitFeedback.mutate({ ...form, student_id: form.student_id || null }, { onSuccess: reset });

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Feedback</span><span>/</span><span className="text-brand-600 font-semibold">Feedback Form</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Submit Feedback</h1>
          <p className="text-slate-500 text-sm mt-0.5">Share a concern, suggestion or question with the school.</p>
        </div>
        <div className="flex gap-3">
          <Link href="/dashboard/modules/school/feedback/mine" className="btn-secondary gap-2">My Feedback</Link>
          {canManage && <Link href="/dashboard/modules/school/feedback/manage" className="btn-secondary gap-2"><ListChecks size={15} /> Manage</Link>}
        </div>
      </div>

      {settings?.acknowledgement_message && (
        <div className="rounded-xl border border-brand-200 bg-brand-50/50 p-4 mb-6 text-sm text-brand-800">{settings.acknowledgement_message}</div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 p-6 mb-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="md:col-span-2">
            <label className="label">Subject *</label>
            <input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} className="input" />
          </div>
          <div>
            <label className="label">Category *</label>
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value as FeedbackCategory })} className="input">
              {(Object.keys(CATEGORY_LABEL) as FeedbackCategory[]).map((k) => <option key={k} value={k}>{CATEGORY_LABEL[k]}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Student ID (if applicable)</label>
            <input value={form.student_id} onChange={(e) => setForm({ ...form, student_id: e.target.value })} className="input" />
          </div>
          <div className="md:col-span-2">
            <label className="label">Message *</label>
            <textarea value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} className="input" rows={4} />
          </div>
          {(settings?.allow_anonymous ?? true) && (
            <div className="md:col-span-2 flex items-center gap-2">
              <input id="anon" type="checkbox" checked={form.is_anonymous} onChange={(e) => setForm({ ...form, is_anonymous: e.target.checked })} />
              <label htmlFor="anon" className="text-xs font-medium text-slate-700">Submit anonymously</label>
            </div>
          )}
        </div>
        <div className="flex justify-end mt-4">
          <button onClick={submit} disabled={submitFeedback.isPending || !form.subject || !form.message} className="btn-primary gap-2">
            {submitFeedback.isPending && <Loader2 size={15} className="animate-spin" />}Submit
          </button>
        </div>
      </div>

      {recent.length > 0 && (
        <div>
          <h2 className="text-sm font-bold text-slate-800 mb-3">Your recent feedback</h2>
          <div className="space-y-2">
            {recent.map((f) => (
              <Link key={f.id} href="/dashboard/modules/school/feedback/mine" className="block bg-white rounded-xl border border-slate-200 p-4 hover:border-slate-300">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-slate-800">{f.subject}</p>
                  {f.is_resolved ? <span className="badge bg-emerald-50 text-emerald-700 border-emerald-200"><CheckCircle2 size={10} className="mr-1" />Resolved</span> : <span className="badge bg-amber-50 text-amber-700 border-amber-200">Open</span>}
                </div>
                <p className="text-xs text-slate-400 mt-0.5">{formatDate(f.created_at)}</p>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
