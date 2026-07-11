"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useMyContexts, type ParentChild } from "@/hooks/useMyContexts";
import { useStudentDailyReportsForChild } from "@/hooks/useFeedbackExtras";
import { getInitials, formatDate } from "@/lib/utils";
import { GraduationCap, Loader2, ArrowLeft, Smile } from "lucide-react";

/**
 * Parent daily-report view — a child's day-to-day mood/academic/behaviour notes.
 * Ownership-scoped server-side (a parent reads only their own children), mirroring
 * how the report card is exposed.
 */
export default function ParentDailyReportsPage() {
  const { data, isLoading } = useMyContexts();
  const children: ParentChild[] = data?.as_parent?.children ?? [];
  const [childId, setChildId] = useState("");
  useEffect(() => { if (!childId && children.length) setChildId(children[0].id); }, [children, childId]);

  const child = children.find((c) => c.id === childId);
  const { data: reports, isLoading: loadingReports } = useStudentDailyReportsForChild(childId || null);
  const items = reports?.items ?? [];

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <Link href="/dashboard/my-children" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> My Children</Link>
      <div className="mb-6">
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Daily Reports</h1>
        <p className="text-slate-500 text-sm mt-0.5">Your child’s daily mood, academic and behaviour notes from staff.</p>
      </div>

      {isLoading ? (
        <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
      ) : children.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400">
          <GraduationCap size={34} className="mx-auto mb-3 opacity-40" />
          <p className="font-semibold text-slate-500">No children linked to your account</p>
        </div>
      ) : (
        <>
          {children.length > 1 && (
            <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6 max-w-xs">
              <label className="label">Child</label>
              <select value={childId} onChange={(e) => setChildId(e.target.value)} className="input">
                {children.map((c) => (<option key={c.id} value={c.id}>{c.first_name} {c.last_name}</option>))}
              </select>
            </div>
          )}
          {child && (
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-brand-600/10 text-brand-700 flex items-center justify-center text-sm font-bold">{getInitials(`${child.first_name} ${child.last_name}`)}</div>
              <div><h2 className="text-sm font-bold text-slate-900">{child.first_name} {child.last_name}</h2><p className="text-xs text-slate-400">{child.class_name || "No class"}</p></div>
            </div>
          )}

          {loadingReports ? (
            <div className="py-10 text-center"><Loader2 size={20} className="animate-spin text-slate-400 mx-auto" /></div>
          ) : items.length === 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 py-12 text-center text-slate-400">
              <Smile size={30} className="mx-auto mb-2 opacity-40" />
              <p className="font-semibold text-slate-500">No daily reports yet</p>
            </div>
          ) : (
            <div className="space-y-3">
              {items.map((r) => (
                <div key={r.id} className="bg-white rounded-xl border border-slate-200 p-5">
                  <p className="text-sm font-bold text-slate-900">{formatDate(r.report_date)}{r.mood ? <span className="capitalize font-normal text-slate-400"> · {r.mood}</span> : null}</p>
                  {r.academic && <p className="text-xs text-slate-500 mt-2"><span className="font-semibold text-slate-700">Academic:</span> {r.academic}</p>}
                  {r.behaviour && <p className="text-xs text-slate-500 mt-1"><span className="font-semibold text-slate-700">Behaviour:</span> {r.behaviour}</p>}
                  {r.notes && <p className="text-xs text-slate-500 mt-1"><span className="font-semibold text-slate-700">Notes:</span> {r.notes}</p>}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
