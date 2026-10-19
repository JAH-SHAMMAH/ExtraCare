"use client";

import { useMemo } from "react";
import { useSections, useTerms, useWeeks, useCurrentSession } from "@/hooks/usePlatform";
import { useClasses, useSubjects } from "@/hooks/useSchool";
import { useMyContexts } from "@/hooks/useMyContexts";

export interface LessonFilterValue { section: string; term: string; classId: string; weekId: string; day: string; subjectId: string }
export const EMPTY_LESSON_FILTER: LessonFilterValue = { section: "", term: "", classId: "", weekId: "", day: "", subjectId: "" };
export const DAY_OPTIONS = [
  { v: "0", l: "Monday" }, { v: "1", l: "Tuesday" }, { v: "2", l: "Wednesday" }, { v: "3", l: "Thursday" }, { v: "4", l: "Friday" },
];

/** Educare-style cascade: School → Term → Class → Week → Day → Subject.
 *  Week unlocks after a Term, Day after a Week, Subject after a Class. */
export function useLessonFilterData(v: LessonFilterValue) {
  const { data: sections = [] } = useSections();
  const { data: terms = [] } = useTerms();
  const { data: cur } = useCurrentSession();
  const { data: ctx } = useMyContexts();
  const { data: classData } = useClasses({ page_size: 300 } as any);
  const { data: subjectData } = useSubjects({ page_size: 300 } as any);
  const termName = (terms as any[]).find((t) => t.id === v.term)?.name as string | undefined;
  const { data: weeks = [] } = useWeeks(termName ? { academic_year: cur?.name || undefined, term: termName } : undefined);

  const teacherClasses: any[] = (ctx as any)?.as_teacher?.classes ?? [];
  const teacherSubjects: any[] = (ctx as any)?.as_teacher?.subjects ?? [];
  const allClasses: any[] = (classData as any)?.items || [];
  const allSubjects: any[] = (subjectData as any)?.items || [];
  const classes = useMemo(() => {
    const base = teacherClasses.length ? teacherClasses : allClasses;
    return base.filter((c: any) => {
      if (!v.section) return true;
      const full = allClasses.find((a) => a.id === c.id);
      return (full?.section_id ?? c.section_id) === v.section;
    });
  }, [teacherClasses, allClasses, v.section]);
  const subjects = teacherSubjects.length ? teacherSubjects : allSubjects;
  const week = (weeks as any[]).find((w) => w.id === v.weekId);
  return { sections: sections as any[], terms: terms as any[], classes, subjects, weeks: weeks as any[], week };
}

export function LessonFilters({ value, onChange, className = "" }: { value: LessonFilterValue; onChange: (v: LessonFilterValue) => void; className?: string }) {
  const d = useLessonFilterData(value);
  const set = (patch: Partial<LessonFilterValue>) => onChange({ ...value, ...patch });
  const Field = ({ label, children }: { label: string; children: React.ReactNode }) => (
    <div className="px-4 py-3 border-b border-slate-100 last:border-0 sm:border-0"><label className="label">{label}</label>{children}</div>
  );
  return (
    <div className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 ${className}`}>
      <Field label="Select School">
        <select aria-label="Select School" value={value.section} onChange={(e) => set({ section: e.target.value, classId: "", subjectId: "" })} className="input">
          <option value="">All schools</option>{d.sections.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </Field>
      <Field label="Term">
        <select aria-label="Term" value={value.term} onChange={(e) => set({ term: e.target.value, weekId: "", day: "" })} className="input">
          <option value="">Select Term…</option>{d.terms.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
      </Field>
      <Field label="Class">
        <select aria-label="Class" value={value.classId} onChange={(e) => set({ classId: e.target.value, subjectId: "" })} className="input">
          <option value="">Select Class…</option>{d.classes.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </Field>
      <Field label="Week">
        <select aria-label="Week" value={value.weekId} disabled={!value.term} onChange={(e) => set({ weekId: e.target.value, day: "" })} className="input disabled:bg-slate-100">
          <option value="">Select Week…</option>{d.weeks.map((w) => <option key={w.id} value={w.id}>{w.label || `Week ${w.week_number}`}</option>)}
        </select>
      </Field>
      <Field label="Day">
        <select aria-label="Day" value={value.day} disabled={!value.weekId} onChange={(e) => set({ day: e.target.value })} className="input disabled:bg-slate-100">
          <option value="">Select Day…</option>{DAY_OPTIONS.map((x) => <option key={x.v} value={x.v}>{x.l}</option>)}
        </select>
      </Field>
      <Field label="Subject">
        <select aria-label="Subject" value={value.subjectId} disabled={!value.classId} onChange={(e) => set({ subjectId: e.target.value })} className="input disabled:bg-slate-100">
          <option value="">Select Subject…</option>{d.subjects.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </Field>
    </div>
  );
}
