"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { enrollmentApi, schoolApi } from "@/lib/api";
import type {
  AdmissionApplication, EntranceExam, EntranceExamResult,
  PromotionRecord, TransferRecord, Paginated,
} from "@/types";

// Classes for the promotion from/to selectors. Reuses the existing
// /school/classes endpoint (school:classes:read, covered by school:read).
export function useClassOptions() {
  return useQuery<any>({
    queryKey: ["classes", "options"],
    queryFn: () => schoolApi.classes.list({ page_size: 100 }),
    staleTime: 60_000,
  });
}

// Students in a class — feeds the promotion roster selection.
export function useClassStudents(classId: string | null) {
  return useQuery<any>({
    queryKey: ["students", "by-class", classId],
    queryFn: () => schoolApi.students.list({ class_id: classId, page_size: 100 }),
    enabled: !!classId,
  });
}

// ── Admission Applications ─────────────────────────────────────────────────────

export function useApplications(params?: { status?: string; search?: string; page?: number; page_size?: number }) {
  return useQuery<Paginated<AdmissionApplication>>({
    queryKey: ["applications", params],
    queryFn: () => enrollmentApi.applications.list(params),
  });
}

export function useCreateApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => enrollmentApi.applications.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["applications"] }); toast.success("Application saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save application."),
  });
}

export function useUpdateApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => enrollmentApi.applications.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["applications"] }); toast.success("Application updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update application."),
  });
}

export function useDeleteApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => enrollmentApi.applications.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["applications"] }); toast.success("Application removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove application."),
  });
}

export function useAdmitApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data?: object }) => enrollmentApi.applications.admit(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["students"] });
      toast.success("Applicant admitted — added to the student roster.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to admit applicant."),
  });
}

// ── Entrance Exams ─────────────────────────────────────────────────────────────

export function useEntranceExams(params?: { status?: string; page?: number; page_size?: number }) {
  return useQuery<Paginated<EntranceExam>>({
    queryKey: ["entrance-exams", params],
    queryFn: () => enrollmentApi.entranceExams.list(params),
  });
}

export function useCreateEntranceExam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => enrollmentApi.entranceExams.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["entrance-exams"] }); toast.success("Exam saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save exam."),
  });
}

export function useUpdateEntranceExam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => enrollmentApi.entranceExams.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["entrance-exams"] }); toast.success("Exam updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update exam."),
  });
}

export function useDeleteEntranceExam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => enrollmentApi.entranceExams.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["entrance-exams"] }); toast.success("Exam removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove exam."),
  });
}

export function useExamResults(examId: string | null) {
  return useQuery<EntranceExamResult[]>({
    queryKey: ["exam-results", examId],
    queryFn: () => enrollmentApi.entranceExams.results.list(examId as string),
    enabled: !!examId,
  });
}

export function useAddExamResult() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ examId, data }: { examId: string; data: object }) => enrollmentApi.entranceExams.results.add(examId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exam-results"] });
      qc.invalidateQueries({ queryKey: ["entrance-exams"] });
      toast.success("Result recorded.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to record result."),
  });
}

export function useUpdateExamResult() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ resultId, data }: { resultId: string; data: object }) => enrollmentApi.entranceExams.results.update(resultId, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["exam-results"] }); toast.success("Result updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update result."),
  });
}

export function useDeleteExamResult() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (resultId: string) => enrollmentApi.entranceExams.results.remove(resultId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exam-results"] });
      qc.invalidateQueries({ queryKey: ["entrance-exams"] });
      toast.success("Result removed.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove result."),
  });
}

// ── Promotions ─────────────────────────────────────────────────────────────────

export function usePromotions(params?: { student_id?: string; page?: number; page_size?: number }) {
  return useQuery<Paginated<PromotionRecord>>({
    queryKey: ["promotions", params],
    queryFn: () => enrollmentApi.promotions.list(params),
  });
}

type PromotionInput = { student_ids: string[]; to_class_id?: string; from_class_id?: string; academic_year?: string; outcome?: string };

export function usePreviewPromotions() {
  return useMutation({
    mutationFn: (data: PromotionInput) => enrollmentApi.promotions.preview(data),
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to preview."),
  });
}

export function useCreatePromotions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: PromotionInput) => enrollmentApi.promotions.create(data),
    onSuccess: (created: PromotionRecord[]) => {
      qc.invalidateQueries({ queryKey: ["promotions"] });
      qc.invalidateQueries({ queryKey: ["students"] });
      toast.success(`${created.length} student(s) processed.`);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to process promotion."),
  });
}

export function useRevertPromotion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (batchId: string) => enrollmentApi.promotions.revert(batchId),
    onSuccess: (res: { reverted: number }) => {
      qc.invalidateQueries({ queryKey: ["promotions"] });
      qc.invalidateQueries({ queryKey: ["students"] });
      toast.success(`Run reverted — ${res.reverted} student(s) restored.`);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to revert run."),
  });
}

// ── Transfers ──────────────────────────────────────────────────────────────────

export function useTransfers(params?: { status?: string; page?: number; page_size?: number }) {
  return useQuery<Paginated<TransferRecord>>({
    queryKey: ["transfers", params],
    queryFn: () => enrollmentApi.transfers.list(params),
  });
}

export function useCreateTransfer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => enrollmentApi.transfers.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transfers"] });
      qc.invalidateQueries({ queryKey: ["students"] });
      toast.success("Transfer recorded.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to record transfer."),
  });
}

export function useUpdateTransfer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => enrollmentApi.transfers.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transfers"] });
      qc.invalidateQueries({ queryKey: ["students"] });
      toast.success("Transfer updated.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update transfer."),
  });
}
