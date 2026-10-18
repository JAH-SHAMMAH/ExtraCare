"use client";

import { useState, useEffect } from "react";
import { FileText, Loader2, Printer, ShieldCheck } from "lucide-react";
import { useTerms, useSubTerms, useReportCard } from "@/hooks/usePlatform";
import { defaultSubTermId } from "@/lib/reportEntry";
import { Card } from "@/components/reports/ReportCardPrint";

export interface ViewerPerson { id: string; name: string; first_name?: string }

/**
 * The designed report card (Nursery / Junior / Secondary) for a pupil or a parent's
 * children, with term + report pickers and Print / Save as PDF. One component for
 * every non-staff reader, so the pupil and the parent can never see different
 * layouts. The API only releases the card once the class's report is published.
 */
export function ReportCardViewer({ people }: { people: ViewerPerson[] }) {
  const { data: terms = [] } = useTerms();
  const { data: subTerms = [] } = useSubTerms();
  const [personId, setPersonId] = useState("");
  const [termId, setTermId] = useState("");
  const [subTermId, setSubTermId] = useState("");

  useEffect(() => { if (!personId && people.length) setPersonId(people[0].id); }, [people, personId]);
  useEffect(() => {
    if (!termId && terms.length) setTermId((terms.find((t: any) => t.is_active) ?? terms[0]).id);
  }, [terms, termId]);
  useEffect(() => {
    if (!subTermId && subTerms.length) setSubTermId(defaultSubTermId(subTerms));
  }, [subTerms, subTermId]);

  const person = people.find((p) => p.id === personId);
  const { data: card, isLoading, error } = useReportCard({ student_id: personId, term_id: termId, sub_term_id: subTermId });
  const num = (v: any) => (v == null ? "–" : Number(v));
  const ready = !!card && !(card as any).not_configured;
  const detail: string | undefined = (error as any)?.response?.data?.detail;

  return (
    <>
      <style>{`@media print {
        body * { visibility: hidden !important; }
        #own-report, #own-report * { visibility: visible !important; }
        #own-report { position: absolute; left: 0; top: 0; width: 100%; }
      }`}</style>
      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6 flex flex-wrap items-end gap-4 no-print">
        {people.length > 1 && (
          <div className="min-w-[180px]">
            <label className="label">Child</label>
            <select value={personId} onChange={(e) => setPersonId(e.target.value)} className="input">
              {people.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
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

      {isLoading ? (
        <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
      ) : !ready ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 px-6 text-center text-slate-400">
          <FileText size={30} className="mx-auto mb-2 opacity-40" />
          <p className="font-semibold text-slate-500">
            {detail?.includes("not been published") ? `${person?.first_name ?? "This"} report isn't published yet` : "No report available for this term yet"}
          </p>
          <p className="text-sm mt-1">{detail ?? "Check back once the school has published it."}</p>
        </div>
      ) : (
        <>
          <div id="own-report" className="bg-white rounded-xl border border-slate-300 p-4 sm:p-6 text-slate-900 overflow-x-auto [print-color-adjust:exact] [-webkit-print-color-adjust:exact]">
            <Card card={card} num={num} />
          </div>
          <p className="inline-flex items-center gap-1.5 text-[11px] text-emerald-600 mt-3 no-print"><ShieldCheck size={13} /> Published by the school</p>
        </>
      )}
    </>
  );
}
