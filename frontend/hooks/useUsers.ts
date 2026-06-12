"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { usersApi } from "@/lib/api";
import type { UserStatus } from "@/types";

export function useUsers(params?: {
  page?: number;
  page_size?: number;
  search?: string;
  status?: UserStatus;
}) {
  return useQuery({
    queryKey: ["users", params],
    queryFn: () => usersApi.list(params),
  });
}

export function useUser(id: string) {
  return useQuery({
    queryKey: ["users", id],
    queryFn: () => usersApi.get(id),
    enabled: !!id,
  });
}

export function useAvailableRoles() {
  return useQuery({
    queryKey: ["users", "roles"],
    queryFn: () => usersApi.listRoles(),
  });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: usersApi.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      toast.success("User created successfully.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to create user."),
  });
}

export function useUpdateUserStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: UserStatus }) =>
      usersApi.updateStatus(id, status),
    onSuccess: (_, { status }) => {
      qc.invalidateQueries({ queryKey: ["users"] });
      toast.success(`User ${status}.`);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to update status."),
  });
}

export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: usersApi.delete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      toast.success("User removed.");
    },
  });
}

export function useInviteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: usersApi.invite,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      toast.success("Invitation sent.");
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to send invitation."),
  });
}
