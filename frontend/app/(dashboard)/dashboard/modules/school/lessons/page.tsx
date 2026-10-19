"use client";

import { useEffect, useMemo, useState, useRef } from "react";
import NextLink from "next/link";
import { PlanDrawer, type DrawerState } from "@/components/lessons/PlanDrawer";
import { LessonFilters, useLessonFilterData, EMPTY_LESSON_FILTER, type LessonFilterValue } from "@/components/lessons/LessonFilters";
import DOMPurify from "dompurify";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import TextAlign from "@tiptap/extension-text-align";
import {
  NotebookPen, Plus, ChevronLeft, ChevronRight, Calendar, X, Loader2, CheckCircle2,
  Pencil, Trash2, BookOpen, Target, ListChecks, Wrench, FileText,
  ArrowRight, Bold, Italic, Underline, List, ListOrdered, Link as LinkIcon,
  AlignLeft, AlignCenter, AlignRight, Undo2, Redo2, Zap, Layers, Lightbulb,
  Sparkles, Link2, Users,
} from "lucide-react";
import {
  useLessonPlans, useCreateLessonPlan, useUpdateLessonPlan,
  usePublishLessonPlan, useDeleteLessonPlan, useLessonPlannerSettings,
  type LessonPlanRow,
} from "@/hooks/useSchool";
import { useMyContexts } from "@/hooks/useMyContexts";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import { Skeleton } from "@/components/loading/Skeleton";
import { SuccessCriteriaTable } from "@/components/forms/SuccessCriteriaTable";
import { cn } from "@/lib/utils";

const DAYS = [
  { idx: 0, label: "Monday", short: "Mon" },
  { idx: 1, label: "Tuesday", short: "Tue" },
  { idx: 2, label: "Wednesday", short: "Wed" },
  { idx: 3, label: "Thursday", short: "Thu" },
  { idx: 4, label: "Friday", short: "Fri" },
];

/**
 * Lesson Planner — weekly view. The whole feature fits on one page:
 *   - Week navigation (← Prev | This week | Next →)
 *   - 5-column grid (Mon–Fri) with plans-per-day
 *   - Click a plan → right-side drawer with full detail + actions
 *   - "+ New" opens the drawer in create mode
 *
 * Demo priority: every cell shows something for the seeded week, and the
 * drawer works for both create and edit flows with the same component.
 */
export default function LessonPlannerPage() {
  const [weekStart, setWeekStart] = useState<Date>(() => startOfWeek(new Date()));
  const weekEnd = addDays(weekStart, 6);

  const [drawer, setDrawer] = useState<
    | { mode: "closed" }
    | { mode: "create"; prefillDate?: string }
    | { mode: "edit"; plan: LessonPlanRow }
  >({ mode: "closed" });

  const { data, isLoading } = useLessonPlans({
    mine: true,
    start_date: formatISO(weekStart),
    end_date: formatISO(weekEnd),
  });
  const showSkeleton = useDelayedFlag(isLoading);
  const [flt, setFlt] = useState<LessonFilterValue>(EMPTY_LESSON_FILTER);
  const fd = useLessonFilterData(flt);
  // Choosing a week jumps the grid to it; choosing a day narrows the grid to that weekday.
  useEffect(() => { if (fd.week?.start_date) setWeekStart(startOfWeek(new Date(fd.week.start_date + "T00:00:00"))); }, [fd.week?.start_date]);
  const allPlans = data?.items ?? [];
  const plans = allPlans.filter((p: any) =>
    (!flt.classId || p.class_id === flt.classId) && (!flt.subjectId || p.subject_id === flt.subjectId) &&
    (!flt.day || String((new Date(p.lesson_date).getDay() + 6) % 7) === flt.day));

  const plansByDay = useMemo(() => {
    const grouped: Record<number, LessonPlanRow[]> = {};
    for (const p of plans) {
      const d = new Date(p.lesson_date);
      const dayIdx = (d.getDay() + 6) % 7; // Mon=0..Sun=6
      if (dayIdx > 4) continue;
      if (!grouped[dayIdx]) grouped[dayIdx] = [];
      grouped[dayIdx].push(p);
    }
    for (const k of Object.keys(grouped)) {
      grouped[Number(k)].sort(
        (a, b) => (a.period ?? 0) - (b.period ?? 0) || a.title.localeCompare(b.title),
      );
    }
    return grouped;
  }, [plans]);

  const todayIsInWeek = useMemo(() => {
    const today = new Date();
    return today >= weekStart && today <= weekEnd;
  }, [weekStart, weekEnd]);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="rounded-t-xl bg-emerald-800 text-white px-5 py-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold flex items-center gap-2"><NotebookPen size={20} /> Manage Lesson Plan</h1>
        <NextLink href="/dashboard/modules/school/lessons/create" className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-600 text-white text-sm font-semibold"><Plus size={15} /> Create Lesson Plan</NextLink>
      </div>
      <div className="bg-white border border-slate-200 rounded-b-xl mb-5">
        <LessonFilters value={flt} onChange={setFlt} />
        {(flt.section || flt.term || flt.classId || flt.weekId || flt.day || flt.subjectId) && (
          <div className="px-4 pb-3"><button onClick={() => setFlt(EMPTY_LESSON_FILTER)} className="btn-secondary">Reset filters</button></div>
        )}
      </div>

      {/* Week navigation */}
      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setWeekStart((d) => addDays(d, -7))}
            className="p-2 rounded-lg hover:bg-slate-100 text-slate-500"
            title="Previous week"
          >
            <ChevronLeft size={15} />
          </button>
          <button
            onClick={() => setWeekStart(startOfWeek(new Date()))}
            disabled={todayIsInWeek}
            className={cn(
              "px-3 h-8 rounded-lg text-xs font-semibold",
              todayIsInWeek
                ? "bg-brand-50 text-brand-700 cursor-default"
                : "text-slate-600 hover:bg-slate-100",
            )}
          >
            This week
          </button>
          <button
            onClick={() => setWeekStart((d) => addDays(d, 7))}
            className="p-2 rounded-lg hover:bg-slate-100 text-slate-500"
            title="Next week"
          >
            <ChevronRight size={15} />
          </button>
        </div>
        <div className="text-sm font-semibold text-slate-700">
          {formatNice(weekStart)} – {formatNice(addDays(weekStart, 4))}
        </div>
      </div>

      {/* Grid */}
      {showSkeleton ? (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {DAYS.map((d) => (
            <div key={d.idx} className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-20 w-full rounded-lg" />
              <Skeleton className="h-20 w-full rounded-lg" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {DAYS.map((d) => {
            const cellDate = addDays(weekStart, d.idx);
            const isToday = isSameDate(cellDate, new Date());
            const dayPlans = plansByDay[d.idx] ?? [];
            return (
              <DayColumn
                key={d.idx}
                label={d.label}
                short={d.short}
                date={cellDate}
                isToday={isToday}
                plans={dayPlans}
                onAdd={() => setDrawer({ mode: "create", prefillDate: formatISO(cellDate) })}
                onOpen={(p) => setDrawer({ mode: "edit", plan: p })}
              />
            );
          })}
        </div>
      )}

      {drawer.mode !== "closed" && (
        <PlanDrawer
          state={drawer}
          onClose={() => setDrawer({ mode: "closed" })}
        />
      )}
    </div>
  );
}

// ── Day column ───────────────────────────────────────────────────────────────

function DayColumn({
  label, short, date, isToday, plans, onAdd, onOpen,
}: {
  label: string;
  short: string;
  date: Date;
  isToday: boolean;
  plans: LessonPlanRow[];
  onAdd: () => void;
  onOpen: (p: LessonPlanRow) => void;
}) {
  return (
    <div className={cn(
      "bg-white rounded-xl border overflow-hidden flex flex-col",
      isToday ? "border-brand-300 ring-2 ring-brand-100" : "border-slate-200",
    )}>
      <div className={cn(
        "px-4 py-3 border-b flex items-center justify-between",
        isToday ? "bg-brand-50 border-brand-100" : "bg-slate-50/50 border-slate-100",
      )}>
        <div>
          <p className={cn(
            "text-xs font-black uppercase tracking-widest",
            isToday ? "text-brand-700" : "text-slate-500",
          )}>
            {short}
          </p>
          <p className={cn("text-[10px]", isToday ? "text-brand-600" : "text-slate-400")}>
            {label} · {date.getDate()} {date.toLocaleString("en-GB", { month: "short" })}
          </p>
        </div>
        {isToday && <span className="text-[10px] font-bold uppercase tracking-wider text-brand-600">Today</span>}
      </div>
      <div className="p-2 space-y-2 min-h-[280px] flex-1">
        {plans.length === 0 ? (
          <button
            onClick={onAdd}
            className="w-full h-full min-h-[240px] flex flex-col items-center justify-center text-center rounded-lg border-2 border-dashed border-slate-200 hover:border-brand-300 hover:bg-brand-50/30 transition-colors text-slate-400 hover:text-brand-600"
          >
            <Plus size={16} />
            <span className="text-[11px] font-semibold mt-1">Add plan</span>
          </button>
        ) : (
          <>
            {plans.map((p) => (
              <button
                key={p.id}
                onClick={() => onOpen(p)}
                className="w-full text-left rounded-lg border border-slate-200 bg-slate-50/50 hover:bg-brand-50 hover:border-brand-200 p-3 transition-colors group"
              >
                <div className="flex items-start justify-between gap-2 mb-1">
                  <span className={cn(
                    "badge text-[9px]",
                    p.status === "published"
                      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                      : "bg-amber-50 text-amber-700 border-amber-200",
                  )}>
                    {p.status === "published" ? "Published" : "Draft"}
                  </span>
                  {p.period && (
                    <span className="text-[10px] font-bold text-slate-400">P{p.period}</span>
                  )}
                </div>
                <p className="text-sm font-bold text-slate-900 line-clamp-2 group-hover:text-brand-700">
                  {p.title}
                </p>
                <p className="text-[10px] text-slate-500 mt-1">
                  {[p.subject_name, p.class_name].filter(Boolean).join(" · ") || "—"}
                </p>
              </button>
            ))}
            <button
              onClick={onAdd}
              className="w-full mt-1 text-[10px] font-semibold text-slate-400 hover:text-brand-600 py-2 rounded-lg hover:bg-brand-50/30 transition-colors"
            >
              + Add another plan
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ── Date helpers ─────────────────────────────────────────────────────────────

function startOfWeek(d: Date): Date {
  const copy = new Date(d);
  const day = (copy.getDay() + 6) % 7; // Mon=0..Sun=6
  copy.setDate(copy.getDate() - day);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function addDays(d: Date, n: number): Date {
  const copy = new Date(d);
  copy.setDate(copy.getDate() + n);
  return copy;
}

function formatISO(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function formatNice(d: Date): string {
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

function isSameDate(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}
