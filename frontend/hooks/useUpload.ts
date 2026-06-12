"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { uploadApi } from "@/lib/api";

export function useUploadAvatar() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadApi.avatar(file),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["me"] });
      toast.success("Avatar updated.");
      return data;
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to upload avatar."),
  });
}

export function useUploadDocument() {
  return useMutation({
    mutationFn: ({ file, category }: { file: File; category?: string }) =>
      uploadApi.document(file, category),
    onSuccess: () => toast.success("Document uploaded."),
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to upload document."),
  });
}
