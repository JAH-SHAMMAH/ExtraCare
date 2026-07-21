"use client";

import Link from "next/link";
import { HR_ADMIN_LISTS } from "@/components/hrm/hrNav";
import { useHrCatalog } from "@/hooks/useHrAdmin";
import { ArrowRight, Settings2 } from "lucide-react";

// The recruitment config lists (Application Sources, Interview Stages) — managed
// lists on the generic infra, surfaced here under the Recruitment tab.
const LISTS = HR_ADMIN_LISTS.filter((l) => l.section?.label === "Recruitment");

export default function RecruitmentConfigPage() {
  const { data: catalog } = useHrCatalog();
  const countFor = (type: string) => catalog?.find((c) => c.list_type === type)?.count;

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><Link href="/dashboard/hrm/recruitment" className="hover:text-brand-600">Recruitment</Link><span>/</span><span className="text-brand-600 font-semibold">Configuration</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2"><Settings2 className="text-brand-600" size={22} /> Recruitment Configuration</h1>
        <p className="text-slate-500 text-sm mt-0.5">The lists that power your hiring pipeline.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {LISTS.map((l) => {
          const count = countFor(l.type);
          return (
            <Link key={l.slug} href={`/dashboard/hrm/admin/${l.slug}`} className="group bg-white rounded-xl border border-slate-200 p-4 hover:shadow-md hover:border-brand-300 transition-all flex flex-col">
              <div className="flex items-start justify-between">
                <span className="text-sm font-bold text-slate-800 group-hover:text-brand-700">{l.label}</span>
                <ArrowRight size={15} className="text-slate-300 group-hover:text-brand-500 shrink-0 mt-0.5" />
              </div>
              <p className="text-xs text-slate-400 mt-1 flex-1">{l.hint}</p>
              <span className="text-[11px] font-semibold text-slate-500 mt-3">{count === undefined ? "—" : `${count} ${count === 1 ? "entry" : "entries"}`}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
