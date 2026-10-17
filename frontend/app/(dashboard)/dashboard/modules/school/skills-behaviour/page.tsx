"use client";

import { useEffect, useState } from "react";
import { useClasses } from "@/hooks/useSchool";
import { useTerms } from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { DomainRatingsEntry } from "@/components/reports/DomainRatingsEntry";
import { ListChecks } from "lucide-react";

/**
 * Where a CLASS TEACHER rates her pupils' skills and behaviour (Secondary and Junior,
 * scored on the school's 1-5 key) or writes each Nursery pupil's learning-goal
 * achievements. Report Entry is the administrators' marks desk; teachers never reach
 * it, so this has its own page, gated like Make Report. The API still limits it to the
 * teacher's own class.
 */
export default function SkillsBehaviourPage() {
  const canWrite = useHasPermission("school:reports:write");
  const classesData: any = useClasses({ page_size: 200 }).data;
  const classes: any[] = classesData?.items ?? classesData ?? [];
  const { data: terms = [] } = useTerms();
  const [classId, setClassId] = useState("");
  const [termId, setTermId] = useState("");

  // Start on the school's current term so the teacher only has to pick her class.
  useEffect(() => {
    if (termId || !(terms as any[]).length) return;
    const cur = (terms as any[]).find((t) => t.is_active) ?? (terms as any[])[0];
    if (cur) setTermId(cur.id);
  }, [terms, termId]);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>School Report</span><span>/</span><span className="text-brand-600 font-semibold">Skills &amp; Behaviour</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2"><ListChecks size={22} className="text-brand-600" /> Skills &amp; Behaviour</h1>
      <p className="text-slate-500 text-sm mb-5">Rate each pupil on the skills and behaviour printed on their report card. Nursery classes write each pupil&apos;s learning-goal achievements and add sample pictures instead.</p>

      <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3 mb-5">
        <div><label className="label">Class</label><select value={classId} onChange={(e) => setClassId(e.target.value)} className="input"><option value="">— Select —</option>{classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
        <div><label className="label">Term</label><select value={termId} onChange={(e) => setTermId(e.target.value)} className="input"><option value="">— Select —</option>{(terms as any[]).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
      </div>

      {classId && termId ? (
        <DomainRatingsEntry classId={classId} termId={termId} canWrite={canWrite} />
      ) : (
        <div className="bg-white rounded-xl border border-dashed border-slate-200 py-16 text-center text-slate-400"><ListChecks size={30} className="mx-auto mb-3 opacity-40" /><p className="text-sm">Choose your class and the term to start.</p></div>
      )}
    </div>
  );
}
