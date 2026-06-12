"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  MessageSquare, Send, Image as ImageIcon, Film, Paperclip,
  Users2, Globe, Loader2, Plus,
} from "lucide-react";
import {
  useConversations, useCreateConversation, useMessages, useSendMessage,
  useUploadMedia, useMessengerSocket,
} from "@/hooks/useMessenger";
import { useAuthStore } from "@/lib/store";
import { useUsers } from "@/hooks/useUsers";
import { resolveMediaUrl } from "@/lib/utils";
import type { ChatMessage, Conversation, MessageType } from "@/types";

export default function MessengerPage() {
  const { user } = useAuthStore();
  const { connected } = useMessengerSocket();
  const { data: conversations = [], isLoading: convLoading } = useConversations();

  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Auto-select the global room on first load so the user always sees
  // something. Picking the most-recently-active conversation instead would
  // hide the global room from fresh orgs.
  useEffect(() => {
    if (!selectedId && conversations.length > 0) {
      const global = conversations.find((c) => c.kind === "global");
      setSelectedId(global?.id ?? conversations[0].id);
    }
  }, [conversations, selectedId]);

  const selected = conversations.find((c) => c.id === selectedId) || null;

  return (
    <div className="h-[calc(100vh-4rem)] flex bg-slate-50">
      <ConversationSidebar
        conversations={conversations}
        loading={convLoading}
        selectedId={selectedId}
        onSelect={setSelectedId}
        currentUserId={user?.id}
      />
      <div className="flex-1 flex flex-col min-w-0">
        {selected ? (
          <ChatPane
            conversation={selected}
            currentUserId={user?.id}
            connected={connected}
          />
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-400">
            <div className="text-center">
              <MessageSquare className="w-10 h-10 mx-auto mb-3 text-slate-300" />
              <p className="text-sm">Select a conversation to start chatting.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Left column: conversation list ────────────────────────────────────────

function ConversationSidebar({
  conversations, loading, selectedId, onSelect, currentUserId,
}: {
  conversations: Conversation[];
  loading: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  currentUserId?: string;
}) {
  const [showNew, setShowNew] = useState(false);

  return (
    <aside className="w-80 border-r border-slate-200 bg-white flex flex-col">
      <header className="px-4 py-4 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-brand-600" />
          <h1 className="text-sm font-bold text-slate-900 uppercase tracking-wide">Messenger</h1>
        </div>
        <button
          onClick={() => setShowNew((s) => !s)}
          className="text-xs font-semibold text-brand-600 hover:text-brand-700 inline-flex items-center gap-1"
        >
          <Plus className="w-3.5 h-3.5" />
          New
        </button>
      </header>

      {showNew && (
        <NewDMForm
          currentUserId={currentUserId}
          onClose={(id) => {
            setShowNew(false);
            if (id) onSelect(id);
          }}
        />
      )}

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <p className="text-xs text-slate-400 p-4">Loading…</p>
        ) : conversations.length === 0 ? (
          <p className="text-xs text-slate-400 p-4">No conversations yet.</p>
        ) : (
          <ul>
            {conversations.map((c) => (
              <ConversationRow
                key={c.id}
                conv={c}
                active={c.id === selectedId}
                onClick={() => onSelect(c.id)}
                currentUserId={currentUserId}
              />
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}

function ConversationRow({
  conv, active, onClick, currentUserId,
}: {
  conv: Conversation;
  active: boolean;
  onClick: () => void;
  currentUserId?: string;
}) {
  const title = resolveTitle(conv, currentUserId);
  const Icon = conv.kind === "global" ? Globe : conv.kind === "group" ? Users2 : MessageSquare;
  return (
    <li>
      <button
        onClick={onClick}
        className={`w-full text-left px-4 py-3 border-b border-slate-100 transition ${
          active ? "bg-brand-50" : "hover:bg-slate-50"
        }`}
      >
        <div className="flex items-center gap-2">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
            active ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600"
          }`}>
            <Icon className="w-4 h-4" />
          </div>
          <div className="flex-1 min-w-0">
            <p className={`text-sm truncate ${active ? "font-bold text-brand-700" : "font-semibold text-slate-800"}`}>
              {title}
            </p>
            <p className="text-xs text-slate-500 truncate">
              {conv.last_message_preview || "No messages yet."}
            </p>
          </div>
          {conv.last_message_at && (
            <span className="text-[10px] text-slate-400 shrink-0">{formatShort(conv.last_message_at)}</span>
          )}
        </div>
      </button>
    </li>
  );
}

function NewDMForm({ onClose, currentUserId }: { onClose: (id: string | null) => void; currentUserId?: string }) {
  // Reuses the existing users list — avoids baking a messenger-specific
  // directory endpoint when /users already answers this.
  const { data: users = [], isLoading } = useUsers();
  const create = useCreateConversation();
  const [peer, setPeer] = useState("");

  const options = useMemo(
    () => (users as any[]).filter((u) => u.id !== currentUserId),
    [users, currentUserId],
  );

  const submit = () => {
    if (!peer) return;
    create.mutate(
      { kind: "direct", peer_id: peer },
      { onSuccess: (conv: Conversation) => onClose(conv.id) },
    );
  };

  return (
    <div className="px-4 py-3 border-b border-slate-100 bg-slate-50 space-y-2">
      <label className="block">
        <span className="text-[11px] font-semibold text-slate-600">Start DM with</span>
        <select
          value={peer}
          onChange={(e) => setPeer(e.target.value)}
          disabled={isLoading}
          className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="">Select a colleague…</option>
          {options.map((u) => (
            <option key={u.id} value={u.id}>{u.full_name} — {u.email}</option>
          ))}
        </select>
      </label>
      <div className="flex gap-2">
        <button
          onClick={submit}
          disabled={!peer || create.isPending}
          className="flex-1 bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold px-3 py-1.5 rounded-md disabled:opacity-50"
        >
          {create.isPending ? "Creating…" : "Start"}
        </button>
        <button onClick={() => onClose(null)} className="text-xs text-slate-500 hover:text-slate-700 px-2">
          Cancel
        </button>
      </div>
    </div>
  );
}

// ── Right column: chat pane ───────────────────────────────────────────────

function ChatPane({
  conversation, currentUserId, connected,
}: {
  conversation: Conversation;
  currentUserId?: string;
  connected: boolean;
}) {
  const { data: messages = [], isLoading } = useMessages(conversation.id);
  const send = useSendMessage();
  const upload = useUploadMedia();
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom whenever the message list grows. Using scrollHeight
  // after a layout commit (effect timing) avoids racing React's DOM updates.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length]);

  const title = resolveTitle(conversation, currentUserId);

  const submitText = () => {
    const content = draft.trim();
    if (!content) return;
    send.mutate({ conversation_id: conversation.id, type: "text", content });
    setDraft("");
  };

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const isVideo = f.type.startsWith("video/");
    const isImage = f.type.startsWith("image/");
    if (!isVideo && !isImage) return;
    const res = await upload.mutateAsync(f);
    const type: MessageType = isVideo ? "video" : "image";
    send.mutate({ conversation_id: conversation.id, type, file_url: res.file_url });
    e.target.value = "";
  };

  return (
    <>
      <header className="px-6 py-4 border-b border-slate-200 bg-white flex items-center justify-between">
        <div>
          <h2 className="text-sm font-black text-slate-900">{title}</h2>
          <p className="text-xs text-slate-500 capitalize">
            {conversation.kind} · {conversation.members.length} member{conversation.members.length === 1 ? "" : "s"}
          </p>
        </div>
        <span
          className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full ${
            connected ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"
          }`}
          title={connected ? "Live" : "Reconnecting…"}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-emerald-500" : "bg-slate-400 animate-pulse"}`} />
          {connected ? "Live" : "Offline"}
        </span>
      </header>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-4 space-y-3 bg-slate-50">
        {isLoading ? (
          <p className="text-xs text-slate-400">Loading messages…</p>
        ) : messages.length === 0 ? (
          <p className="text-xs text-slate-400 italic text-center py-10">
            No messages yet — be the first to say hello.
          </p>
        ) : (
          messages.map((m) => <MessageBubble key={m.id} msg={m} mine={m.sender_id === currentUserId} />)
        )}
      </div>

      <footer className="border-t border-slate-200 bg-white px-4 py-3">
        <form
          onSubmit={(e) => { e.preventDefault(); submitText(); }}
          className="flex items-center gap-2"
        >
          <input
            ref={fileRef}
            type="file"
            accept="image/*,video/*"
            onChange={handleFile}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={upload.isPending}
            title="Attach image or video"
            className="p-2 rounded-md text-slate-500 hover:text-brand-600 hover:bg-slate-100 disabled:opacity-50"
          >
            {upload.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Paperclip className="w-4 h-4" />}
          </button>
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Type a message…"
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
          />
          <button
            type="submit"
            disabled={!draft.trim() || send.isPending}
            className="bg-brand-600 hover:bg-brand-700 text-white px-3 py-2 rounded-md disabled:opacity-50"
          >
            {send.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </form>
      </footer>
    </>
  );
}

function MessageBubble({ msg, mine }: { msg: ChatMessage; mine: boolean }) {
  const side = mine ? "items-end" : "items-start";
  const bubble = mine
    ? "bg-brand-600 text-white"
    : "bg-white text-slate-800 border border-slate-200";

  return (
    <div className={`flex flex-col ${side}`}>
      {!mine && msg.sender_name && (
        <span className="text-[10px] font-semibold text-slate-500 mb-0.5 px-1">{msg.sender_name}</span>
      )}
      <div className={`max-w-[70%] rounded-2xl px-3 py-2 text-sm ${bubble}`}>
        {msg.type === "text" && <p className="whitespace-pre-wrap break-words">{msg.content}</p>}
        {msg.type === "image" && msg.file_url && (
          <img src={resolveMediaUrl(msg.file_url)} alt="" className="rounded-lg max-h-72 w-auto" />
        )}
        {msg.type === "video" && msg.file_url && (
          <video src={resolveMediaUrl(msg.file_url)} controls className="rounded-lg max-h-80 w-full" />
        )}
        {msg.type !== "text" && msg.content && (
          <p className="whitespace-pre-wrap break-words mt-1 text-xs opacity-90">{msg.content}</p>
        )}
      </div>
      <span className={`text-[10px] text-slate-400 mt-0.5 px-1 ${mine ? "text-right" : ""}`}>
        {formatTime(msg.created_at)}
      </span>
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────

function resolveTitle(conv: Conversation, currentUserId?: string): string {
  if (conv.kind === "global") return "Organisation";
  if (conv.kind === "group") return conv.title || "Group";
  const other = conv.members.find((m) => m.id !== currentUserId);
  return other?.full_name || "Direct message";
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function formatShort(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
