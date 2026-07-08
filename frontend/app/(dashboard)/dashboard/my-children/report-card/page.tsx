"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useMyContexts, type ParentChild } from "@/hooks/useMyContexts";
import { useReportCard } from "@/hooks/useSchool";
import { getInitials } from "@/lib/utils";
import { GraduationCap, Loader2, ArrowLeft, FileText, ShieldCheck } from "lucide-react";

const TERMS = ["1st Term", "2nd Term", "3rd Term", "Term 1", "Term 2", "Term 3"];

/**
 * Parent report card — the child-scoped view a parent actually uses. Data is
 * ownership-scoped server-side (they can only read their own children), and the
 * report-card endpoint returns PUBLISHED grades only for parents, so nothing a
 * teacher hasn't finalised shows here.
 */
export default function ParentReportCardPage() {
  const { data, isLoading } = useMyContexts();
  const children: ParentChild[] = data?.as_parent?.children ?? [];

  const [childId, setChildId] = useState("");
  const [term, setTerm] = useState("1st Term");

  useEffect(() => {
    if (!childId && children.length) setChildId(children[0].id);
  }, [children, childId]);

  const child = children.find((c) => c.id === childId);
  const { data: card, isLoading: cardLoading } = useReportCard(childId, term);
  const grades: any[] = card?.grades ?? [];

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <Link href="/dashboard/my-children" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> My Children</Link>
      <div className="mb-6">
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Report Card</h1>
        <p className="text-slate-500 text-sm mt-0.5">Finalised results for your child. You&apos;ll only see grades the school has published.</p>
      </div>

      {isLoading ? (
        <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
      ) : children.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400">
          <GraduationCap size={34} className="mx-auto mb-3 opacity-40" />
          <p className="font-semibold text-slate-500">No children linked to your account</p>
          <p className="text-sm mt-1">Ask the school to link your child to your parent account.</p>
        </div>
      ) : (
        <>
          {/* Pickers */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6 flex flex-wrap items-end gap-4">
            {children.length > 1 && (
              <div className="min-w-[180px]">
                <label className="label">Child</label>
                <select value={childId} onChange={(e) => setChildId(e.target.value)} className="input">
                  {children.map((c) => (<option key={c.id} value={c.id}>{c.first_name} {c.last_name}</option>))}
                </select>
              </div>
            )}
            <div className="min-w-[140px]">
              <label className="label">Term</label>
              <select value={term} onChange={(e) => setTerm(e.target.value)} className="input">
                {TERMS.map((t) => (<option key={t} value={t}>{t}</option>))}
              </select>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6">
            {child && (
              <div className="flex items-center gap-3 pb-4 mb-4 border-b border-slate-100">
                <div className="w-11 h-11 rounded-xl bg-brand-600/10 text-brand-700 flex items-center justify-center text-sm font-bold">{getInitials(`${child.first_name} ${child.last_name}`)}</div>
                <div>
                  <h2 className="text-base font-bold text-slate-900">{child.first_name} {child.last_name}</h2>
                  <p className="text-xs text-slate-400">{child.class_name || "No class"} · {term}</p>
                </div>
              </div>
            )}

            {cardLoading ? (
              <div className="py-10 text-center"><Loader2 size={20} className="animate-spin text-slate-400 mx-auto" /></div>
            ) : grades.length === 0 ? (
              <div className="py-12 text-center text-slate-400">
                <FileText size={30} className="mx-auto mb-2 opacity-40" />
                <p className="font-semibold text-slate-500">No published results for {term} yet</p>
                <p className="text-sm mt-1">Results appear here once the school finalises and publishes them.</p>
              </div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead><tr className="border-b border-slate-100">{["Subject", "Score", "Grade"].map((h) => (<th key={h} className="pb-2 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>))}</tr></thead>
                    <tbody className="divide-y divide-slate-50">
                      {grades.map((g, i) => (
                        <tr key={i}>
                          <td className="py-2.5 text-sm font-medium text-slate-800">{g.subject_name || "—"}</td>
                          <td className="py-2.5 text-sm text-slate-600 tabular-nums">{g.score ?? "—"}{g.max_score ? ` / ${g.max_score}` : ""}</td>
                          <td className="py-2.5 text-sm font-bold text-slate-700">{g.grade_letter || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-100">
                  <span className="inline-flex items-center gap-1.5 text-[11px] text-emerald-600"><ShieldCheck size={13} /> Published results</span>
                  <div className="text-right">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Average</p>
                    <p className="text-xl font-black text-slate-900 tabular-nums">{card?.average?.toFixed?.(1) ?? "—"}</p>
                  </div>
                </div>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}
