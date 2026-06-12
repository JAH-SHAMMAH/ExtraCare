"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { feedApi } from "@/lib/api";
import type { FeedComment, FeedLikeToggle, FeedPost } from "@/types";

const STALE_MS = 15_000;

export function usePosts(limit = 20) {
  return useQuery<FeedPost[]>({
    queryKey: ["feed", "posts", { limit }],
    queryFn: () => feedApi.posts.list({ limit }),
    staleTime: STALE_MS,
  });
}

export function useCreatePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: feedApi.posts.create,
    onSuccess: (post: FeedPost) => {
      // Prepend to every cached page — the only query key variant currently
      // in flight is the single limit-bound list, but invalidating afterwards
      // keeps us safe if a future hook adds another filter.
      qc.setQueriesData<FeedPost[]>({ queryKey: ["feed", "posts"] }, (prev) =>
        prev ? [post, ...prev] : [post],
      );
      qc.invalidateQueries({ queryKey: ["feed", "posts"] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Could not publish post."),
  });
}

export function useDeletePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => feedApi.posts.remove(id),
    onSuccess: (_res, id) => {
      qc.setQueriesData<FeedPost[]>({ queryKey: ["feed", "posts"] }, (prev) =>
        prev ? prev.filter((p) => p.id !== id) : prev,
      );
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Could not delete post."),
  });
}

/**
 * Optimistic like/unlike. We flip the counter + flag in the cache
 * immediately, then reconcile with the server's authoritative response on
 * success. On failure we roll the cache back to the pre-mutation snapshot.
 */
export function useToggleLike() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, liked }: { id: string; liked: boolean }) => {
      const res: FeedLikeToggle = liked ? await feedApi.unlike(id) : await feedApi.like(id);
      return { id, ...res };
    },
    onMutate: async ({ id, liked }) => {
      await qc.cancelQueries({ queryKey: ["feed", "posts"] });
      const snapshot = qc.getQueriesData<FeedPost[]>({ queryKey: ["feed", "posts"] });
      qc.setQueriesData<FeedPost[]>({ queryKey: ["feed", "posts"] }, (prev) =>
        prev
          ? prev.map((p) =>
              p.id === id
                ? {
                    ...p,
                    liked_by_me: !liked,
                    like_count: Math.max(0, p.like_count + (liked ? -1 : 1)),
                  }
                : p,
            )
          : prev,
      );
      return { snapshot };
    },
    onError: (e: any, _vars, ctx) => {
      ctx?.snapshot?.forEach(([key, data]) => qc.setQueryData(key, data));
      toast.error(e?.response?.data?.detail || "Could not update like.");
    },
    onSuccess: ({ id, liked, like_count }) => {
      qc.setQueriesData<FeedPost[]>({ queryKey: ["feed", "posts"] }, (prev) =>
        prev
          ? prev.map((p) => (p.id === id ? { ...p, liked_by_me: liked, like_count } : p))
          : prev,
      );
    },
  });
}

export function useComments(post_id: string | null) {
  return useQuery<FeedComment[]>({
    queryKey: ["feed", "comments", post_id],
    queryFn: () => feedApi.comments.list(post_id as string),
    enabled: !!post_id,
    staleTime: STALE_MS,
  });
}

export function useCreateComment(post_id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (content: string) => feedApi.comments.create(post_id, { content }),
    onSuccess: (c: FeedComment) => {
      qc.setQueryData<FeedComment[]>(["feed", "comments", post_id], (prev) =>
        prev ? [...prev, c] : [c],
      );
      // Bump the comment_count in any cached post list so the feed card
      // updates without a full refetch.
      qc.setQueriesData<FeedPost[]>({ queryKey: ["feed", "posts"] }, (prev) =>
        prev
          ? prev.map((p) => (p.id === post_id ? { ...p, comment_count: p.comment_count + 1 } : p))
          : prev,
      );
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Could not post comment."),
  });
}

export function useDeleteComment(post_id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (comment_id: string) => feedApi.comments.remove(post_id, comment_id),
    onSuccess: (_res, comment_id) => {
      qc.setQueryData<FeedComment[]>(["feed", "comments", post_id], (prev) =>
        prev ? prev.filter((c) => c.id !== comment_id) : prev,
      );
      qc.setQueriesData<FeedPost[]>({ queryKey: ["feed", "posts"] }, (prev) =>
        prev
          ? prev.map((p) =>
              p.id === post_id ? { ...p, comment_count: Math.max(0, p.comment_count - 1) } : p,
            )
          : prev,
      );
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Could not delete comment."),
  });
}
