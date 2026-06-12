"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { liveApi } from "@/lib/api";
import type { LiveSession, LiveRecording, LiveAnalytics, TimetableSlot } from "@/types";

const STALE_MS = 10_000;

export function useLiveSessions(activeOnly = true) {
  return useQuery<LiveSession[]>({
    queryKey: ["live", "sessions", { activeOnly }],
    queryFn: () => liveApi.sessions.list({ active_only: activeOnly }),
    staleTime: STALE_MS,
    refetchInterval: 15_000,
  });
}

export function useLiveSession(id: string | null) {
  return useQuery<LiveSession>({
    queryKey: ["live", "session", id],
    queryFn: () => liveApi.sessions.get(id as string),
    enabled: !!id,
    staleTime: STALE_MS,
  });
}

export function useStartLive() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: liveApi.start,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["live", "sessions"] }),
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Could not start session."),
  });
}

export function useEndLive() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => liveApi.end(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["live"] }),
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Could not end session."),
  });
}

export function useLiveRecordings(sessionId: string | null) {
  return useQuery<LiveRecording[]>({
    queryKey: ["live", "recordings", sessionId],
    queryFn: () => liveApi.recordings.list(sessionId as string),
    enabled: !!sessionId,
    staleTime: STALE_MS,
  });
}

export function useUploadRecording(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ blob, duration_seconds }: { blob: Blob; duration_seconds?: number }) =>
      liveApi.recordings.upload(sessionId, blob, duration_seconds),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["live", "recordings", sessionId] });
      qc.invalidateQueries({ queryKey: ["live", "sessions"] });
      qc.invalidateQueries({ queryKey: ["live", "session", sessionId] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Recording upload failed."),
  });
}

export function useLiveAnalytics(sessionId: string | null, enabled = true) {
  return useQuery<LiveAnalytics>({
    queryKey: ["live", "analytics", sessionId],
    queryFn: () => liveApi.analytics(sessionId as string),
    enabled: !!sessionId && enabled,
    staleTime: 5_000,
  });
}

// Timetable-integrated live sessions — drives "Go Live" buttons on the
// teacher's day view and "Join" badges on the student's.
export function useLiveTimetableToday(enabled = true) {
  return useQuery<TimetableSlot[]>({
    queryKey: ["live", "timetable-today"],
    queryFn: () => liveApi.timetable.today(),
    enabled,
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
}

export function useStartLiveFromTimetable() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (timetable_id: string) => liveApi.timetable.start(timetable_id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["live"] });
    },
    onError: (e: any) => {
      const d = e?.response?.data?.detail;
      if (d?.error === "feature_disabled") {
        toast.error("Live classes aren't enabled on your plan.");
      } else {
        toast.error(d?.message || d || "Could not start live session.");
      }
    },
  });
}
