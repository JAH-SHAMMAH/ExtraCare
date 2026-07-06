"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { pastoralApi, medicalApi } from "@/lib/api";
import type {
  Hostel, BoardingAllocation, ExeatRequest, MentorReport, StudentMedicalRecord, Paginated,
} from "@/types";

// ── Hostels + Boarding ──────────────────────────────────────────────────────────

export function useHostels() {
  return useQuery<Paginated<Hostel>>({ queryKey: ["hostels"], queryFn: () => pastoralApi.hostels.list() });
}
export function useHostelAllocations(hostelId: string | null) {
  return useQuery<BoardingAllocation[]>({
    queryKey: ["hostels", hostelId, "allocations"],
    queryFn: () => pastoralApi.hostels.allocations(hostelId as string),
    enabled: !!hostelId,
  });
}
export function useCreateHostel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => pastoralApi.hostels.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hostels"] }); toast.success("Hostel saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save hostel."),
  });
}
export function useUpdateHostel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => pastoralApi.hostels.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hostels"] }); toast.success("Hostel updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useDeleteHostel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pastoralApi.hostels.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hostels"] }); toast.success("Hostel removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}
export function useAllocateBoarder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => pastoralApi.allocations.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hostels"] }); toast.success("Boarder allocated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to allocate."),
  });
}
export function useDeallocateBoarder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pastoralApi.allocations.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["hostels"] }); toast.success("Boarder removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}

// ── Exeat ────────────────────────────────────────────────────────────────────

export function useExeats(params?: { status?: string }) {
  return useQuery<Paginated<ExeatRequest>>({ queryKey: ["exeats", params], queryFn: () => pastoralApi.exeats.list(params) });
}
export function useCreateExeat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => pastoralApi.exeats.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["exeats"] }); toast.success("Exeat requested."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to request exeat."),
  });
}
export function useUpdateExeat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => pastoralApi.exeats.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["exeats"] }); toast.success("Exeat updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useApproveExeat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data?: object }) => pastoralApi.exeats.approve(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["exeats"] }); toast.success("Exeat approved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "You can’t authorise this exeat."),
  });
}
export function useRejectExeat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data?: object }) => pastoralApi.exeats.reject(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["exeats"] }); toast.success("Exeat rejected."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "You can’t authorise this exeat."),
  });
}
export function useReturnExeat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pastoralApi.exeats.markReturned(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["exeats"] }); toast.success("Marked returned."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}

// ── Mentor Reports ────────────────────────────────────────────────────────────

export function useMentorReports(params?: { student_id?: string; mentor_id?: string }) {
  return useQuery<Paginated<MentorReport>>({ queryKey: ["mentor-reports", params], queryFn: () => pastoralApi.mentorReports.list(params) });
}
export function useCreateMentorReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => pastoralApi.mentorReports.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["mentor-reports"] }); toast.success("Report saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save report."),
  });
}
export function useUpdateMentorReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => pastoralApi.mentorReports.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["mentor-reports"] }); toast.success("Report updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useDeleteMentorReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pastoralApi.mentorReports.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["mentor-reports"] }); toast.success("Report removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}

// ── Medicals (confidential) ───────────────────────────────────────────────────

export function useMedicalRecords(params?: { student_id?: string; record_type?: string }) {
  return useQuery<Paginated<StudentMedicalRecord>>({ queryKey: ["medical", params], queryFn: () => medicalApi.list(params) });
}
export function useCreateMedicalRecord() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => medicalApi.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["medical"] }); toast.success("Record saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to save record."),
  });
}
export function useUpdateMedicalRecord() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => medicalApi.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["medical"] }); toast.success("Record updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useDeleteMedicalRecord() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => medicalApi.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["medical"] }); toast.success("Record removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}
