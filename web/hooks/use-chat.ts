"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiRequestError } from "@/lib/api-client";
import type { Persona } from "@/lib/personas";
import type { ChatStatus, Source } from "@/lib/types";
import { usePolling } from "@/hooks/use-polling";
import { useLocalStorage } from "@/hooks/use-local-storage";

export interface ChatItem {
  id: string;
  role: "customer" | "assistant";
  content: string;
  sources?: Source[];
  outcome?: string | null;
  status?: ChatStatus;
  handoffReason?: string | null;
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const isUuid = (value: string): value is string => UUID_PATTERN.test(value);

// These phrases come from the agent's own reply templates in src/concierge/agent/nodes.py.
const PENDING_MARK = "sent a refund request";
const APPROVED_MARK = "has been approved";
const REJECTED_MARK = "couldn't approve";

const CONVERSATION_GONE =
  "That conversation was cleared. Send your message again to start a new one.";

function outcomeFromReply(content: string): string | null {
  if (content.includes(APPROVED_MARK)) return "refund_completed";
  if (content.includes(REJECTED_MARK)) return "refund_rejected";
  return null;
}

function newId(): string {
  return globalThis.crypto.randomUUID();
}

/** What is on screen belongs to one persona AND one conversation. */
function threadKey(personaId: string, conversationId: string | null): string {
  return `${personaId}:${conversationId ?? "new"}`;
}

interface UseChatOptions {
  persona: Persona;
  /** Called after any turn that may have changed the customer's bookings. */
  onBookingsMayHaveChanged?: () => void;
}

export interface ChatController {
  messages: ChatItem[];
  sending: boolean;
  awaitingApproval: boolean;
  error: string | null;
  send: (text: string) => Promise<void>;
  startNewConversation: () => void;
}

export function useChat({ persona, onBookingsMayHaveChanged }: UseChatOptions): ChatController {
  const [conversationId, setConversationId] = useLocalStorage<string>(
    `concierge:conversation:${persona.id}`,
    null,
    isUuid,
  );
  const [messages, setMessages] = useState<ChatItem[]>([]);
  const [sending, setSending] = useState(false);
  const [awaitingApproval, setAwaitingApproval] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // How many transcript messages existed when the refund went to a human.
  const pausedAtRef = useRef<number | null>(null);
  // Which persona + conversation the messages on screen belong to. Keeps a live reply (with its
  // citations and approval status) from being replaced by plain transcript text, and keeps one
  // persona's messages from showing under another.
  const loadedRef = useRef<string | null>(null);
  const personaRef = useRef(persona.id);

  const currentKey = threadKey(persona.id, conversationId);

  const forget = useCallback(() => {
    loadedRef.current = null;
    pausedAtRef.current = null;
    setMessages([]);
    setAwaitingApproval(false);
  }, []);

  useEffect(() => {
    if (loadedRef.current === currentKey) return;
    let cancelled = false;
    personaRef.current = persona.id;

    const restore = async () => {
      if (!conversationId) {
        loadedRef.current = currentKey;
        pausedAtRef.current = null;
        setMessages([]);
        setAwaitingApproval(false);
        return;
      }
      try {
        const transcript = await api.transcript(persona.id, conversationId);
        if (cancelled) return;
        loadedRef.current = currentKey;
        setMessages(
          transcript.map((message) => ({
            id: newId(),
            role: message.role,
            content: message.content,
            outcome: message.role === "assistant" ? outcomeFromReply(message.content) : null,
          })),
        );
        const last = transcript.at(-1);
        const stillWaiting = last?.role === "assistant" && last.content.includes(PENDING_MARK);
        pausedAtRef.current = stillWaiting ? transcript.length : null;
        setAwaitingApproval(stillWaiting ?? false);
      } catch {
        if (cancelled) return;
        // A conversation this browser remembers but the server has forgotten (for example
        // after a demo reset): start clean instead of showing an unusable error.
        forget();
        setConversationId(null);
      }
    };

    void restore();
    return () => {
      cancelled = true;
    };
  }, [persona.id, conversationId, currentKey, forget, setConversationId]);

  const send = useCallback(
    async (text: string) => {
      const message = text.trim();
      if (!message || sending) return;
      const sendingFor = persona.id;
      setError(null);
      setMessages((previous) => [
        ...previous,
        { id: newId(), role: "customer", content: message },
      ]);
      setSending(true);
      try {
        const reply = await api.chat({
          persona: sendingFor,
          message,
          conversationId: conversationId ?? undefined,
        });
        // The visitor may have switched persona while this was in flight; that reply belongs to
        // the other account's thread, not the one now on screen.
        if (personaRef.current !== sendingFor) return;

        setMessages((previous) => [
          ...previous,
          {
            id: reply.request_id || newId(),
            role: "assistant",
            content: reply.reply,
            sources: reply.sources,
            outcome: reply.outcome,
            status: reply.status,
            handoffReason: reply.handoff_reason,
          },
        ]);
        if (!conversationId) {
          // Adopt the server's id without triggering a reload: what is on screen is current.
          loadedRef.current = threadKey(sendingFor, reply.conversation_id);
          setConversationId(reply.conversation_id);
        }
        if (reply.status === "pending_approval") {
          const transcript = await api.transcript(sendingFor, reply.conversation_id);
          pausedAtRef.current = transcript.length;
          setAwaitingApproval(true);
        }
        onBookingsMayHaveChanged?.();
      } catch (failure: unknown) {
        if (personaRef.current !== sendingFor) return;
        if (failure instanceof ApiRequestError && failure.status === 404) {
          // The conversation was cleared underneath us (demo reset). Recover in place.
          forget();
          setConversationId(null);
          setError(CONVERSATION_GONE);
          return;
        }
        setError(
          failure instanceof ApiRequestError ? failure.message : "Something went wrong.",
        );
      } finally {
        setSending(false);
      }
    },
    [conversationId, forget, onBookingsMayHaveChanged, persona.id, sending, setConversationId],
  );

  // While a refund waits on a human, watch the transcript for the outcome message.
  usePolling(
    async () => {
      const pausedAt = pausedAtRef.current;
      if (!conversationId || pausedAt === null) return;
      const transcript = await api.transcript(persona.id, conversationId);
      if (transcript.length <= pausedAt) return;

      const fresh = transcript.slice(pausedAt).filter((m) => m.role === "assistant");
      pausedAtRef.current = null;
      setAwaitingApproval(false);
      setMessages((previous) => [
        ...previous,
        ...fresh.map((message) => ({
          id: newId(),
          role: "assistant" as const,
          content: message.content,
          outcome: outcomeFromReply(message.content),
        })),
      ]);
      onBookingsMayHaveChanged?.();
    },
    5_000,
    awaitingApproval,
  );

  const startNewConversation = useCallback(() => {
    forget();
    setError(null);
    setConversationId(null);
  }, [forget, setConversationId]);

  return { messages, sending, awaitingApproval, error, send, startNewConversation };
}
