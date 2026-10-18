"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { GraduationCap, Loader2, ArrowLeft, FileText, ShieldCheck, Printer } from "lucide-react";
import { useTerms, useSubTerms, useReportCard } from "@/hooks/usePlatform";
import { useMyContexts, type ParentChild } from "@/hooks/useMyContexts";
import { defaultSubTermId } from "@/lib/reportEntry";
import { Card } from "@/components/reports/ReportCardPrint";

/**
 * A parent's view of their child's report card — the SAME designed report the
 * school prints (Nursery / Junior / Secondary layouts), not a plain table.
 * The API only returns it once the class's report is published, and only for the
 * parent's own children.
 */
export default function ParentReportCardPage() {
  const { data, isLoading } = useMyContexts();
  const children: ParentChild[] = data?.as_parent?.children ?? [];
  const { data: terms = [] } = useTerms();
  const { data: subTerms = [] } = useSubTerms();

  const [childId, setChildId] = useState("");
  const [termId, setTermId] = useState("");
  const [subTermId, setSubTermId] = useState("");

  useEffect(() => {
    if (!childId && children.length) setChildId(children[0].id);
  }, [children, childId]);
  // Start on the school's current term and Full-Term; the parent can change both.
  useEffect(() => {
    if (!termId && terms.length) setTermId((terms.find((t: any) => t.is_active) ?? terms[0]).id);
  }, [terms, termId]);
  useEffect(() => {
    if (!subTermId && subTerms.length) setSubTermId(defaultSubTermId(subTerms));
  }, [subTerms, subTermId]);

  const child = children.find((c) => c.id === childId);
  const { data: card, isLoading: cardLoading, error } = useReportCard({ student_id: childId, term_id: termId, sub_term_id: subTermId });
  const num = (v: any) => (v == null ? "–" : Number(v));
  const ready = !!card && !(card as any).not_configured;
  const detail: string | undefined = (error as any)?.response?.data?.detail;

  return (
    <div className="p-4 sm:p-8 max-w-4xl mx-auto">
      <style>{`@media print {
        body * { visibility: hidden !important; }
        #parent-report, #parent-report * { visibility: visible !important; }
        #parent-report { position: absolute; left: 0; top: 0; width: 100%; }
      }`}</style>
      <Link href="/dashboard/my-children" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4 no-print"><ArrowLeft size={13} /> My Children</Link>
      <div className="mb-6 no-print">
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Report Card</h1>
        <p className="text-slate-500 text-sm mt-0.5">Your child&apos;s finalised report. It appears here once the school publishes it.</p>
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
          <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6 flex flex-wrap items-end gap-4 no-print">
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
              <select value={termId} onChange={(e) => setTermId(e.target.value)} className="input">
                {terms.map((t: any) => (<option key={t.id} value={t.id}>{t.name}</option>))}
              </select>
            </div>
            <div className="min-w-[140px]">
              <label className="label">Report</label>
              <select value={subTermId} onChange={(e) => setSubTermId(e.target.value)} className="input">
                {subTerms.map((s: any) => (<option key={s.id} value={s.id}>{s.alias || s.name}</option>))}
              </select>
            </div>
            {ready && (
              <button onClick={() => window.print()} className="btn-primary gap-2 ml-auto"><Printer size={15} /> Print / Save as PDF</button>
            )}
          </div>

          {cardLoading ? (
            <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
          ) : !ready ? (
            <div className="bg-white rounded-xl border border-slate-200 py-14 px-6 text-center text-slate-400">
              <FileText size={30} className="mx-auto mb-2 opacity-40" />
              <p className="font-semibold text-slate-500">
                {detail?.includes("not been published") ? `${child?.first_name ?? "This"} report isn't published yet` : "No report available for this term yet"}
              </p>
              <p className="text-sm mt-1">{detail ?? "Check back once the school has published it."}</p>
            </div>
          ) : (
            <>
              <div id="parent-report" className="bg-white rounded-xl border border-slate-300 p-4 sm:p-6 text-slate-900 overflow-x-auto [print-color-adjust:exact] [-webkit-print-color-adjust:exact]">
                <Card card={card} num={num} />
              </div>
              <p className="inline-flex items-center gap-1.5 text-[11px] text-emerald-600 mt-3 no-print"><ShieldCheck size={13} /> Published by the school</p>
            </>
          )}
        </>
      )}
    </div>
  );
}
