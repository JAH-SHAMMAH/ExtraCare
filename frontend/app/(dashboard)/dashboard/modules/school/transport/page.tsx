"use client";

import Link from "next/link";
import { useState } from "react";
import {
  Bus, Users as UsersIcon, AlertTriangle, ArrowRight, ArrowUpRight,
  Play, CheckCircle2, XCircle, Clock, MapPin, RefreshCw, Loader2,
  Sun, Moon, ChevronRight, User as UserIcon, Truck, Wrench,
} from "lucide-react";
import {
  useTransportDashboard, useTrip, useStartTrip, useCompleteTrip,
  useCancelTrip, useMarkBoarding,
  type TripRow, type BoardingRow, type BoardingStatus,
} from "@/hooks/useTransport";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import { Skeleton, CardGridSkeleton } from "@/components/loading/Skeleton";
import { cn } from "@/lib/utils";

export default function TransportDashboardPage() {
  const { data, isLoading, refetch, isFetching } = useTransportDashboard();
  const showSkeleton = useDelayedFlag(isLoading);
  const [openTripId, setOpenTripId] = useState<string | null>(null);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Operations</span><span>/</span>
            <span className="text-brand-600 font-semibold">Transport</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Transport Operations</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Live view of today&apos;s school runs, who&apos;s on board, and what needs attention.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="btn-secondary gap-2"
            title="Refresh now"
          >
            {isFetching ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            Refresh
          </button>
          <Link href="/dashboard/modules/school/transport/routes" className="btn-secondary gap-2">
            <MapPin size={14} /> Routes
          </Link>
          <Link href="/dashboard/modules/school/transport/fleet" className="btn-secondary gap-2">
            <Truck size={14} /> Fleet
          </Link>
        </div>
      </div>

      {showSkeleton ? (
        <CardGridSkeleton count={4} />
      ) : !data ? null : (
        <>
          {/* Operational stats strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <BigStat
              label="On board now"
              value={data.summary.on_board_now}
              icon={UsersIcon}
              color="bg-brand-50 text-brand-700 border-brand-100"
              accent="text-brand-700"
            />
            <BigStat
              label="Trips in progress"
              value={data.summary.trips_in_progress}
              sub={`${data.summary.trips_completed} completed today`}
              icon={Bus}
              color="bg-emerald-50 text-emerald-700 border-emerald-100"
              accent="text-emerald-700"
            />
            <BigStat
              label="Active routes"
              value={data.summary.active_routes}
              sub={`${data.summary.students_on_routes} students assigned`}
              icon={MapPin}
              color="bg-indigo-50 text-indigo-700 border-indigo-100"
              accent="text-indigo-700"
            />
            <BigStat
              label="Issues today"
              value={data.summary.issue_count}
              sub={data.summary.issue_count === 0 ? "All running smoothly" : "Needs attention"}
              icon={AlertTriangle}
              color={data.summary.issue_count
                ? "bg-rose-50 text-rose-700 border-rose-200"
                : "bg-slate-50 text-slate-500 border-slate-100"}
              accent={data.summary.issue_count ? "text-rose-700" : "text-slate-700"}
              highlight={data.summary.issue_count > 0}
            />
          </div>

          {/* Issues panel — only renders when there are issues */}
          {data.issues.length > 0 && (
            <div className="bg-rose-50/50 border border-rose-200 rounded-xl p-4 mb-6">
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-lg bg-rose-100 text-rose-700 flex items-center justify-center shrink-0">
                  <AlertTriangle size={16} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-rose-900">
                    {data.issues.length} issue{data.issues.length === 1 ? "" : "s"} today
                  </p>
                  <ul className="text-xs text-rose-700 mt-1 space-y-0.5">
                    {data.issues.map((iss, i) => (
                      <li key={`${iss.trip_id}-${i}`} className="flex items-start gap-1.5">
                        <span className="text-rose-400">•</span>
                        <span>{iss.detail}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* In-progress trips — the most important panel */}
          {data.in_progress.length > 0 && (
            <section className="mb-6">
              <h2 className="text-sm font-bold text-slate-800 mb-3 flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                </span>
                Live trips ({data.in_progress.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {data.in_progress.map((t) => (
                  <TripCard key={t.id} trip={t} onClick={() => setOpenTripId(t.id)} />
                ))}
              </div>
            </section>
          )}

          {/* Planned trips */}
          {data.planned.length > 0 && (
            <section className="mb-6">
              <h2 className="text-sm font-bold text-slate-800 mb-3 flex items-center gap-2">
                <Clock size={14} className="text-slate-400" /> Up next ({data.planned.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {data.planned.map((t) => (
                  <TripCard key={t.id} trip={t} onClick={() => setOpenTripId(t.id)} />
                ))}
              </div>
            </section>
          )}

          {/* Completed trips */}
          {data.completed.length > 0 && (
            <section className="mb-6">
              <h2 className="text-sm font-bold text-slate-500 mb-3 flex items-center gap-2">
                <CheckCircle2 size={14} className="text-slate-400" /> Completed today ({data.completed.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 opacity-80">
                {data.completed.map((t) => (
                  <TripCard key={t.id} trip={t} onClick={() => setOpenTripId(t.id)} subtle />
                ))}
              </div>
            </section>
          )}

          {/* Empty-day fallback */}
          {data.in_progress.length === 0
            && data.planned.length === 0
            && data.completed.length === 0
            && data.cancelled.length === 0 && (
              <EmptyDay />
            )}
        </>
      )}

      {openTripId && (
        <TripDrawer tripId={openTripId} onClose={() => setOpenTripId(null)} />
      )}
    </div>
  );
}

// ── Stat tiles ───────────────────────────────────────────────────────────────

function BigStat({
  label, value, sub, icon: Icon, color, accent, highlight = false,
}: {
  label: string;
  value: number | string;
  sub?: string;
  icon: typeof Bus;
  color: string;
  accent: string;
  highlight?: boolean;
}) {
  return (
    <div className={cn(
      "rounded-xl border p-5",
      color,
      highlight && "ring-2 ring-rose-200",
    )}>
      <div className="flex items-start justify-between mb-3">
        <Icon size={16} />
        <ArrowUpRight size={12} className="opacity-40" />
      </div>
      <p className={cn("text-3xl font-black tabular-nums", accent)}>{value}</p>
      <p className="text-[10px] font-bold uppercase tracking-widest opacity-80 mt-1">{label}</p>
      {sub && <p className="text-[10px] opacity-70 mt-1">{sub}</p>}
    </div>
  );
}

// ── Trip card (used for in-progress / planned / completed) ──────────────────

function TripCard({
  trip, onClick, subtle = false,
}: { trip: TripRow; onClick: () => void; subtle?: boolean }) {
  const counts = trip.counts;
  const totalAssigned =
    (counts.boarded ?? 0) +
    (counts.dropped_off ?? 0) +
    (counts.absent ?? 0) +
    (counts.skipped ?? 0) +
    (counts.expected ?? 0);
  const onBoard = counts.boarded ?? 0;
  const dropped = counts.dropped_off ?? 0;
  const absent = counts.absent ?? 0;
  const skipped = counts.skipped ?? 0;

  const isMorning = trip.direction === "morning";
  const isLive = trip.status === "in_progress";
  const isPlanned = trip.status === "planned";
  const isCompleted = trip.status === "completed";
  const isCancelled = trip.status === "cancelled";

  return (
    <button
      onClick={onClick}
      className={cn(
        "text-left bg-white rounded-xl border p-5 hover:shadow-md transition-all w-full",
        isLive ? "border-emerald-300" :
        isPlanned ? "border-slate-200" :
        isCancelled ? "border-rose-200 bg-rose-50/30" :
        "border-slate-200",
        subtle && "hover:shadow-sm",
      )}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <div className={cn(
            "w-9 h-9 rounded-lg flex items-center justify-center shrink-0",
            isMorning ? "bg-amber-50 text-amber-700" : "bg-indigo-50 text-indigo-700",
          )}>
            {isMorning ? <Sun size={15} /> : <Moon size={15} />}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-black text-slate-900 truncate">{trip.route_name}</p>
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
              {trip.route_code} · {isMorning ? "Morning run" : "Afternoon run"}
            </p>
          </div>
        </div>
        <StatusBadge status={trip.status} />
      </div>

      <div className="text-xs text-slate-500 mb-3 flex flex-wrap gap-x-4 gap-y-1">
        <span className="flex items-center gap-1">
          <Bus size={11} /> {trip.vehicle_registration ?? "—"}
        </span>
        <span className="flex items-center gap-1">
          <UserIcon size={11} /> {trip.driver_name ?? "—"}
        </span>
      </div>

      {/* Boarding counts as a mini-bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-widest text-slate-400">
          <span>Roster ({totalAssigned})</span>
          {isLive && <span className="text-emerald-600">{onBoard} on board</span>}
          {isCompleted && <span className="text-slate-600">{dropped} dropped off</span>}
        </div>
        <CountBar
          counts={[
            { key: "boarded", label: "Boarded", count: onBoard, color: "bg-emerald-500" },
            { key: "dropped_off", label: "Dropped off", count: dropped, color: "bg-emerald-700" },
            { key: "expected", label: "Pending", count: counts.expected ?? 0, color: "bg-slate-300" },
            { key: "absent", label: "Absent", count: absent, color: "bg-amber-400" },
            { key: "skipped", label: "Skipped", count: skipped, color: "bg-rose-500" },
          ]}
          total={totalAssigned}
        />
      </div>

      {(absent > 0 || skipped > 0) && (
        <div className="mt-3 text-[11px] text-rose-700 font-semibold flex items-center gap-1">
          <AlertTriangle size={11} />
          {[absent && `${absent} absent`, skipped && `${skipped} skipped`].filter(Boolean).join(" · ")}
        </div>
      )}
    </button>
  );
}

function StatusBadge({ status }: { status: TripRow["status"] }) {
  const map: Record<TripRow["status"], { label: string; cls: string }> = {
    in_progress: { label: "Live", cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
    planned:     { label: "Scheduled", cls: "bg-slate-100 text-slate-600 border-slate-200" },
    completed:   { label: "Completed", cls: "bg-slate-50 text-slate-500 border-slate-200" },
    cancelled:   { label: "Cancelled", cls: "bg-rose-50 text-rose-700 border-rose-200" },
  };
  const { label, cls } = map[status];
  return <span className={cn("badge text-[9px] shrink-0", cls)}>{label}</span>;
}

function CountBar({
  counts, total,
}: {
  counts: Array<{ key: string; label: string; count: number; color: string }>;
  total: number;
}) {
  if (total === 0) {
    return <div className="h-1.5 rounded-full bg-slate-100" />;
  }
  return (
    <div className="space-y-1.5">
      <div className="flex h-1.5 rounded-full bg-slate-100 overflow-hidden">
        {counts.map((c) =>
          c.count > 0 ? (
            <div
              key={c.key}
              className={c.color}
              style={{ width: `${(c.count / total) * 100}%` }}
            />
          ) : null,
        )}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-slate-500">
        {counts.filter((c) => c.count > 0).map((c) => (
          <span key={c.key} className="flex items-center gap-1">
            <span className={cn("w-1.5 h-1.5 rounded-full", c.color)} />
            {c.count} {c.label.toLowerCase()}
          </span>
        ))}
      </div>
    </div>
  );
}

function EmptyDay() {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
      <Bus size={28} className="text-slate-300 mx-auto mb-3" />
      <p className="text-sm font-semibold text-slate-700">No trips scheduled today</p>
      <p className="text-xs text-slate-500 mt-1">
        Create a trip from the route detail page when you&apos;re ready to dispatch.
      </p>
    </div>
  );
}

// ── Trip drawer (live boarding control) ──────────────────────────────────────

function TripDrawer({ tripId, onClose }: { tripId: string; onClose: () => void }) {
  const { data, isLoading } = useTrip(tripId);
  const showSkeleton = useDelayedFlag(isLoading);

  const startMut = useStartTrip();
  const completeMut = useCompleteTrip();
  const cancelMut = useCancelTrip();
  const boardMut = useMarkBoarding(tripId);

  const trip = data?.trip;
  const boardings = data?.boardings ?? [];
  const isMorning = trip?.direction === "morning";

  const isLive = trip?.status === "in_progress";
  const isPlanned = trip?.status === "planned";

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm animate-fade-in" onClick={onClose} />
      <div className="relative ml-auto w-full max-w-2xl bg-white shadow-2xl overflow-y-auto animate-slide-in flex flex-col">
        <div className="sticky top-0 z-10 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
              {trip ? `${trip.route_code} · ${isMorning ? "Morning" : "Afternoon"} run` : "Trip detail"}
            </p>
            <h2 className="text-lg font-black text-slate-900 truncate">
              {trip?.route_name ?? "—"}
            </h2>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-100 text-slate-500">
            <XCircle size={18} />
          </button>
        </div>

        {showSkeleton || !trip ? (
          <div className="p-6 space-y-3">
            <Skeleton className="h-20 w-full rounded-xl" />
            <Skeleton className="h-3 w-1/2" />
            <Skeleton className="h-32 w-full rounded-xl" />
          </div>
        ) : (
          <div className="p-6 space-y-5 flex-1">
            {/* Trip controls */}
            <div className="flex items-center justify-between gap-3 bg-slate-50 rounded-xl p-3 border border-slate-100">
              <div className="flex items-center gap-2">
                <StatusBadge status={trip.status} />
                <span className="text-xs text-slate-500">
                  {trip.driver_name ?? "—"} · {trip.vehicle_registration ?? "—"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                {isPlanned && (
                  <button
                    onClick={() => startMut.mutate(trip.id)}
                    disabled={startMut.isPending}
                    className="btn-primary gap-1.5 text-xs py-1.5 px-3"
                  >
                    {startMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                    Start trip
                  </button>
                )}
                {isLive && (
                  <button
                    onClick={() => completeMut.mutate(trip.id)}
                    disabled={completeMut.isPending}
                    className="btn-primary gap-1.5 text-xs py-1.5 px-3"
                  >
                    {completeMut.isPending ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle2 size={12} />}
                    Complete
                  </button>
                )}
                {(isPlanned || isLive) && (
                  <button
                    onClick={() => {
                      const reason = prompt("Reason for cancellation?");
                      if (reason !== null) cancelMut.mutate({ id: trip.id, reason });
                    }}
                    disabled={cancelMut.isPending}
                    className="btn-secondary text-xs py-1.5 px-3 text-rose-700 border-rose-200 hover:bg-rose-50"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </div>

            {/* Boarding rows */}
            <div>
              <h3 className="text-sm font-bold text-slate-800 mb-2">
                Roster ({boardings.length})
              </h3>
              <div className="rounded-xl border border-slate-200 overflow-hidden divide-y divide-slate-50">
                {boardings.map((b) => (
                  <BoardingRowItem
                    key={b.id}
                    boarding={b}
                    isMorning={!!isMorning}
                    canMark={isLive}
                    onMark={(status) => boardMut.mutate({ student_id: b.student_id, status })}
                    pending={boardMut.isPending && boardMut.variables?.student_id === b.student_id}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const BOARDING_ACTIONS: Record<"morning" | "afternoon", Array<{ status: BoardingStatus; label: string; cls: string }>> = {
  morning: [
    { status: "boarded", label: "Boarded", cls: "bg-emerald-600 text-white border-emerald-600" },
    { status: "absent", label: "Absent", cls: "bg-amber-50 text-amber-700 border-amber-200" },
    { status: "skipped", label: "Skipped", cls: "bg-rose-50 text-rose-700 border-rose-200" },
  ],
  afternoon: [
    { status: "dropped_off", label: "Dropped off", cls: "bg-emerald-700 text-white border-emerald-700" },
    { status: "absent", label: "Absent", cls: "bg-amber-50 text-amber-700 border-amber-200" },
    { status: "skipped", label: "Skipped", cls: "bg-rose-50 text-rose-700 border-rose-200" },
  ],
};

function BoardingRowItem({
  boarding, isMorning, canMark, onMark, pending,
}: {
  boarding: BoardingRow;
  isMorning: boolean;
  canMark: boolean;
  onMark: (s: BoardingStatus) => void;
  pending: boolean;
}) {
  const statusMeta: Record<BoardingStatus, { label: string; cls: string; dot: string }> = {
    expected:    { label: "Pending",     cls: "text-slate-500",   dot: "bg-slate-300" },
    boarded:     { label: "Boarded",     cls: "text-emerald-700", dot: "bg-emerald-500" },
    dropped_off: { label: "Dropped off", cls: "text-emerald-700", dot: "bg-emerald-700" },
    absent:      { label: "Absent",      cls: "text-amber-700",   dot: "bg-amber-400" },
    skipped:     { label: "Skipped",     cls: "text-rose-700",    dot: "bg-rose-500" },
  };
  const m = statusMeta[boarding.status];
  const actions = BOARDING_ACTIONS[isMorning ? "morning" : "afternoon"];

  return (
    <div className="px-4 py-3 flex items-center gap-3">
      <div className={cn("w-2.5 h-2.5 rounded-full shrink-0", m.dot)} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-bold text-slate-900 truncate">{boarding.student_name}</p>
        <p className="text-[10px] text-slate-500 truncate">
          {boarding.student_code}{boarding.stop_name ? ` · ${boarding.stop_name}` : ""}
        </p>
      </div>
      {canMark ? (
        <div className="flex items-center gap-1">
          {actions.map((a) => {
            const active = boarding.status === a.status;
            return (
              <button
                key={a.status}
                onClick={() => onMark(a.status)}
                disabled={pending}
                className={cn(
                  "text-[10px] font-bold border px-2.5 py-1 rounded-md transition-colors",
                  active ? a.cls : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50",
                )}
              >
                {pending && active ? <Loader2 size={10} className="animate-spin" /> : a.label}
              </button>
            );
          })}
        </div>
      ) : (
        <span className={cn("text-[10px] font-bold uppercase tracking-widest", m.cls)}>
          {m.label}
        </span>
      )}
    </div>
  );
}
