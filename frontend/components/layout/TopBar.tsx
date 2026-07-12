"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { Bell, HelpCircle, Settings, Loader2, MessageSquare, Menu } from "lucide-react";
import { useAuthStore } from "@/lib/store";
import { timeAgo } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/lib/api";

const GlobalSearch = dynamic(() => import("./GlobalSearch").then((mod) => mod.GlobalSearch), { ssr: false });
import { RoleSwitcher } from "@/components/role/RoleSwitcher";
import type { ActivityLog } from "@/types";

export function TopBar({ onMenu }: { onMenu?: () => void }) {
  const router = useRouter();
  const { user } = useAuthStore();
  const [notifOpen, setNotifOpen] = useState(false);
  const notifRef = useRef<HTMLDivElement>(null);

  const { data: notifications = [], isLoading: notifsLoading } = useQuery<ActivityLog[]>({
    queryKey: ["analytics", "activity-feed", "topbar"],
    queryFn: () => analyticsApi.activityFeed(5),
    refetchInterval: 30_000,
  });

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotifOpen(false);
      }
    }
    if (notifOpen) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [notifOpen]);

  return (
    <header className="no-print fixed top-0 left-0 lg:left-60 right-0 z-30 h-16 bg-white/90 backdrop-blur-md border-b border-slate-200/70 flex items-center px-4 md:px-6 gap-3 md:gap-4 shadow-sm shadow-slate-100/50">
      {/* Mobile: open the sidebar drawer */}
      <button
        onClick={onMenu}
        aria-label="Open menu"
        className="lg:hidden -ml-1 p-2 rounded-lg text-slate-500 hover:bg-slate-100 transition-colors shrink-0"
      >
        <Menu size={20} />
      </button>

      {/* Global Search */}
      <GlobalSearch />

      <div className="flex items-center gap-2 ml-auto">
        {/* Role switcher (only visible for multi-role users — Phase 6.3). */}
        <RoleSwitcher />

        {/* Chat — jumps straight to /messenger. An unread badge hangs off
            WebSocket delivery, which needs an unread tally endpoint; add
            it here once that lands. */}
        <Link
          href="/messenger"
          className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors"
          title="Messenger"
          aria-label="Open messenger"
        >
          <MessageSquare size={18} />
        </Link>

        {/* Notifications */}
        <div className="relative" ref={notifRef}>
          <button
            onClick={() => setNotifOpen((o) => !o)}
            className="relative p-2 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors"
          >
            <Bell size={18} />
            {notifications.length > 0 && (
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border-2 border-white" />
            )}
          </button>

          {notifOpen && (
            <div className="absolute right-0 top-full mt-2 w-80 bg-white rounded-xl border border-slate-200 shadow-xl z-50 overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-800">Notifications</h3>
                <Link
                  href="/dashboard/notifications"
                  onClick={() => setNotifOpen(false)}
                  className="text-xs text-brand-600 font-semibold hover:underline"
                >
                  View all
                </Link>
              </div>
              <div className="max-h-72 overflow-y-auto divide-y divide-slate-50">
                {notifsLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 size={18} className="animate-spin text-slate-400" />
                  </div>
                ) : notifications.length === 0 ? (
                  <div className="px-4 py-8 text-center text-sm text-slate-400">
                    No notifications yet.
                  </div>
                ) : (
                  notifications.map((n) => (
                    <div key={n.id} className="px-4 py-3 hover:bg-slate-50 transition-colors cursor-pointer">
                      <p className="text-sm font-medium text-slate-800 capitalize leading-snug">
                        {n.action.replace(".", " ").replace(/_/g, " ")}
                      </p>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {n.actor_email && <span>{n.actor_email} &middot; </span>}
                        {timeAgo(n.created_at)}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Help */}
        <button
          onClick={() => router.push("/support")}
          className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors"
          title="Help & Support"
        >
          <HelpCircle size={18} />
        </button>

        {/* Settings */}
        <button
          onClick={() => router.push("/dashboard/settings")}
          className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors"
          title="Settings"
        >
          <Settings size={18} />
        </button>

        {/* Avatar */}
        <Link
          href="/dashboard/profile"
          className="ml-2 flex items-center gap-2 pl-3 border-l border-slate-200 hover:opacity-80 transition-opacity"
        >
          <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center text-white text-xs font-bold overflow-hidden">
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt="" className="w-full h-full object-cover" />
            ) : (
              user?.full_name?.charAt(0) ?? "?"
            )}
          </div>
          <div className="hidden md:block">
            <p className="text-xs font-semibold text-slate-800 leading-tight">{user?.full_name}</p>
            <p className="text-[10px] text-slate-400 capitalize">{user?.primary_role?.replace("_", " ")}</p>
          </div>
        </Link>
      </div>
    </header>
  );
}
