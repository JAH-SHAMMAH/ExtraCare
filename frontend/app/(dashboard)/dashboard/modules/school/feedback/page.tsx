"use client";

import { useState } from "react";
import {
  useFeedbackList,
  useSubmitFeedback,
  useResolveFeedback,
} from "@/hooks/useSchoolExperience";
import { useMineFilter } from "@/hooks/useMineFilter";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import {
  MessageSquare, Plus, X, Loader2, CheckCircle2, User, EyeOff, Reply,
} from "lucide-react";
import type { FeedbackItem, FeedbackCategory } from "@/types";

const CATEGORY_LABEL: Record<FeedbackCategory, string> = {
  general: "General",
  facilities: "Facilities",
  teaching: "Teaching",
  bullying: "Bullying",
  suggestion: "Suggestion",
  other: "Other",
};

export default function FeedbackPage() {
  const canResolve = useHasPermission("school:write");
  const { mine: urlMine, setMine } = useMineFilter();
  // Non-resolvers (students) are always scoped to their own submissions regardless of URL.
  const mine = canResolve ? urlMine : true;
  const [resolvedFilter, setResolvedFilter] = useState<"" | "true" | "false">("");
  const [showForm, setShowForm] = useState(false);
  const [respondingTo, setRespondingTo] = useState<FeedbackItem | null>(null);
  const [response, setResponse] = useState("");

  const { data, isLoading } = useFeedbackList({
    mine: mine || undefined,
    resolved: resolvedFilter ? resolvedFilter === "true" : undefined,
    page: 1,
    page_size: 50,
  });

  const submitFeedback = useSubmitFeedback();
  const resolveFeedback = useResolveFeedback();

  const [form, setForm] = useState({
    subject: "",
    message: "",
    category: "general" as FeedbackCategory,
    is_anonymous: false,
    student_id: "",
  });

  const resetForm = () => {
    setForm({ subject: "", message: "", category: "general", is_anonymous: false, student_id: "" });
    setShowForm(false);
  };

  const handleSubmit = () => {
    submitFeedback.mutate(
      { ...form, student_id: form.student_id || null },
      { onSuccess: resetForm },
    );
  };

  const handleRespond = () => {
    if (!respondingTo) return;
    resolveFeedback.mutate(
      { id: respondingTo.id, admin_response: response, is_resolved: true },
      {
        onSuccess: () => {
          setRespondingTo(null);
          setResponse("");
        },
      },
    );
  };

  const items = data?.items as FeedbackItem[] | undefined;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Education</span><span>/</span>
            <span className="text-brand-600 font-semibold">Feedback</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Student Feedback</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Share concerns, suggestions, and get responses from the school.
          </p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary gap-2">
          <Plus size={15} />
          Submit Feedback
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: "Total", value: data?.total ?? "—" },
          { label: "Resolved", value: items?.filter((f) => f.is_resolved).length ?? 0 },
          { label: "Open", value: items?.filter((f) => !f.is_resolved).length ?? 0 },
          { label: "Anonymous", value: items?.filter((f) => f.is_anonymous).length ?? 0 },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">{label}</p>
            <p className="text-xl font-black text-slate-900">{value}</p>
          </div>
        ))}
      </div>

      {showForm && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">New Feedback</h2>
            <button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="label">Subject *</label>
              <input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Category *</label>
              <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value as FeedbackCategory })} className="input">
                {(Object.keys(CATEGORY_LABEL) as FeedbackCategory[]).map((k) => (
                  <option key={k} value={k}>{CATEGORY_LABEL[k]}</option>
                ))}
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
            <div className="md:col-span-2 flex items-center gap-2">
              <input
                id="anon"
                type="checkbox"
                checked={form.is_anonymous}
                onChange={(e) => setForm({ ...form, is_anonymous: e.target.checked })}
              />
              <label htmlFor="anon" className="text-xs font-medium text-slate-700">Submit anonymously</label>
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={resetForm} className="btn-secondary">Cancel</button>
            <button
              onClick={handleSubmit}
              disabled={submitFeedback.isPending || !form.subject || !form.message}
              className="btn-primary gap-2"
            >
              {submitFeedback.isPending && <Loader2 size={15} className="animate-spin" />}
              Submit
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4 flex flex-wrap items-center gap-3">
        {canResolve && (
          <div className="flex bg-slate-100 rounded-lg p-0.5">
            <button
              onClick={() => setMine(false)}
              className={cn("px-3 py-1 text-xs font-semibold rounded-md", !mine ? "bg-white shadow" : "text-slate-600")}
            >
              All
            </button>
            <button
              onClick={() => setMine(true)}
              className={cn("px-3 py-1 text-xs font-semibold rounded-md", mine ? "bg-white shadow" : "text-slate-600")}
            >
              Mine
            </button>
          </div>
        )}
        <select value={resolvedFilter} onChange={(e) => setResolvedFilter(e.target.value as any)} className="input max-w-48">
          <option value="">All statuses</option>
          <option value="false">Open</option>
          <option value="true">Resolved</option>
        </select>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-28 bg-slate-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : items && items.length > 0 ? (
        <div className="space-y-3">
          {items.map((f) => (
            <div key={f.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-start justify-between gap-4 mb-2">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="badge bg-slate-50 text-slate-600 border-slate-200">
                      {CATEGORY_LABEL[f.category] || f.category}
                    </span>
                    {f.is_resolved ? (
                      <span className="badge bg-emerald-50 text-emerald-700 border-emerald-200">
                        <CheckCircle2 size={10} className="mr-1" /> Resolved
                      </span>
                    ) : (
                      <span className="badge bg-amber-50 text-amber-700 border-amber-200">Open</span>
                    )}
                    {f.is_anonymous && (
                      <span className="badge bg-slate-50 text-slate-500 border-slate-200">
                        <EyeOff size={10} className="mr-1" /> Anonymous
                      </span>
                    )}
                  </div>
                  <h3 className="text-sm font-bold text-slate-900">{f.subject}</h3>
                  <p className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
                    <User size={11} />
                    {f.is_anonymous ? "Anonymous" : f.submitted_by ? f.submitted_by.slice(0, 8) : "Unknown"}
                    <span className="text-slate-300">·</span>
                    {formatDate(f.created_at)}
                  </p>
                </div>
              </div>
              <p className="text-sm text-slate-700 whitespace-pre-wrap">{f.message}</p>

              {f.admin_response && (
                <div className="mt-4 bg-slate-50 border-l-2 border-brand-500 rounded-r-lg p-3">
                  <p className="text-[10px] font-bold uppercase text-brand-600 mb-1">School Response</p>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">{f.admin_response}</p>
                </div>
              )}

              {canResolve && !f.is_resolved && (
                <div className="mt-4 border-t border-slate-100 pt-3">
                  {respondingTo?.id === f.id ? (
                    <div className="space-y-2">
                      <textarea
                        value={response}
                        onChange={(e) => setResponse(e.target.value)}
                        placeholder="Type your response…"
                        className="input"
                        rows={3}
                      />
                      <div className="flex justify-end gap-2">
                        <button onClick={() => { setRespondingTo(null); setResponse(""); }} className="btn-secondary">Cancel</button>
                        <button
                          onClick={handleRespond}
                          disabled={!response.trim() || resolveFeedback.isPending}
                          className="btn-primary gap-2"
                        >
                          {resolveFeedback.isPending && <Loader2 size={14} className="animate-spin" />}
                          Resolve &amp; Send
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={() => { setRespondingTo(f); setResponse(f.admin_response || ""); }}
                      className="flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700"
                    >
                      <Reply size={12} />
                      Respond
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400">
          <MessageSquare size={36} className="mb-3 opacity-40" />
          <p className="font-semibold">No feedback yet</p>
        </div>
      )}
    </div>
  );
}
