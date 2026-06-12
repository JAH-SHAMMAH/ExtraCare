"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { messengerApi } from "@/lib/api";
import type { ChatMessage, Conversation, UploadResponse } from "@/types";

const STALE_MS = 15_000;

export function useConversations() {
  return useQuery<Conversation[]>({
    queryKey: ["messenger", "conversations"],
    queryFn: messengerApi.conversations.list,
    staleTime: STALE_MS,
  });
}

export function useCreateConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: messengerApi.conversations.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["messenger", "conversations"] }),
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to start conversation."),
  });
}

export function useMessages(conversation_id: string | null) {
  return useQuery<ChatMessage[]>({
    queryKey: ["messenger", "messages", conversation_id],
    queryFn: () => messengerApi.messages.list(conversation_id as string),
    enabled: !!conversation_id,
    staleTime: STALE_MS,
  });
}

export function useSendMessage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: messengerApi.messages.create,
    onSuccess: (msg: ChatMessage) => {
      qc.setQueryData<ChatMessage[]>(
        ["messenger", "messages", msg.conversation_id],
        (prev) => {
          if (!prev) return [msg];
          if (prev.some((m) => m.id === msg.id)) return prev;
          return [...prev, msg];
        },
      );
      qc.invalidateQueries({ queryKey: ["messenger", "conversations"] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Failed to send message."),
  });
}

export function useUploadMedia() {
  return useMutation<UploadResponse, unknown, File>({
    mutationFn: (file: File) => messengerApi.upload(file),
    onError: (e: any) => toast.error(e?.response?.data?.detail || "Upload failed."),
  });
}

/**
 * Lifetime-of-the-chat-page WebSocket. Auto-reconnects with back-off so a
 * dropped connection (wifi switch, laptop lid) heals without the user
 * refreshing. Every inbound `message.new` event is merged into the React
 * Query cache for its conversation — the UI re-renders with no REST round-
 * trip.
 */
export function useMessengerSocket() {
  const qc = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const [connected, setConnected] = useState(false);

  const onMessage = useCallback(
    (raw: MessageEvent<string>) => {
      try {
        const data = JSON.parse(raw.data);
        if (data.event !== "message.new" || !data.message) return;
        const msg: ChatMessage = data.message;
        qc.setQueryData<ChatMessage[]>(
          ["messenger", "messages", msg.conversation_id],
          (prev) => {
            if (!prev) return [msg];
            if (prev.some((m) => m.id === msg.id)) return prev;
            return [...prev, msg];
          },
        );
        qc.invalidateQueries({ queryKey: ["messenger", "conversations"] });
      } catch {
        // Non-JSON frame or malformed event — ignore; the server won't send one.
      }
    },
    [qc],
  );

  useEffect(() => {
    let closed = false;

    const connect = () => {
      if (closed) return;
      const url = messengerApi.wsUrl();
      const ws = new WebSocket(url);
      wsRef.current = ws;
      ws.onopen = () => {
        retriesRef.current = 0;
        setConnected(true);
      };
      ws.onmessage = onMessage;
      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        if (closed) return;
        // Exponential back-off, capped at 10s so we don't hammer on a long outage.
        const delay = Math.min(1000 * 2 ** retriesRef.current, 10_000);
        retriesRef.current += 1;
        setTimeout(connect, delay);
      };
      ws.onerror = () => ws.close();
    };

    connect();

    return () => {
      closed = true;
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [onMessage]);

  const send = useCallback((payload: object) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload));
      return true;
    }
    return false;
  }, []);

  return { connected, send };
}
