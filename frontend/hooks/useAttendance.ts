"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { attendanceApi } from "@/lib/api";

// ── Types (mirror backend schemas/attendance.py) ──────────────────────────────

export interface DailyAttendanceRow {
  student_id: string;
  student_name: string;
  status: string | null; // present | late | absent | excused | null
  first_check_in: string | null;
  last_check_out: string | null;
}

export interface DailyAttendanceSummary {
  date: string;
  present: number;
  late: number;
  absent: number;
  excused: number;
  total_students: number;
  rows: DailyAttendanceRow[];
}

export interface MonthlyAttendanceSummary {
  year: number;
  month: number;
  present: number;
  late: number;
  absent: number;
  excused: number;
  days_recorded: number;
}

export interface AttendanceEvent {
  id: string;
  student_id: string;
  event_type: "check_in" | "check_out";
  event_time: string;
  source: string;
  device_id: string | null;
  notes: string | null;
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

export function useDailyAttendance(date?: string, classId?: string, enabled = true) {
  return useQuery<DailyAttendanceSummary>({
    queryKey: ["attendance", "daily", date ?? "today", classId ?? "all"],
    queryFn: () => attendanceApi.daily({ date, class_id: classId || undefined }),
    enabled,
    staleTime: 30_000,
  });
}

export function useMonthlyAttendance(
  year: number,
  month: number,
  studentId?: string,
  enabled = true,
) {
  return useQuery<MonthlyAttendanceSummary>({
    queryKey: ["attendance", "monthly", year, month, studentId ?? "all"],
    queryFn: () => attendanceApi.monthly({ year, month, student_id: studentId }),
    enabled,
    staleTime: 60_000,
  });
}

export function useStudentAttendanceHistory(studentId: string | undefined, limit = 50) {
  return useQuery<AttendanceEvent[]>({
    queryKey: ["attendance", "history", studentId ?? "none", limit],
    queryFn: () => attendanceApi.studentHistory(studentId as string, limit),
    enabled: !!studentId,
    staleTime: 30_000,
  });
}

export function useRecordManualAttendance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: attendanceApi.recordManual,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["attendance"] });
      toast.success("Attendance recorded. Parents have been notified.");
    },
    onError: (e: any) =>
      toast.error(e?.response?.data?.detail || "Could not record attendance."),
  });
}
