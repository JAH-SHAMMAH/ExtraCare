"use client";

import Link from "next/link";
import { HR_ADMIN_LISTS } from "@/components/hrm/hrNav";
import { useHrCatalog } from "@/hooks/useHrAdmin";
import { ArrowRight, Settings2 } from "lucide-react";

/**
 * HR Admin landing — the seven Phase-1 managed lists ('Admin › Job' cluster) as
 * cards with live item counts. Reached from the list-page breadcrumb or directly;
 * the dashboard Quick Link lands on /section?open=admin (which pre-expands the tab
 * dropdown) and links to the same list pages.
 */
export default function HrAdminPage() {
  const { data: catalog } = useHrCatalog();
  const countFor = (type: string) => catalog?.find((c) => c.list_type === type)?.count;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><span className="text-brand-600 font-semibold">Admin</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2"><Settings2 className="text-brand-600" size={22} /> Admin</h1>
        <p className="text-slate-500 text-sm mt-0.5">Managed lists that power the rest of HR — job titles, grades, shifts and more.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {HR_ADMIN_LISTS.filter((l) => !l.section).map((l) => {
          const count = countFor(l.type);
          return (
            <Link key={l.slug} href={`/dashboard/hrm/admin/${l.slug}`}
              className="group bg-white rounded-xl border border-slate-200 p-4 hover:shadow-md hover:border-brand-300 transition-all flex flex-col">
              <div className="flex items-start justify-between">
                <span className="text-sm font-bold text-slate-800 group-hover:text-brand-700">{l.label}</span>
                <ArrowRight size={15} className="text-slate-300 group-hover:text-brand-500 shrink-0 mt-0.5" />
              </div>
              <p className="text-xs text-slate-400 mt-1 flex-1">{l.hint}</p>
              <span className="text-[11px] font-semibold text-slate-500 mt-3">
                {count === undefined ? "—" : `${count} ${count === 1 ? "entry" : "entries"}`}
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
