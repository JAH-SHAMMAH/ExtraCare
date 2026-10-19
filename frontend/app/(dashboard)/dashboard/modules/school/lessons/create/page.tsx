"use client";

import { useState } from "react";
import Link from "next/link";
import { NotebookPen } from "lucide-react";
import { LessonFilters, useLessonFilterData, EMPTY_LESSON_FILTER, type LessonFilterValue } from "@/components/lessons/LessonFilters";
import { PlanDrawer, type DrawerState } from "@/components/lessons/PlanDrawer";

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export default function CreateLessonPlanPage() {
  const [flt, setFlt] = useState<LessonFilterValue>(EMPTY_LESSON_FILTER);
  const [drawer, setDrawer] = useState<DrawerState>({ mode: "closed" });
  const d = useLessonFilterData(flt);

  const ready = !!(flt.classId && flt.subjectId && flt.weekId && flt.day);
  const start = () => {
    // The lesson date is the chosen weekday of the chosen week.
    const base = new Date((d.week?.start_date || "") + "T00:00:00");
    const dow = (base.getDay() + 6) % 7; // Mon=0
    base.setDate(base.getDate() - dow + Number(flt.day));
    setDrawer({ mode: "create", prefillDate: iso(base), prefillClassId: flt.classId, prefillSubjectId: flt.subjectId });
  };

  return (
    <div className="p-4 sm:p-8 max-w-5xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-500 mb-3 font-semibold"><span>Home</span><span>•</span><span>Lesson Planner</span><span>•</span><span className="text-slate-900">Create lesson Plan</span></nav>
      <div className="rounded-t-xl bg-emerald-800 text-white px-5 py-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold flex items-center gap-2"><NotebookPen size={20} /> Create Lesson Plan</h1>
        <Link href="/dashboard/modules/school/lessons" className="px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white text-sm font-semibold">Manage Lesson Plan</Link>
      </div>
      <div className="bg-white border border-slate-200 rounded-b-xl">
        <LessonFilters value={flt} onChange={setFlt} />
        <div className="px-4 py-4 border-t border-slate-100 flex items-center justify-between gap-3 flex-wrap">
          <p className="text-xs text-slate-500">{ready ? "Group chosen — start writing the plan." : "Choose a term, class, week, day and subject to begin."}</p>
          <button onClick={start} disabled={!ready} className="btn-primary disabled:opacity-50">Start Lesson Plan</button>
        </div>
      </div>
      {drawer.mode !== "closed" && <PlanDrawer state={drawer} onClose={() => setDrawer({ mode: "closed" })} />}
    </div>
  );
}
