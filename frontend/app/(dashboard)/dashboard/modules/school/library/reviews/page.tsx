"use client";

import { useState } from "react";
import { Star, Loader2, Check, X, Trash2, MessageSquare } from "lucide-react";
import { useBookReviews, useModerateReview, useDeleteReview, type BookReviewRow } from "@/hooks/useSchool";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";

const FILTERS = [
  { id: "pending", label: "Pending" },
  { id: "approved", label: "Approved" },
  { id: "rejected", label: "Rejected" },
  { id: "", label: "All" },
];

export default function ManageReviewsPage() {
  const canWrite = useHasPermission("school:library:write");
  const [status, setStatus] = useState("pending");
  const { data: reviews = [], isLoading } = useBookReviews({ status: status || undefined });
  const moderate = useModerateReview();
  const del = useDeleteReview();

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span>Library</span><span>/</span><span className="text-brand-600 font-semibold">Manage Reviews</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2"><MessageSquare size={22} className="text-brand-600" /> Manage Reviews</h1>
        <p className="text-slate-500 text-sm mt-0.5">Moderate reader reviews. Only approved reviews are public.</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-1 mb-5 inline-flex">
        {FILTERS.map((f) => (
          <button key={f.id} onClick={() => setStatus(f.id)} className={cn("px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors", status === f.id ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100")}>{f.label}</button>
        ))}
      </div>

      {isLoading ? <div className="py-12 text-center"><Loader2 className="animate-spin mx-auto text-slate-400" /></div>
        : reviews.length === 0 ? <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-sm text-slate-400"><MessageSquare size={26} className="mx-auto mb-2 opacity-40" />No reviews here.</div>
          : (
            <div className="space-y-3">
              {reviews.map((r: BookReviewRow) => (
                <div key={r.id} className="bg-white rounded-xl border border-slate-200 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-bold text-slate-900">{r.book_title || "—"}</span>
                        <span className="flex items-center gap-0.5">{Array.from({ length: 5 }).map((_, i) => <Star key={i} size={12} className={i < r.rating ? "text-amber-400 fill-amber-400" : "text-slate-200"} />)}</span>
                        <span className={cn("badge text-[10px]", r.status === "approved" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : r.status === "rejected" ? "bg-rose-50 text-rose-700 border-rose-200" : "bg-amber-50 text-amber-700 border-amber-200")}>{r.status}</span>
                      </div>
                      {r.comment && <p className="text-sm text-slate-600">{r.comment}</p>}
                      <p className="text-xs text-slate-400 mt-1">{r.reviewer_name || "Anonymous"}</p>
                    </div>
                    {canWrite && (
                      <div className="flex items-center gap-1.5 shrink-0">
                        {r.status !== "approved" && <button onClick={() => moderate.mutate({ id: r.id, status: "approved" })} className="btn-secondary text-xs py-1 gap-1"><Check size={12} /> Approve</button>}
                        {r.status !== "rejected" && <button onClick={() => moderate.mutate({ id: r.id, status: "rejected" })} className="btn-secondary text-xs py-1 gap-1"><X size={12} /> Reject</button>}
                        <button onClick={() => del.mutate(r.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={13} /></button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
    </div>
  );
}
