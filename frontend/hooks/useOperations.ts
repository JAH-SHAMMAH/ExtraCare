"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { operationsApi } from "@/lib/api";
import type { CalendarEvent, Facility, FacilityBooking, VisitorLog, StudentCollection, Paginated } from "@/types";

function inv(qc: ReturnType<typeof useQueryClient>, keys: string[]) {
  keys.forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
}

// ── Calendar ────────────────────────────────────────────────────────────────────

export function useCalendar() {
  return useQuery<Paginated<CalendarEvent>>({ queryKey: ["calendar"], queryFn: () => operationsApi.calendar.list() });
}
export function useCreateEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => operationsApi.calendar.create(data),
    onSuccess: () => { inv(qc, ["calendar"]); toast.success("Event added."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add event."),
  });
}
export function useDeleteEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => operationsApi.calendar.remove(id),
    onSuccess: () => { inv(qc, ["calendar"]); toast.success("Event removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}

// ── Facilities ──────────────────────────────────────────────────────────────────

export function useFacilities() {
  return useQuery<Paginated<Facility>>({ queryKey: ["facilities"], queryFn: () => operationsApi.facilities.list() });
}
export function useFacilityBookings(id: string | null) {
  return useQuery<FacilityBooking[]>({ queryKey: ["facilities", id, "bookings"], queryFn: () => operationsApi.facilities.bookings(id as string), enabled: !!id });
}
export function useCreateFacility() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => operationsApi.facilities.create(data),
    onSuccess: () => { inv(qc, ["facilities"]); toast.success("Facility added."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to add facility."),
  });
}
export function useUpdateFacility() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => operationsApi.facilities.update(id, data),
    onSuccess: () => { inv(qc, ["facilities"]); toast.success("Facility updated."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update."),
  });
}
export function useDeleteFacility() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => operationsApi.facilities.remove(id),
    onSuccess: () => { inv(qc, ["facilities"]); toast.success("Facility removed."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}
export function useBookFacility() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => operationsApi.facilities.book(id, data),
    onSuccess: () => { inv(qc, ["facilities"]); toast.success("Booked."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to book."),
  });
}
export function useCancelBooking() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (bookingId: string) => operationsApi.facilities.cancelBooking(bookingId),
    onSuccess: () => { inv(qc, ["facilities"]); toast.success("Booking cancelled."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to cancel."),
  });
}

// ── Visitors + Collections (safeguarding) ────────────────────────────────────────

export function useVisitors(params?: { status?: string }) {
  return useQuery<Paginated<VisitorLog>>({ queryKey: ["visitors", params], queryFn: () => operationsApi.visitors.list(params) });
}
export function useSignInVisitor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => operationsApi.visitors.signIn(data),
    onSuccess: () => { inv(qc, ["visitors"]); toast.success("Visitor signed in."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to sign in."),
  });
}
export function useSignOutVisitor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => operationsApi.visitors.signOut(id),
    onSuccess: () => { inv(qc, ["visitors"]); toast.success("Signed out."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to sign out."),
  });
}
export function useDeleteVisitor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => operationsApi.visitors.remove(id),
    onSuccess: () => { inv(qc, ["visitors"]); toast.success("Record removed (audited)."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}

export function useCollections() {
  return useQuery<Paginated<StudentCollection>>({ queryKey: ["collections"], queryFn: () => operationsApi.collections.list() });
}
export function useRecordCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => operationsApi.collections.create(data),
    onSuccess: () => { inv(qc, ["collections"]); toast.success("Collection recorded."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to record."),
  });
}
export function useDeleteCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => operationsApi.collections.remove(id),
    onSuccess: () => { inv(qc, ["collections"]); toast.success("Record removed (audited)."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to remove."),
  });
}
