"use client";

import Link from "next/link";
import { useAssessmentCriteria, useSaveAssessmentCriterion } from "@/hooks/usePeople";
import { useHrList } from "@/hooks/useHrAdmin";
import { Network, Loader2, SlidersHorizontal } from "lucide-react";
import type { AssessmentCriterion } from "@/types";

export default function CompetencyMappingsPage() {
  const { data, isLoading } = useAssessmentCriteria();
  const { data: competencies } = useHrList("competency");
  const criteria: AssessmentCriterion[] = data?.items || [];
  const compOptions = (competencies ?? []).filter((c: any) => c.is_active);

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><Link href="/dashboard/hrm/performance" className="hover:text-brand-600">Performance</Link><span>/</span><span className="text-brand-600 font-semibold">Competency Mappings</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Competency Mappings</h1>
        <p className="text-slate-500 text-sm mt-0.5">Map each appraisal criterion to the competency it assesses. Manage the list under <Link href="/dashboard/hrm/admin/competencies" className="text-brand-600 hover:underline">Competency List</Link>.</p>
      </div>

      {isLoading ? (
        <div className="py-16 text-center"><Loader2 size={22} className="animate-spin text-slate-400 mx-auto" /></div>
      ) : criteria.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400 text-sm">
          <SlidersHorizontal size={30} className="mx-auto mb-2 opacity-50" />No appraisal criteria yet.
          <p className="mt-2"><Link href="/dashboard/hrm/performance/configuration" className="text-brand-600 hover:underline">Add criteria</Link> first.</p>
        </div>
      ) : compOptions.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400 text-sm">
          <Network size={30} className="mx-auto mb-2 opacity-50" />No competencies defined yet.
          <p className="mt-2"><Link href="/dashboard/hrm/admin/competencies" className="text-brand-600 hover:underline">Add competencies</Link> to map them here.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {criteria.map((c) => <MapRow key={c.id} criterion={c} options={compOptions} />)}
        </div>
      )}
    </div>
  );
}

function MapRow({ criterion, options }: { criterion: AssessmentCriterion; options: any[] }) {
  const save = useSaveAssessmentCriterion();
  return (
    <div className="flex items-center gap-3 px-5 py-3.5">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-slate-800 truncate">{criterion.name}</p>
        {criterion.category && <p className="text-xs text-slate-400">{criterion.category}</p>}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <select
          value={criterion.competency || ""}
          onChange={(e) => save.mutate({ id: criterion.id, data: { competency: e.target.value || null } })}
          disabled={save.isPending}
          className="input py-1.5 text-sm w-52"
        >
          <option value="">— Unmapped —</option>
          {options.map((o) => <option key={o.id} value={o.name}>{o.name}</option>)}
        </select>
        {save.isPending && <Loader2 size={14} className="animate-spin text-slate-400" />}
      </div>
    </div>
  );
}
