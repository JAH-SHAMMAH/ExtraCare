"use client";

import { useRef, useState } from "react";
import {
  Heart, MessageCircle, Image as ImageIcon, Film, Loader2, Trash2,
  Send, X, Newspaper, Paperclip, FileText, ExternalLink, Link2, Plus, Lock,
} from "lucide-react";
import { toast } from "sonner";
import {
  usePosts, useCreatePost, useDeletePost, useToggleLike,
  useComments, useCreateComment, useDeleteComment,
} from "@/hooks/useFeed";
import { useAuthStore } from "@/lib/store";
import { messengerApi, uploadApi } from "@/lib/api";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { AudiencePicker } from "@/components/feed/AudiencePicker";
import { cn, getInitials, resolveMediaUrl, timeAgo } from "@/lib/utils";
import type { FeedPost, FeedAttachment, FeedAttachmentInput, AudienceUser, UploadResponse } from "@/types";

/**
 * Shared News Feed — the org social feed (posts, likes, comments). Single source
 * of truth reused by the standalone /news-feed page AND the dashboard home, so
 * there is never a second parallel feed to keep in sync. Renders the publish
 * composer + the post list (with its own loading / empty states). Callers own
 * the page chrome (header, width, background).
 */
export function NewsFeed({ limit = 30, showComposer = true }: { limit?: number; showComposer?: boolean }) {
  const { data: posts = [], isLoading } = usePosts(limit);
  const { user } = useAuthStore();

  return (
    <div className="space-y-4">
      {showComposer && <Composer />}
      {isLoading ? (
        <div className="flex items-center justify-center py-10 text-slate-400">
          <Loader2 className="w-5 h-5 animate-spin" />
        </div>
      ) : posts.length === 0 ? (
        <EmptyState />
      ) : (
        posts.map((p) => <PostCard key={p.id} post={p} currentUserId={user?.id} />)
      )}
    </div>
  );
}

// ── Composer ──────────────────────────────────────────────────────────────

// Documents the /upload/document endpoint accepts (see backend upload.py).
const DOC_ACCEPT = ".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/plain,text/csv";

function Composer() {
  const [content, setContent] = useState("");
  const [media, setMedia] = useState<UploadResponse | null>(null);
  // Non-inline attachments (documents + links). Image/video go through `media`.
  const [attachments, setAttachments] = useState<FeedAttachmentInput[]>([]);
  const [uploading, setUploading] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
  const [linkUrl, setLinkUrl] = useState("");
  const [linkTitle, setLinkTitle] = useState("");
  // Publish-To targeting (empty both = everyone). Only shown to users:read holders.
  const [audRoles, setAudRoles] = useState<string[]>([]);
  const [audUsers, setAudUsers] = useState<AudienceUser[]>([]);
  const canTarget = useHasPermission("users:read");
  // Genuinely distinct pickers so each button opens only its media type.
  const imageRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLInputElement>(null);
  const docRef = useRef<HTMLInputElement>(null);

  const create = useCreatePost();

  const reset = () => {
    setContent("");
    setMedia(null);
    setAttachments([]);
    setLinkOpen(false);
    setLinkUrl("");
    setLinkTitle("");
    setAudRoles([]);
    setAudUsers([]);
    if (imageRef.current) imageRef.current.value = "";
    if (videoRef.current) videoRef.current.value = "";
    if (docRef.current) docRef.current.value = "";
  };

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const isImage = f.type.startsWith("image/");
    const isVideo = f.type.startsWith("video/");
    if (!isImage && !isVideo) {
      toast.error("Only images or videos are allowed here — use the file button for documents.");
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

  const handleDoc = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      // Durable document upload (/upload/document) — accepts PDF/Word/Excel/CSV/text.
      const res: { url: string; filename: string } = await uploadApi.document(f);
      setAttachments((prev) => [
        ...prev,
        { kind: "file", url: res.url, filename: res.filename || f.name, mime_type: f.type, size_bytes: f.size },
      ]);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Document upload failed.");
    } finally {
      setUploading(false);
      if (docRef.current) docRef.current.value = "";
    }
  };

  const addLink = () => {
    let raw = linkUrl.trim();
    if (!raw) return;
    // Be forgiving — accept "example.com" and normalise to a real URL.
    if (!/^https?:\/\//i.test(raw)) raw = `https://${raw}`;
    try {
      new URL(raw);
    } catch {
      toast.error("Enter a valid URL.");
      return;
    }
    setAttachments((prev) => [...prev, { kind: "link", url: raw, title: linkTitle.trim() || raw }]);
    setLinkUrl("");
    setLinkTitle("");
    setLinkOpen(false);
  };

  const removeAttachment = (i: number) =>
    setAttachments((prev) => prev.filter((_, j) => j !== i));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = content.trim();
    if (!text && !media && attachments.length === 0) {
      toast.error("Say something or attach media, a document, or a link first.");
      return;
    }
    await create.mutateAsync({
      content: text || undefined,
      media_url: media?.file_url,
      media_type: media ? (media.type as "image" | "video") : undefined,
      attachments: attachments.length ? attachments : undefined,
      audience_roles: audRoles.length ? audRoles : undefined,
      audience_user_ids: audUsers.length ? audUsers.map((u) => u.id) : undefined,
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

      {attachments.length > 0 && (
        <div className="space-y-1.5">
          {attachments.map((a, i) => (
            <div key={i} className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
              {a.kind === "link"
                ? <Link2 className="w-4 h-4 text-indigo-600 shrink-0" />
                : <FileText className="w-4 h-4 text-indigo-600 shrink-0" />}
              <span className="text-sm text-slate-700 truncate flex-1">{a.kind === "link" ? (a.title || a.url) : a.filename}</span>
              <button
                type="button"
                onClick={() => removeAttachment(i)}
                className="text-slate-400 hover:text-red-500 shrink-0"
                aria-label="Remove attachment"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {linkOpen && (
        <div className="flex flex-col sm:flex-row items-stretch gap-2 rounded-xl border border-slate-200 bg-slate-50 p-2">
          <input
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addLink(); } }}
            placeholder="Paste a link (https://…)"
            className="flex-1 text-sm px-3 py-2 rounded-lg bg-white border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 placeholder:text-slate-400"
            autoFocus
          />
          <input
            value={linkTitle}
            onChange={(e) => setLinkTitle(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addLink(); } }}
            placeholder="Label (optional)"
            className="sm:w-40 text-sm px-3 py-2 rounded-lg bg-white border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 placeholder:text-slate-400"
          />
          <button type="button" onClick={addLink} disabled={!linkUrl.trim()}
            className="flex items-center justify-center gap-1 bg-indigo-600 text-white text-sm font-medium px-3 py-2 rounded-lg hover:bg-indigo-700 disabled:opacity-50">
            <Plus className="w-4 h-4" /> Add
          </button>
        </div>
      )}

      <div className="flex items-center justify-between pt-2 border-t border-slate-100">
        <div className="flex items-center gap-2">
          <input ref={imageRef} type="file" accept="image/*" className="hidden" onChange={handleFile} />
          <input ref={videoRef} type="file" accept="video/*" className="hidden" onChange={handleFile} />
          <input ref={docRef} type="file" accept={DOC_ACCEPT} className="hidden" onChange={handleDoc} />
          <button
            type="button"
            onClick={() => imageRef.current?.click()}
            disabled={busy}
            className="flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-indigo-600 px-2 py-1.5 rounded-md hover:bg-slate-50 disabled:opacity-50"
          >
            <ImageIcon className="w-4 h-4" />
            Image
          </button>
          <button
            type="button"
            onClick={() => videoRef.current?.click()}
            disabled={busy}
            className="flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-indigo-600 px-2 py-1.5 rounded-md hover:bg-slate-50 disabled:opacity-50"
          >
            <Film className="w-4 h-4" />
            Video
          </button>
          <button
            type="button"
            onClick={() => docRef.current?.click()}
            disabled={busy}
            className="flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-indigo-600 px-2 py-1.5 rounded-md hover:bg-slate-50 disabled:opacity-50"
          >
            <Paperclip className="w-4 h-4" />
            File
          </button>
          <button
            type="button"
            onClick={() => setLinkOpen((v) => !v)}
            disabled={busy}
            className={cn(
              "flex items-center gap-1.5 text-xs font-medium px-2 py-1.5 rounded-md hover:bg-slate-50 disabled:opacity-50",
              linkOpen ? "text-indigo-600 bg-indigo-50" : "text-slate-600 hover:text-indigo-600",
            )}
          >
            <Link2 className="w-4 h-4" />
            Link
          </button>
          {uploading && (
            <span className="flex items-center gap-1 text-xs text-slate-500">
              <Loader2 className="w-3 h-3 animate-spin" /> uploading…
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {canTarget && (
            <AudiencePicker
              roles={audRoles}
              users={audUsers}
              onChange={(r, u) => { setAudRoles(r); setAudUsers(u); }}
              disabled={busy}
            />
          )}
          <button
            type="submit"
            disabled={busy || (!content.trim() && !media && attachments.length === 0)}
            className="flex items-center gap-1.5 bg-indigo-600 text-white text-sm font-medium px-4 py-1.5 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {create.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            Post
          </button>
        </div>
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
          <p className="text-xs text-slate-400 flex items-center gap-1.5">
            {timeAgo(post.created_at)}
            {((post.audience_roles?.length ?? 0) + (post.audience_user_ids?.length ?? 0) > 0) && (
              <span className="inline-flex items-center gap-0.5 text-indigo-500" title="Limited audience — not shared with everyone">
                <span aria-hidden>·</span><Lock className="w-3 h-3" />
              </span>
            )}
          </p>
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

      {(post.attachments ?? []).map((att) => <AttachmentView key={att.id} att={att} />)}

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

// Renders one post attachment. Documents ("file") get the "View Document" card
// (stacked-doc icon + View Document link); image/video render inline; link → card.
function AttachmentView({ att }: { att: FeedAttachment }) {
  const href = resolveMediaUrl(att.url);
  if (att.kind === "image") {
    return <img src={href} alt={att.filename || ""} className="w-full max-h-[32rem] object-contain bg-slate-50 mt-3" />;
  }
  if (att.kind === "video") {
    return <video src={href} controls className="w-full max-h-[32rem] bg-black mt-3" />;
  }
  if (att.kind === "link") {
    return (
      <a href={att.url} target="_blank" rel="noopener noreferrer"
         className="mx-4 mt-3 flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2.5 hover:bg-slate-50 transition-colors">
        <ExternalLink className="w-4 h-4 text-indigo-600 shrink-0" />
        <span className="text-sm text-indigo-700 truncate">{att.title || att.url}</span>
      </a>
    );
  }
  // "file" → View Document card
  return (
    <a href={href} target="_blank" rel="noopener noreferrer"
       className="mx-4 mt-3 flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 hover:bg-slate-100 transition-colors group">
      <div className="relative shrink-0">
        <FileText className="w-7 h-7 text-indigo-500" />
        <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-[3px] border border-white bg-indigo-400" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-700 truncate">{att.filename || att.title || "Document"}</p>
        <span className="text-xs font-semibold text-indigo-600 group-hover:underline">View Document</span>
      </div>
      <ExternalLink className="w-4 h-4 text-slate-400 shrink-0" />
    </a>
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
