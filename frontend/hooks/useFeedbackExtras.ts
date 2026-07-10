"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { feedbackApi } from "@/lib/api";
import type { FeedbackSettings, DailyReport, StudentDailyReport, CRMContact } from "@/types";

function saver<T>(fn: (v: any) => Promise<T>, key: string, ok: string) {
  return () => {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: fn,
      onSuccess: () => { qc.invalidateQueries({ queryKey: [key] }); toast.success(ok); },
      onError: (e: any) => toast.error(e?.response?.data?.detail || "Action failed."),
    });
  };
}

// ── Feedback settings ────────────────────────────────────────────────────────
export function useFeedbackSettings() {
  return useQuery<FeedbackSettings>({ queryKey: ["feedback-settings"], queryFn: () => feedbackApi.settings.get() });
}
export const useUpdateFeedbackSettings = saver((d) => feedbackApi.settings.update(d), "feedback-settings", "Settings saved.");

// ── Daily reports ────────────────────────────────────────────────────────────
export function useDailyReports(params?: { mine?: boolean; author_id?: string }) {
  return useQuery<{ items: DailyReport[] }>({ queryKey: ["daily-reports", params], queryFn: () => feedbackApi.dailyReports.list(params) });
}
export const useSaveDailyReport = saver(
  (v: { id?: string; data: object }) => (v.id ? feedbackApi.dailyReports.update(v.id, v.data) : feedbackApi.dailyReports.create(v.data)),
  "daily-reports", "Report saved.",
);
export const useDeleteDailyReport = saver((id: string) => feedbackApi.dailyReports.remove(id), "daily-reports", "Report deleted.");

// ── Student daily reports ────────────────────────────────────────────────────
export function useStudentDailyReports(params?: { student_id?: string }) {
  return useQuery<{ items: StudentDailyReport[] }>({ queryKey: ["student-daily-reports", params], queryFn: () => feedbackApi.studentDailyReports.list(params) });
}
export const useSaveStudentDailyReport = saver(
  (v: { id?: string; data: object }) => (v.id ? feedbackApi.studentDailyReports.update(v.id, v.data) : feedbackApi.studentDailyReports.create(v.data)),
  "student-daily-reports", "Report saved.",
);
export const useDeleteStudentDailyReport = saver((id: string) => feedbackApi.studentDailyReports.remove(id), "student-daily-reports", "Report deleted.");

// ── CRM ──────────────────────────────────────────────────────────────────────
export function useCrmContacts(params?: { stage?: string }) {
  return useQuery<{ items: CRMContact[] }>({ queryKey: ["crm-contacts", params], queryFn: () => feedbackApi.crm.list(params) });
}
export const useSaveCrmContact = saver(
  (v: { id?: string; data: object }) => (v.id ? feedbackApi.crm.update(v.id, v.data) : feedbackApi.crm.create(v.data)),
  "crm-contacts", "Contact saved.",
);
export const useDeleteCrmContact = saver((id: string) => feedbackApi.crm.remove(id), "crm-contacts", "Contact deleted.");
