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
import type { SchoolClass } from "@/types";

/**
 * School Class Distribution — students per class for the current session, with a
 * toggle to an "All sessions" view (total students per academic year). Data comes
 * straight from GET /school/classes (each row carries student_count + academic_year),
 * so this is a real, live chart — no separate analytics endpoint.
 *
 * Current view : one bar per class in the latest academic year (X = class name),
 *                each class given its own hue so a level stays visually trackable
 *                even as the roster grows or ordering shifts.
 * All sessions : one bar per academic year (X = session, Y = total students) — a
 *                time series, so a single accent rather than the per-class palette.
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

  // Sessions newest-first so [0] is the "current" one; chronological for the all view.
  const sessions = useMemo(
    () => Array.from(new Set(classes.map((c) => c.academic_year).filter(Boolean))).sort().reverse(),
    [classes],
  );
  const currentSession = sessions[0] ?? null;

  const currentData = useMemo(
    () =>
      classes
        .filter((c) => c.academic_year === currentSession)
        .map((c) => ({
          label: c.section ? `${c.name} ${c.section}` : c.name,
          students: c.student_count,
          capacity: c.capacity,
        }))
        .sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true })),
    [classes, currentSession],
  );

  const allSessionsData = useMemo(
    () =>
      sessions
        .slice()
        .reverse() // chronological (oldest → newest) across the X-axis
        .map((s) => {
          const rows = classes.filter((c) => c.academic_year === s);
          return {
            label: s,
            students: rows.reduce((sum, c) => sum + (c.student_count || 0), 0),
            classes: rows.length,
          };
        }),
    [classes, sessions],
  );

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
                : `${sessions.length} session${sessions.length === 1 ? "" : "s"} on record`}
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
                  tickFormatter={(v: string) => String(v).toUpperCase()}
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
