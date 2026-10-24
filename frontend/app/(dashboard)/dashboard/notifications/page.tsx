"use client";

import { CheckCheck, Bell, LogIn, LogOut, Trash2 } from "lucide-react";
import { cn, timeAgo } from "@/lib/utils";
import { useNotifications, useMarkNotificationRead, useMarkAllNotificationsRead, useClearNotifications } from "@/hooks/useNotifications";

export default function NotificationsPage() {
  const { data, isLoading } = useNotifications({ limit: 100 });
  const markRead = useMarkNotificationRead();
  const markAll = useMarkAllNotificationsRead();
  const clearAll = useClearNotifications();
  const items = data?.items ?? [];
  const unread = data?.unread_count ?? 0;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Core</span><span>/</span>
            <span className="text-brand-600 font-semibold">Notifications</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Notifications</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Alerts for you, including when your child arrives at or leaves school.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {unread > 0 && (
            <button className="btn-secondary gap-2 text-sm" onClick={() => markAll.mutate()} disabled={markAll.isPending}>
              <CheckCheck size={15} /> Mark all read ({unread})
            </button>
          )}
          {items.length > 0 && (
            <button className="btn-secondary gap-2 text-sm text-rose-600" onClick={() => clearAll.mutate()} disabled={clearAll.isPending}>
              <Trash2 size={15} /> Clear all
            </button>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden divide-y divide-slate-50">
        {isLoading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="px-5 py-4"><div className="h-4 w-56 bg-slate-100 rounded animate-pulse" /></div>
          ))
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-400">
            <Bell size={40} className="mb-3 opacity-40" />
            <p className="font-semibold">No notifications</p>
            <p className="text-sm mt-1">You&apos;re all caught up.</p>
          </div>
        ) : (
          items.map((n) => {
            const out = n.payload?.event_type === "check_out";
            const Icon = n.type === "attendance" ? (out ? LogOut : LogIn) : Bell;
            return (
              <button
                key={n.id}
                onClick={() => !n.read && markRead.mutate(n.id)}
                className={cn("w-full text-left flex items-start gap-3 px-5 py-4 hover:bg-slate-50 transition-colors", !n.read && "bg-brand-50/30")}
              >
                <div className={cn("mt-0.5 w-8 h-8 rounded-lg flex items-center justify-center shrink-0",
                  n.type === "attendance" ? (out ? "bg-slate-100 text-slate-600" : "bg-emerald-50 text-emerald-600") : "bg-brand-50 text-brand-600")}>
                  <Icon size={15} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-800 leading-snug">{n.title}</p>
                  {n.message && <p className="text-xs text-slate-500 mt-0.5">{n.message}</p>}
                  <p className="text-[10px] text-slate-400 mt-1">{n.created_at ? timeAgo(n.created_at) : ""}</p>
                </div>
                {!n.read && <span className="mt-2 w-2 h-2 rounded-full bg-brand-500 shrink-0" />}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
