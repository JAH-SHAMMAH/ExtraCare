"use client";

import { useMemo, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Cell,
} from "recharts";
import { BarChart3, School as SchoolIcon } from "lucide-react";
import { useClasses } from "@/hooks/useSchool";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import { Skeleton } from "@/components/loading/Skeleton";
import { cn } from "@/lib/utils";
import {
  allSessionsRows, currentSessionOf, currentSessionRows,
} from "@/lib/classDistribution";
import type { SchoolClass } from "@/types";

/**
 * School Class Distribution — students per class for the current session, with a
 * toggle to an "All sessions" view (total students per academic year). Data comes
 * straight from GET /school/classes (each row carries student_count + academic_year),
 * so this is a real, live chart — no separate analytics endpoint.
 *
 * Current view : one bar per class in the current academic year (X = class name),
 *                each class given its own hue so a level stays visually trackable
 *                even as the roster grows or ordering shifts.
 * All sessions : NOT a time series yet, and says so. See `allSessionsData`.
 *
 * ~~~ TWO FAULTS FIXED HERE ~~~
 * 1. Labels were built as `${c.name} ${c.section}`, where `section` is the ARM.
 *    Fairview's Year classes are already NAMED "Year 1 A", so 24 of 31 printed
 *    their arm twice ("YEAR 1 A A"), and the uppercasing tickFormatter made it
 *    shout. Both are gone: `classLabel` is the shared rule, and the name prints
 *    as stored.
 * 2. A class with a NULL `academic_year` was excluded from the current session
 *    entirely, because the filter was an equality against the resolved session.
 *    Fairview's Playgroup is that class. It holds 0 pupils today so the total
 *    was still right, but enrol one child and they would have vanished from
 *    both the chart and the headline count with no empty state to explain it.
 */

// Curated 12+ hue palette — distinct-but-cohesive, cycled per class in the current view.
const PALETTE = [
  "#38bdf8", "#34d399", "#fbbf24", "#fb7185", "#818cf8", "#2dd4bf",
  "#fb923c", "#a78bfa", "#60a5fa", "#4ade80", "#f472b6", "#f87171",
  "#22d3ee", "#facc15", "#c084fc", "#5eead4",
];
const SESSION_ACCENT = "#0ea5e9"; // all-sessions view is a time series → single accent
const SCROLL_THRESHOLD = 12;       // above this many bars, scroll instead of squeezing
const MIN_BAND = 56;               // px per bar when scrolling, so labels never collide

export function ClassDistributionChart() {
  const [view, setView] = useState<"current" | "all">("current");
  // page_size 100 is the backend max — a school's class count sits well under it.
  const { data, isLoading } = useClasses({ page_size: 100 });
  const showSkeleton = useDelayedFlag(isLoading);

  const classes: SchoolClass[] = useMemo(
    () => (data?.items ?? (Array.isArray(data) ? data : [])) as SchoolClass[],
    [data],
  );

  // All three derivations live in lib/classDistribution.ts so they can be
  // tested without standing up recharts. See that file for the NULL
  // academic_year fault and why "All sessions" is not a time series.
  const currentSession = useMemo(() => currentSessionOf(classes), [classes]);
  const currentData = useMemo(
    () => currentSessionRows(classes, currentSession), [classes, currentSession]);
  const allSessionsData = useMemo(
    () => allSessionsRows(classes, currentSession), [classes, currentSession]);

  const chartData = view === "current" ? currentData : allSessionsData;
  const totalStudents = useMemo(
    () => currentData.reduce((sum, r) => sum + r.students, 0),
    [currentData],
  );

  // Past the threshold, force a min width per bar and let the card scroll horizontally.
  const needsScroll = chartData.length > SCROLL_THRESHOLD;

  return (
    <div className="bg-white rounded-xl border border-slate-200/70 p-5 shadow-sm">
      {/* Header + toggle */}
      <div className="flex items-start justify-between gap-4 mb-5 flex-wrap">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center">
            <BarChart3 size={16} />
          </div>
          <div>
            <p className="text-sm font-bold text-slate-900">School Class Distribution</p>
            <p className="text-[11px] text-slate-400">
              {view === "current"
                ? currentSession
                  ? `${totalStudents.toLocaleString()} students · ${currentSession} session`
                  : "Current session"
                : "Per-session history not recorded yet — showing the current session"}
            </p>
          </div>
        </div>

        <div className="inline-flex rounded-lg bg-slate-100 p-0.5 text-[11px] font-semibold">
          <button
            onClick={() => setView("current")}
            className={cn(
              "px-3 py-1.5 rounded-md transition-colors",
              view === "current" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700",
            )}
          >
            Current session
          </button>
          <button
            onClick={() => setView("all")}
            className={cn(
              "px-3 py-1.5 rounded-md transition-colors",
              view === "all" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700",
            )}
          >
            All sessions
          </button>
        </div>
      </div>

      {/* The All-sessions view draws a bar with a session name on it, which
          invites being read as history. Say plainly that it is not, rather than
          relying on the subtitle alone. */}
      {view === "all" && !showSkeleton && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50/60 px-3 py-2">
          <p className="text-[11px] leading-relaxed text-amber-900">
            <span className="font-semibold">Showing the current session.</span>{" "}
            Student numbers per class are only recorded for the roster as it is
            now, so past sessions cannot be charted yet.
          </p>
        </div>
      )}

      {/* Body */}
      {showSkeleton ? (
        <div className="flex items-end gap-3 h-[300px] px-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="flex-1 rounded-t-md" style={{ height: `${30 + ((i * 37) % 60)}%` }} />
          ))}
        </div>
      ) : chartData.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="overflow-x-auto -mx-1 px-1">
          <div style={{ minWidth: needsScroll ? chartData.length * MIN_BAND : undefined }}>
            <ResponsiveContainer width="100%" height={340}>
              <BarChart data={chartData} margin={{ top: 8, right: 12, left: 8, bottom: 0 }} barCategoryGap="22%">
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 11, fill: "#64748b", fontWeight: 600 }}
                  interval={0}
                  angle={-35}
                  textAnchor="end"
                  height={72}
                  tickMargin={8}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "#94a3b8" }}
                  allowDecimals={false}
                  width={48}
                  label={{
                    value: "Number of Students",
                    angle: -90,
                    position: "insideLeft",
                    style: { textAnchor: "middle", fontSize: 11, fontWeight: 600, fill: "#64748b" },
                  }}
                />
                <Tooltip cursor={{ fill: "#f8fafc" }} content={<DistTooltip view={view} />} />
                <Bar dataKey="students" radius={[4, 4, 0, 0]} maxBarSize={46}>
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={view === "current" ? PALETTE[i % PALETTE.length] : SESSION_ACCENT} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}

function DistTooltip({
  active, payload, view,
}: {
  active?: boolean;
  payload?: Array<{ payload: { label: string; students: number; capacity?: number; classes?: number } }>;
  view: "current" | "all";
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="bg-white rounded-lg border border-slate-200 shadow-lg px-3 py-2 text-xs">
      <p className="font-bold text-slate-900 mb-0.5">{row.label}</p>
      <p className="text-slate-600">
        <span className="font-semibold tabular-nums">{row.students.toLocaleString()}</span> students
      </p>
      {view === "current" && typeof row.capacity === "number" && row.capacity > 0 && (
        <p className="text-slate-400 text-[11px] mt-0.5">
          {row.capacity} capacity · {Math.round((row.students / row.capacity) * 100)}% full
        </p>
      )}
      {view === "all" && typeof row.classes === "number" && (
        <p className="text-slate-400 text-[11px] mt-0.5">
          {row.classes} class{row.classes === 1 ? "" : "es"}
        </p>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-[300px] text-center">
      <div className="w-11 h-11 rounded-xl bg-slate-50 text-slate-300 flex items-center justify-center mb-3">
        <SchoolIcon size={20} />
      </div>
      <p className="text-sm font-semibold text-slate-600">No classes yet</p>
      <p className="text-xs text-slate-400 mt-1 max-w-xs">
        Add classes and enrol students to see the distribution here.
      </p>
    </div>
  );
}
