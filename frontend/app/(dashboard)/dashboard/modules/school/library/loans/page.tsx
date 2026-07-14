"use client";

import { LoansTab } from "../_components";

/** Library — Issue / Return Book. The loan register with active/overdue/returned. */
export default function IssueReturnPage() {
  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span>Library</span><span>/</span><span className="text-brand-600 font-semibold">Issue / Return Book</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Issue / Return Book</h1>
        <p className="text-slate-500 text-sm mt-0.5">The loan register. Issue from the catalogue; return here.</p>
      </div>
      <LoansTab />
    </div>
  );
}
