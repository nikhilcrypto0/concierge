// Browser-side calls to this app's own /api routes. No keys here: the server adds them.

import type {
  Approval,
  ApprovalDetail,
  ApprovalStatus,
  Booking,
  ChatReply,
  DecisionResult,
  TranscriptMessage,
} from "@/lib/types";
import type { PersonaId } from "@/lib/personas";

export class ApiRequestError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: init?.body ? { "content-type": "application/json" } : undefined,
      cache: "no-store",
    });
  } catch {
    throw new ApiRequestError(0, "You appear to be offline. Check your connection and try again.");
  }
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const message =
      data && typeof data === "object" && "error" in data && typeof data.error === "string"
        ? data.error
        : "Something went wrong.";
    throw new ApiRequestError(response.status, message);
  }
  return data as T;
}

const enc = encodeURIComponent;

export const api = {
  chat: (body: { persona: PersonaId; message: string; conversationId?: string }) =>
    request<ChatReply>("/api/chat", { method: "POST", body: JSON.stringify(body) }),

  bookings: (persona: PersonaId) => request<Booking[]>(`/api/bookings?persona=${enc(persona)}`),

  transcript: (persona: PersonaId, conversationId: string) =>
    request<TranscriptMessage[]>(
      `/api/conversations/${enc(conversationId)}/messages?persona=${enc(persona)}`,
    ),

  approvals: (status: ApprovalStatus) =>
    request<Approval[]>(`/api/approvals?status=${enc(status)}`),

  approval: (id: string) => request<ApprovalDetail>(`/api/approvals/${enc(id)}`),

  decide: (id: string, body: { approve: boolean; note?: string }) =>
    request<DecisionResult>(`/api/approvals/${enc(id)}/decision`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  resetDemo: () => request<{ status: string }>("/api/demo/reset", { method: "POST" }),
};
