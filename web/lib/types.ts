// Shapes returned by the Concierge API, as seen through this app's /api proxy.

export type ChatStatus = "completed" | "pending_approval";

export interface Source {
  id: string;
  title: string;
  heading: string;
}

export interface ChatReply {
  conversation_id: string;
  status: ChatStatus;
  reply: string;
  outcome: string | null;
  intent: string | null;
  handoff_reason: string | null;
  sources: Source[];
  request_id: string;
}

export interface TranscriptMessage {
  role: "customer" | "assistant";
  content: string;
}

export type BookingStatus = "scheduled" | "completed" | "cancelled";

export interface Booking {
  reference: string;
  service: string;
  scheduled_for: string;
  status: BookingStatus;
  amount_cents: number;
  amount: string;
  refunded_cents: number;
  refunded: string;
}

export type ApprovalStatus = "pending" | "approved" | "rejected";

export interface Approval {
  id: string;
  conversation_id: string;
  customer_email: string | null;
  booking_reference: string;
  action: string;
  amount_cents: number;
  amount: string;
  policy_reason: string;
  status: ApprovalStatus;
  reviewer: string | null;
  review_note: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface ApprovalDetail {
  approval: Approval;
  booking: Booking | null;
  transcript: TranscriptMessage[];
}

export interface DecisionResult {
  approval: Approval;
  outcome: string | null;
  customer_reply: string;
}

export interface ApiError {
  error: string;
}
