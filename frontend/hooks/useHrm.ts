"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { hrApi } from "@/lib/api";
import type { HRProfile, HRBirthday, HREvent, HROverview } from "@/types";

// ── Profile ──────────────────────────────────────────────────────────────────

export function useMyHrProfile() {
  return useQuery<HRProfile>({
    queryKey: ["hr", "me"],
    queryFn: hrApi.me.get,
  });
}

export function useUpdateMyHrProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: hrApi.me.update,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "me"] });
      qc.invalidateQueries({ queryKey: ["hr", "overview"] });
      toast.success("Profile updated.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update profile."),
  });
}

export function useHrProfile(userId: string | undefined) {
  return useQuery<HRProfile>({
    queryKey: ["hr", "profiles", userId],
    queryFn: () => hrApi.profiles.get(userId as string),
    enabled: !!userId,
  });
}

// ── Overview / Birthdays / Events ────────────────────────────────────────────

export function useHrOverview() {
  return useQuery<HROverview>({
    queryKey: ["hr", "overview"],
    queryFn: hrApi.overview,
  });
}

export function useHrBirthdays(month?: number) {
  return useQuery<HRBirthday[]>({
    queryKey: ["hr", "birthdays", month ?? "current"],
    queryFn: () => hrApi.birthdays(month),
  });
}

export function useHrEvents(params?: { upcoming_only?: boolean; limit?: number }) {
  return useQuery<HREvent[]>({
    queryKey: ["hr", "events", params],
    queryFn: () => hrApi.events.list(params),
  });
}

export function useCreateHrEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: hrApi.events.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "events"] });
      toast.success("Event created.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to create event."),
  });
}

export function useUpdateHrEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: object }) => hrApi.events.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "events"] });
      toast.success("Event updated.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update event."),
  });
}

export function useDeleteHrEvent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: hrApi.events.delete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["hr", "events"] });
      toast.success("Event deleted.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to delete event."),
  });
}
