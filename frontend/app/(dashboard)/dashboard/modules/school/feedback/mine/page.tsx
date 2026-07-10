"use client";

import Link from "next/link";
import { useFeedbackList } from "@/hooks/useSchoolExperience";
import { formatDate } from "@/lib/utils";
import { MessageSquare, CheckCircle2, EyeOff, ArrowLeft } from "lucide-react";
import type { FeedbackItem } from "@/types";

const CATEGORY_LABEL: Record<string, string> = {
  general: "General", facilities: "Facilities", teaching: "Teaching",
  bullying: "Bullying", suggestion: "Suggestion", other: "Other",
};

export default function MyFeedbackPage() {
  const { data, isLoading } = useFeedbackList({ mine: true, page: 1, page_size: 50 });
  const items = (data?.items as FeedbackItem[] | undefined) || [];

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <Link href="/dashboard/modules/school/feedback" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Feedback</Link>
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Feedback</span><span>/</span><span className="text-brand-600 font-semibold">My Feedback</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">My Feedback</h1>
        <p className="text-slate-500 text-sm mt-0.5">Your submitted feedback and the school’s responses.</p>
      </div>

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-24 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : items.length > 0 ? (
        <div className="space-y-3">
          {items.map((f) => (
            <div key={f.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-center gap-2 mb-1">
                <span className="badge bg-slate-50 text-slate-600 border-slate-200">{CATEGORY_LABEL[f.category] || f.category}</span>
                {f.is_resolved ? <span className="badge bg-emerald-50 text-emerald-700 border-emerald-200"><CheckCircle2 size={10} className="mr-1" />Resolved</span> : <span className="badge bg-amber-50 text-amber-700 border-amber-200">Open</span>}
                {f.is_anonymous && <span className="badge bg-slate-50 text-slate-500 border-slate-200"><EyeOff size={10} className="mr-1" />Anonymous</span>}
              </div>
              <h3 className="text-sm font-bold text-slate-900">{f.subject}</h3>
              <p className="text-xs text-slate-400 mt-0.5">{formatDate(f.created_at)}</p>
              <p className="text-sm text-slate-700 whitespace-pre-wrap mt-2">{f.message}</p>
              {f.admin_response && (
                <div className="mt-4 bg-slate-50 border-l-2 border-brand-500 rounded-r-lg p-3">
                  <p className="text-[10px] font-bold uppercase text-brand-600 mb-1">School Response</p>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">{f.admin_response}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><MessageSquare size={36} className="mb-3 opacity-40" /><p className="font-semibold">You haven’t submitted feedback yet</p></div>
      )}
    </div>
  );
}
