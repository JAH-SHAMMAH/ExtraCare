"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { behaviourApi } from "@/lib/api";

// ── Categories ("Manage behaviourTracker") ───────────────────────────────────

export function useBehaviourCategories() {
  return useQuery({ queryKey: ["behaviour-categories"], queryFn: () => behaviourApi.categories.list() });
}

export function useSaveBehaviourCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id?: string; data: object }) =>
      id ? behaviourApi.categories.update(id, data) : behaviourApi.categories.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["behaviour-categories"] }); toast.success("Category saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn't save the category."),
  });
}

export function useDeleteBehaviourCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => behaviourApi.categories.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["behaviour-categories"] }); toast.success("Category deleted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn't delete the category."),
  });
}

// ── Sub-categories ("Sub-manage behaviourTracker") ───────────────────────────

export function useBehaviourSubcategories(category_id?: string) {
  return useQuery({
    queryKey: ["behaviour-subcategories", category_id ?? "all"],
    queryFn: () => behaviourApi.subcategories.list(category_id),
  });
}

export function useSaveBehaviourSubcategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id?: string; data: object }) =>
      id ? behaviourApi.subcategories.update(id, data) : behaviourApi.subcategories.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["behaviour-subcategories"] }); toast.success("Sub-category saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn't save the sub-category."),
  });
}

export function useDeleteBehaviourSubcategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => behaviourApi.subcategories.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["behaviour-subcategories"] }); toast.success("Sub-category deleted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn't delete the sub-category."),
  });
}

// ── Levels ("Manage behaviour levels") ───────────────────────────────────────

export function useBehaviourLevels() {
  return useQuery({ queryKey: ["behaviour-levels"], queryFn: () => behaviourApi.levels.list() });
}

export function useSaveBehaviourLevel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id?: string; data: object }) =>
      id ? behaviourApi.levels.update(id, data) : behaviourApi.levels.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["behaviour-levels"] }); toast.success("Level saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn't save the level."),
  });
}

export function useDeleteBehaviourLevel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => behaviourApi.levels.remove(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["behaviour-levels"] }); toast.success("Level deleted."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn't delete the level."),
  });
}

// ── Settings ("BehaviourTracker settings") ───────────────────────────────────

export function useBehaviourSettings() {
  return useQuery({ queryKey: ["behaviour-settings"], queryFn: () => behaviourApi.settings.get() });
}

export function useUpdateBehaviourSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: object) => behaviourApi.settings.update(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["behaviour-settings"] }); toast.success("Settings saved."); },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Couldn't save settings."),
  });
}
