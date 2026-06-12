"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { notificationsApi } from "@/lib/api";

// ── Types (mirror backend routers/notifications.py) ───────────────────────────

export interface AppNotification {
  id: string;
  type: string; // e.g. "attendance", "system", "plan_limit"
  title: string;
  message: string | null;
  payload: Record<string, unknown>;
  read: boolean;
  created_at: string | null;
}

export interface NotificationList {
  unread_count: number;
  items: AppNotification[];
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

/** Per-user notification inbox. Pass `type` to scope (e.g. "attendance"). */
export function useNotifications(params?: {
  type?: string;
  unread_only?: boolean;
  limit?: number;
}) {
  return useQuery<NotificationList>({
    queryKey: ["notifications", params ?? {}],
    queryFn: () => notificationsApi.list(params),
    refetchInterval: 30_000, // near-real-time without a socket
    staleTime: 15_000,
  });
}

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
}

export function useMarkAllNotificationsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
}
