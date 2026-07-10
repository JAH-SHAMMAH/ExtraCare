"use client";

import { useState } from "react";
import Link from "next/link";
import { useFeedbackList, useResolveFeedback } from "@/hooks/useSchoolExperience";
import { useMineFilter } from "@/hooks/useMineFilter";
import { cn, formatDate } from "@/lib/utils";
import { MessageSquare, Loader2, CheckCircle2, User, EyeOff, Reply, ArrowLeft } from "lucide-react";
import type { FeedbackItem, FeedbackCategory } from "@/types";

const CATEGORY_LABEL: Record<string, string> = {
  general: "General", facilities: "Facilities", teaching: "Teaching",
  bullying: "Bullying", suggestion: "Suggestion", other: "Other",
};

export default function FeedbackManagerPage() {
  const { mine, setMine } = useMineFilter();
  const [resolvedFilter, setResolvedFilter] = useState<"" | "true" | "false">("");
  const [respondingTo, setRespondingTo] = useState<FeedbackItem | null>(null);
  const [response, setResponse] = useState("");

  const { data, isLoading } = useFeedbackList({
    mine: mine || undefined,
    resolved: resolvedFilter ? resolvedFilter === "true" : undefined,
    page: 1, page_size: 50,
  });
  const resolveFeedback = useResolveFeedback();
  const items = data?.items as FeedbackItem[] | undefined;

  const handleRespond = () => {
    if (!respondingTo) return;
    resolveFeedback.mutate(
      { id: respondingTo.id, admin_response: response, is_resolved: true },
      { onSuccess: () => { setRespondingTo(null); setResponse(""); } },
    );
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <Link href="/dashboard/modules/school/feedback" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Feedback</Link>
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Feedback</span><span>/</span><span className="text-brand-600 font-semibold">Feedback Manager</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Feedback Manager</h1>
        <p className="text-slate-500 text-sm mt-0.5">Review and respond to submitted feedback.</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4 flex flex-wrap items-center gap-3">
        <div className="flex bg-slate-100 rounded-lg p-0.5">
          <button onClick={() => setMine(false)} className={cn("px-3 py-1 text-xs font-semibold rounded-md", !mine ? "bg-white shadow" : "text-slate-600")}>All</button>
          <button onClick={() => setMine(true)} className={cn("px-3 py-1 text-xs font-semibold rounded-md", mine ? "bg-white shadow" : "text-slate-600")}>Mine</button>
        </div>
        <select value={resolvedFilter} onChange={(e) => setResolvedFilter(e.target.value as any)} className="input max-w-48">
          <option value="">All statuses</option>
          <option value="false">Open</option>
          <option value="true">Resolved</option>
        </select>
      </div>

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-28 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : items && items.length > 0 ? (
        <div className="space-y-3">
          {items.map((f) => (
            <div key={f.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-center gap-2 mb-1">
                <span className="badge bg-slate-50 text-slate-600 border-slate-200">{CATEGORY_LABEL[f.category] || f.category}</span>
                {f.is_resolved ? <span className="badge bg-emerald-50 text-emerald-700 border-emerald-200"><CheckCircle2 size={10} className="mr-1" /> Resolved</span> : <span className="badge bg-amber-50 text-amber-700 border-amber-200">Open</span>}
                {f.is_anonymous && <span className="badge bg-slate-50 text-slate-500 border-slate-200"><EyeOff size={10} className="mr-1" /> Anonymous</span>}
              </div>
              <h3 className="text-sm font-bold text-slate-900">{f.subject}</h3>
              <p className="text-xs text-slate-500 flex items-center gap-1 mt-0.5"><User size={11} />{f.is_anonymous ? "Anonymous" : f.submitted_by ? f.submitted_by.slice(0, 8) : "Unknown"}<span className="text-slate-300">·</span>{formatDate(f.created_at)}</p>
              <p className="text-sm text-slate-700 whitespace-pre-wrap mt-2">{f.message}</p>
              {f.admin_response && (
                <div className="mt-4 bg-slate-50 border-l-2 border-brand-500 rounded-r-lg p-3">
                  <p className="text-[10px] font-bold uppercase text-brand-600 mb-1">School Response</p>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">{f.admin_response}</p>
                </div>
              )}
              {!f.is_resolved && (
                <div className="mt-4 border-t border-slate-100 pt-3">
                  {respondingTo?.id === f.id ? (
                    <div className="space-y-2">
                      <textarea value={response} onChange={(e) => setResponse(e.target.value)} placeholder="Type your response…" className="input" rows={3} />
                      <div className="flex justify-end gap-2">
                        <button onClick={() => { setRespondingTo(null); setResponse(""); }} className="btn-secondary">Cancel</button>
                        <button onClick={handleRespond} disabled={!response.trim() || resolveFeedback.isPending} className="btn-primary gap-2">{resolveFeedback.isPending && <Loader2 size={14} className="animate-spin" />}Resolve &amp; Send</button>
                      </div>
                    </div>
                  ) : (
                    <button onClick={() => { setRespondingTo(f); setResponse(f.admin_response || ""); }} className="flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700"><Reply size={12} /> Respond</button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><MessageSquare size={36} className="mb-3 opacity-40" /><p className="font-semibold">No feedback yet</p></div>
      )}
    </div>
  );
}
