"use client";

import { useRef, useState } from "react";
import {
  Heart, MessageCircle, Image as ImageIcon, Film, Loader2, Trash2,
  Send, X, Newspaper,
} from "lucide-react";
import { toast } from "sonner";
import {
  usePosts, useCreatePost, useDeletePost, useToggleLike,
  useComments, useCreateComment, useDeleteComment,
} from "@/hooks/useFeed";
import { useAuthStore } from "@/lib/store";
import { messengerApi } from "@/lib/api";
import { cn, getInitials, resolveMediaUrl, timeAgo } from "@/lib/utils";
import type { FeedPost, UploadResponse } from "@/types";

export default function NewsFeedPage() {
  const { data: posts = [], isLoading } = usePosts(30);
  const { user } = useAuthStore();

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-slate-50">
      <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">
        <header className="flex items-center gap-2">
          <Newspaper className="w-5 h-5 text-indigo-600" />
          <h1 className="text-lg font-semibold text-slate-800">News Feed</h1>
        </header>

        <Composer />

        {isLoading ? (
          <div className="flex items-center justify-center py-10 text-slate-400">
            <Loader2 className="w-5 h-5 animate-spin" />
          </div>
        ) : posts.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="space-y-4">
            {posts.map((p) => (
              <PostCard key={p.id} post={p} currentUserId={user?.id} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Composer ──────────────────────────────────────────────────────────────

function Composer() {
  const [content, setContent] = useState("");
  const [media, setMedia] = useState<UploadResponse | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const create = useCreatePost();

  const reset = () => {
    setContent("");
    setMedia(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const isImage = f.type.startsWith("image/");
    const isVideo = f.type.startsWith("video/");
    if (!isImage && !isVideo) {
      toast.error("Only images or videos are allowed.");
      e.target.value = "";
      return;
    }
    setUploading(true);
    try {
      // Messenger's /upload endpoint is shared — no reason to maintain two.
      const res: UploadResponse = await messengerApi.upload(f);
      setMedia(res);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = content.trim();
    if (!text && !media) {
      toast.error("Say something or attach media first.");
      return;
    }
    await create.mutateAsync({
      content: text || undefined,
      media_url: media?.file_url,
      media_type: media ? (media.type as "image" | "video") : undefined,
    });
    reset();
  };

  const busy = create.isPending || uploading;

  return (
    <form
      onSubmit={submit}
      className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm space-y-3"
    >
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="Share an update with the team…"
        rows={3}
        className="w-full resize-none border-0 focus:ring-0 focus:outline-none text-sm placeholder:text-slate-400 text-slate-800"
      />

      {media && (
        <div className="relative rounded-xl overflow-hidden border border-slate-200 bg-slate-50">
          {media.type === "image" ? (
            <img src={resolveMediaUrl(media.file_url)} alt="" className="max-h-80 w-full object-contain" />
          ) : (
            <video src={resolveMediaUrl(media.file_url)} controls className="max-h-80 w-full" />
          )}
          <button
            type="button"
            onClick={() => setMedia(null)}
            className="absolute top-2 right-2 bg-white/90 hover:bg-white rounded-full p-1 shadow"
            aria-label="Remove attachment"
          >
            <X className="w-4 h-4 text-slate-700" />
          </button>
        </div>
      )}

      <div className="flex items-center justify-between pt-2 border-t border-slate-100">
        <div className="flex items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept="image/*,video/*"
            className="hidden"
            onChange={handleFile}
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={busy}
            className="flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-indigo-600 px-2 py-1.5 rounded-md hover:bg-slate-50 disabled:opacity-50"
          >
            <ImageIcon className="w-4 h-4" />
            Image
          </button>
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={busy}
            className="flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-indigo-600 px-2 py-1.5 rounded-md hover:bg-slate-50 disabled:opacity-50"
          >
            <Film className="w-4 h-4" />
            Video
          </button>
          {uploading && (
            <span className="flex items-center gap-1 text-xs text-slate-500">
              <Loader2 className="w-3 h-3 animate-spin" /> uploading…
            </span>
          )}
        </div>

        <button
          type="submit"
          disabled={busy || (!content.trim() && !media)}
          className="flex items-center gap-1.5 bg-indigo-600 text-white text-sm font-medium px-4 py-1.5 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {create.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          Post
        </button>
      </div>
    </form>
  );
}

// ── Post card ─────────────────────────────────────────────────────────────

function PostCard({ post, currentUserId }: { post: FeedPost; currentUserId?: string }) {
  const [commentsOpen, setCommentsOpen] = useState(false);
  const toggleLike = useToggleLike();
  const del = useDeletePost();

  const handleDelete = async () => {
    if (!confirm("Delete this post?")) return;
    await del.mutateAsync(post.id);
  };

  const isAuthor = currentUserId && currentUserId === post.user_id;

  return (
    <article className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
      <header className="flex items-center gap-3 px-4 pt-4">
        <Avatar name={post.author_name} url={post.author_avatar_url} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-800 truncate">
            {post.author_name || "Unknown"}
          </p>
          <p className="text-xs text-slate-400">{timeAgo(post.created_at)}</p>
        </div>
        {isAuthor && (
          <button
            onClick={handleDelete}
            disabled={del.isPending}
            className="text-slate-400 hover:text-red-500 p-1.5 rounded-md hover:bg-red-50 disabled:opacity-50"
            aria-label="Delete post"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </header>

      {post.content && (
        <p className="px-4 pt-3 text-sm text-slate-700 whitespace-pre-wrap break-words">
          {post.content}
        </p>
      )}

      {post.media_url && post.media_type === "image" && (
        <img
          src={resolveMediaUrl(post.media_url)}
          alt=""
          className="w-full max-h-[32rem] object-contain bg-slate-50 mt-3"
        />
      )}
      {post.media_url && post.media_type === "video" && (
        <video
          src={resolveMediaUrl(post.media_url)}
          controls
          className="w-full max-h-[32rem] bg-black mt-3"
        />
      )}

      <footer className="px-4 py-3 flex items-center gap-5 border-t border-slate-100 mt-3">
        <button
          onClick={() => toggleLike.mutate({ id: post.id, liked: post.liked_by_me })}
          disabled={toggleLike.isPending}
          className={cn(
            "flex items-center gap-1.5 text-sm font-medium transition-colors",
            post.liked_by_me ? "text-rose-600" : "text-slate-500 hover:text-rose-500",
          )}
        >
          <Heart className={cn("w-4 h-4", post.liked_by_me && "fill-current")} />
          {post.like_count}
        </button>
        <button
          onClick={() => setCommentsOpen((v) => !v)}
          className="flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-indigo-600"
        >
          <MessageCircle className="w-4 h-4" />
          {post.comment_count}
        </button>
      </footer>

      {commentsOpen && <CommentSection postId={post.id} currentUserId={currentUserId} />}
    </article>
  );
}

// ── Comments ──────────────────────────────────────────────────────────────

function CommentSection({ postId, currentUserId }: { postId: string; currentUserId?: string }) {
  const { data: comments = [], isLoading } = useComments(postId);
  const create = useCreateComment(postId);
  const del = useDeleteComment(postId);
  const [draft, setDraft] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text) return;
    await create.mutateAsync(text);
    setDraft("");
  };

  return (
    <section className="border-t border-slate-100 bg-slate-50/50 px-4 py-3 space-y-3">
      {isLoading ? (
        <div className="text-xs text-slate-400 flex items-center gap-1">
          <Loader2 className="w-3 h-3 animate-spin" /> loading comments…
        </div>
      ) : comments.length === 0 ? (
        <p className="text-xs text-slate-400">Be the first to comment.</p>
      ) : (
        comments.map((c) => (
          <div key={c.id} className="flex items-start gap-2">
            <Avatar name={c.author_name} url={c.author_avatar_url} size="sm" />
            <div className="flex-1 min-w-0">
              <div className="bg-white border border-slate-200 rounded-xl px-3 py-2">
                <p className="text-xs font-semibold text-slate-700">{c.author_name || "Unknown"}</p>
                <p className="text-sm text-slate-700 whitespace-pre-wrap break-words">{c.content}</p>
              </div>
              <div className="flex items-center gap-3 mt-0.5 px-1">
                <span className="text-[10px] text-slate-400">{timeAgo(c.created_at)}</span>
                {currentUserId === c.user_id && (
                  <button
                    onClick={() => del.mutate(c.id)}
                    className="text-[10px] text-slate-400 hover:text-red-500"
                  >
                    delete
                  </button>
                )}
              </div>
            </div>
          </div>
        ))
      )}

      <form onSubmit={submit} className="flex items-center gap-2 pt-1">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Write a comment…"
          className="flex-1 text-sm px-3 py-2 rounded-full bg-white border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 placeholder:text-slate-400"
        />
        <button
          type="submit"
          disabled={create.isPending || !draft.trim()}
          className="p-2 rounded-full bg-indigo-600 text-white disabled:opacity-50 hover:bg-indigo-700"
          aria-label="Send comment"
        >
          {create.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </button>
      </form>
    </section>
  );
}

// ── Pieces ────────────────────────────────────────────────────────────────

function Avatar({
  name, url, size = "md",
}: { name: string | null; url: string | null; size?: "sm" | "md" }) {
  const px = size === "sm" ? "w-7 h-7 text-[10px]" : "w-10 h-10 text-xs";
  if (url) {
    return (
      <img
        src={resolveMediaUrl(url)}
        alt={name || ""}
        className={cn(px, "rounded-full object-cover bg-slate-100")}
      />
    );
  }
  return (
    <div
      className={cn(
        px,
        "rounded-full bg-indigo-100 text-indigo-700 font-semibold flex items-center justify-center",
      )}
    >
      {getInitials(name || "?")}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="bg-white border border-dashed border-slate-200 rounded-2xl p-10 text-center">
      <Newspaper className="w-10 h-10 mx-auto mb-3 text-slate-300" />
      <p className="text-sm font-medium text-slate-600">No posts yet.</p>
      <p className="text-xs text-slate-400 mt-1">
        Share the first update with your organisation.
      </p>
    </div>
  );
}
