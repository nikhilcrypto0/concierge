import type { BookingStatus } from "@/lib/types";

const DATE_TIME = new Intl.DateTimeFormat("en-US", {
  weekday: "short",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

export function formatDateTime(iso: string): string {
  return DATE_TIME.format(new Date(iso));
}

export function timeAgo(iso: string, now: number = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  return `${Math.round(hours / 24)} d ago`;
}

export function initialsFromEmail(email: string | null): string {
  if (!email) return "?";
  return email.slice(0, 2).toUpperCase();
}

/** How the refund amount was decided, in the words a support lead would use. */
export const POLICY_COPY: Record<string, { label: string; detail: string }> = {
  full_notice: {
    label: "Full refund",
    detail: "Cancelled 48 or more hours before the appointment, so the policy gives a full refund.",
  },
  partial_notice: {
    label: "50% refund",
    detail: "Cancelled between 24 and 48 hours before the appointment, so the policy gives 50%.",
  },
};

export function policyCopy(reason: string): { label: string; detail: string } {
  return POLICY_COPY[reason] ?? { label: reason.replaceAll("_", " "), detail: "" };
}

export const BOOKING_STATUS_COPY: Record<BookingStatus, string> = {
  scheduled: "Scheduled",
  completed: "Completed",
  cancelled: "Cancelled",
};

export const HANDOFF_COPY: Record<string, string> = {
  customer_request: "Handed to a person",
  completed_service_refund: "Quality team review",
  low_confidence: "Unsure, handed to a person",
  budget: "Usage limit reached",
  classifier_unavailable: "AI unavailable, handed to a person",
  answerer_unavailable: "AI unavailable, handed to a person",
  refund_conflict: "Needs a person to check",
};
