"use client";

import { Bell, CheckCheck, LogIn, LogOut } from "lucide-react";
import { cn, timeAgo } from "@/lib/utils";
import {
  useNotifications,
  useMarkAllNotificationsRead,
  type AppNotification,
} from "@/hooks/useNotifications";

export const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/** "7:32 AM" in the viewer's local time, or "—" when missing. */
export function formatClock(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

const STATUS_STYLES: Record<string, string> = {
  present: "bg-emerald-50 text-emerald-700 border-emerald-200",
  late: "bg-amber-50 text-amber-700 border-amber-200",
  absent: "bg-red-50 text-red-700 border-red-200",
  excused: "bg-blue-50 text-blue-700 border-blue-200",
};

export function StatusBadge({ status }: { status: string | null }) {
  if (!status) {
    return <span className="badge bg-slate-50 text-slate-500 border-slate-200">Absent</span>;
  }
  return (
    <span className={cn("badge capitalize", STATUS_STYLES[status] ?? "bg-slate-50 text-slate-500 border-slate-200")}>
      {status}
    </span>
  );
}

/** Single stat card matching the dashboard design system. */
export function StatCard({
  label,
  value,
  accent = "text-slate-900",
}: {
  label: string;
  value: string | number;
  accent?: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">{label}</p>
      <p className={cn("text-xl font-black tabular-nums", accent)}>{value}</p>
    </div>
  );
}

/** Present/Late/Absent/Excused + attendance-rate cards from a daily summary. */
export function DailySummaryCards({
  present,
  late,
  absent,
  excused,
  total,
}: {
  present: number;
  late: number;
  absent: number;
  excused: number;
  total: number;
}) {
  const rate = total > 0 ? Math.round(((present + late) / total) * 100) : null;
  const rateAccent =
    rate == null ? "text-slate-400" : rate >= 90 ? "text-emerald-600" : rate >= 75 ? "text-amber-600" : "text-rose-600";
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      <StatCard label="Present" value={present} accent="text-emerald-600" />
      <StatCard label="Late" value={late} accent="text-amber-600" />
      <StatCard label="Absent" value={absent} accent="text-rose-600" />
      <StatCard label="Excused" value={excused} accent="text-blue-600" />
      <StatCard label="Total" value={total} />
      <StatCard label="Attendance" value={rate != null ? `${rate}%` : "—"} accent={rateAccent} />
    </div>
  );
}

/**
 * Attendance arrival/departure alerts for the signed-in user, from the real
 * /notifications inbox (type=attendance). This is the "notification view" that
 * lets parents see their child's check-in/out alerts inside the portal.
 */
export function AttendanceAlertsPanel({ limit = 20 }: { limit?: number }) {
  const { data, isLoading } = useNotifications({ type: "attendance", limit });
  const markAll = useMarkAllNotificationsRead();
  const items = data?.items ?? [];
  const unread = data?.unread_count ?? 0;

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bell size={15} className="text-brand-600" />
          <h2 className="text-sm font-black text-slate-900">Attendance alerts</h2>
          {unread > 0 && (
            <span className="badge bg-brand-50 text-brand-700 border-brand-200 text-[10px]">{unread} new</span>
          )}
        </div>
        {unread > 0 && (
          <button
            onClick={() => markAll.mutate()}
            disabled={markAll.isPending}
            className="text-xs font-semibold text-slate-500 hover:text-brand-700 flex items-center gap-1.5"
          >
            <CheckCheck size={13} /> Mark all read
          </button>
        )}
      </div>

      <div className="divide-y divide-slate-50 max-h-[28rem] overflow-y-auto">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="px-5 py-4">
              <div className="h-4 w-56 bg-slate-100 rounded animate-pulse" />
            </div>
          ))
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-14 text-slate-400">
            <Bell size={34} className="mb-2 opacity-40" />
            <p className="font-semibold text-sm">No attendance alerts yet</p>
            <p className="text-xs mt-1">You&apos;ll be notified the moment your child checks in or out.</p>
          </div>
        ) : (
          items.map((n) => <AlertRow key={n.id} n={n} />)
        )}
      </div>
    </div>
  );
}

function AlertRow({ n }: { n: AppNotification }) {
  const isOut = (n.payload?.event_type as string) === "check_out";
  const Icon = isOut ? LogOut : LogIn;
  const tone = isOut ? "bg-slate-100 text-slate-600" : "bg-emerald-50 text-emerald-600";
  return (
    <div className={cn("flex items-start gap-3 px-5 py-4", !n.read && "bg-brand-50/30")}>
      <div className={cn("mt-0.5 w-8 h-8 rounded-lg flex items-center justify-center shrink-0", tone)}>
        <Icon size={15} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-800 leading-snug">{n.message || n.title}</p>
        <p className="text-[10px] text-slate-400 mt-1">{n.created_at ? timeAgo(n.created_at) : ""}</p>
      </div>
      {!n.read && <span className="mt-1.5 w-2 h-2 rounded-full bg-brand-600 shrink-0" />}
    </div>
  );
}
