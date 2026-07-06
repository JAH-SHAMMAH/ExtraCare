"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { academicsApi, schoolApi } from "@/lib/api";
import type {
  SubjectSelection, Transcript, ReportApproval, Recognition,
  HouseLeaderboardRow, Paginated,
} from "@/types";

// Subjects for the selection picker. Reuses /school/subjects (school:subjects:read).
export function useSubjectOptions() {
  return useQuery<any>({
    queryKey: ["subjects", "options"],
    queryFn: () => schoolApi.subjects.list({ page_size: 100 }),
    staleTime: 60_000,
  });
}

// ── Subject Selection ──────────────────────────────────────────────────────────

export function useSubjectSelections(params?: { student_id?: string; subject_id?: string; status?: string }) {
  return useQuery<Paginated<SubjectSelection>>({
    queryKey: ["subject-selections", params],
    queryFn: () => academicsApi.subjectSelections.list(params),
  });
}
export function useCreateSelection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => academicsApi.subjectSelections.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["subject-selections"] }); toast.success("Selection saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save selection."),
  });
}
export function useUpdateSelection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => academicsApi.subjectSelections.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["subject-selections"] }); toast.success("Selection updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useDeleteSelection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => academicsApi.subjectSelections.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["subject-selections"] }); toast.success("Selection removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}

// ── Transcripts ────────────────────────────────────────────────────────────────

export function useTranscripts(params?: { student_id?: string }) {
  return useQuery<Paginated<Transcript>>({
    queryKey: ["transcripts", params],
    queryFn: () => academicsApi.transcripts.list(params),
  });
}
export function useCreateTranscript() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => academicsApi.transcripts.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["transcripts"] }); toast.success("Transcript created."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to create transcript."),
  });
}
export function useUpdateTranscript() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => academicsApi.transcripts.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["transcripts"] }); toast.success("Transcript updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update transcript."),
  });
}
export function useDeleteTranscript() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => academicsApi.transcripts.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["transcripts"] }); toast.success("Transcript removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove transcript."),
  });
}
export function useAddTranscriptEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => academicsApi.transcripts.addEntry(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["transcripts"] }); toast.success("Entry added."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add entry."),
  });
}
export function useDeleteTranscriptEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, entryId }: { id: string; entryId: string }) => academicsApi.transcripts.removeEntry(id, entryId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["transcripts"] }); toast.success("Entry removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove entry."),
  });
}

// ── Report Workflow ──────────────────────────────────────────────────────────

export function useReportWorkflow(params?: { stage?: string }) {
  return useQuery<Paginated<ReportApproval>>({
    queryKey: ["report-workflow", params],
    queryFn: () => academicsApi.reportWorkflow.list(params),
  });
}
export function useCreateReportWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => academicsApi.reportWorkflow.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["report-workflow"] }); toast.success("Workflow created."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to create workflow."),
  });
}
export function useUpdateReportWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => academicsApi.reportWorkflow.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["report-workflow"] }); toast.success("Stage updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update stage."),
  });
}
export function useDeleteReportWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => academicsApi.reportWorkflow.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["report-workflow"] }); toast.success("Workflow removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove workflow."),
  });
}

// ── Merit & Awards (Recognition) ────────────────────────────────────────────────

export function useRecognitions(params?: { type?: string; student_id?: string; house?: string; term?: string }) {
  return useQuery<Paginated<Recognition>>({
    queryKey: ["recognitions", params],
    queryFn: () => academicsApi.recognitions.list(params),
  });
}
export function useLeaderboard(params?: { term?: string }) {
  return useQuery<{ houses: HouseLeaderboardRow[] }>({
    queryKey: ["recognitions", "leaderboard", params],
    queryFn: () => academicsApi.recognitions.leaderboard(params),
  });
}
export function useCreateRecognition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => academicsApi.recognitions.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["recognitions"] }); toast.success("Recorded."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to record."),
  });
}
export function useUpdateRecognition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => academicsApi.recognitions.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["recognitions"] }); toast.success("Updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useDeleteRecognition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => academicsApi.recognitions.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["recognitions"] }); toast.success("Removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}
