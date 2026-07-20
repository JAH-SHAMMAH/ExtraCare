"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { hrAttendanceApi } from "@/lib/api";

export type AttendanceEvent = {
  id: string; staff_user_id: string; staff_name: string | null;
  event_type: "clock_in" | "clock_out"; event_time: string; source: string;
  note: string | null; created_at: string;
};

// ── Self-service ────────────────────────────────────────────────────────────
export function useMyAttendance() {
  return useQuery<AttendanceEvent[]>({ queryKey: ["hr-my-attendance"], queryFn: () => hrAttendanceApi.my() });
}

export function useClock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { event_type: "clock_in" | "clock_out"; note?: string }) => hrAttendanceApi.clock(v.event_type, v.note),
    onSuccess: (_d, v) => {
      qc.invalidateQueries({ queryKey: ["hr-my-attendance"] });
      qc.invalidateQueries({ queryKey: ["hr-attendance-log"] });
      toast.success(v.event_type === "clock_in" ? "Clocked in." : "Clocked out.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn’t record that."),
  });
}

// ── Admin log ───────────────────────────────────────────────────────────────
export function useStaffAttendanceLog(params?: { staff_user_id?: string; from_date?: string; to_date?: string }) {
  return useQuery<AttendanceEvent[]>({ queryKey: ["hr-attendance-log", params], queryFn: () => hrAttendanceApi.events(params) });
}

export function useAddAttendanceEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (d: object) => hrAttendanceApi.addEvent(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hr-attendance-log"] }); toast.success("Punch added."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn’t add."),
  });
}

export function useDeleteAttendanceEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => hrAttendanceApi.removeEvent(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hr-attendance-log"] }); toast.success("Removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn’t remove."),
  });
}
