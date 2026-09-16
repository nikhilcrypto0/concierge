// Queue health derived from the approval records the console already fetches.
// Nothing here calls the API: if a figure appears on screen, it was computed from
// created_at, decided_at, status and amount_cents on real rows.

import type { Approval } from "@/lib/types";

/** How long a refund may sit unanswered before the console calls it out. */
export const SLA_MINUTES = 15;

const SLA_MS = SLA_MINUTES * 60_000;

export interface ConsoleMetrics {
  waiting: number;
  oldestWaitMs: number | null;
  breaching: boolean;
  decidedToday: number;
  approvedTotal: number;
  rejectedTotal: number;
  refundedCents: number;
  medianDecisionMs: number | null;
}

function decisionMs(approval: Approval): number | null {
  if (!approval.decided_at) return null;
  const elapsed =
    new Date(approval.decided_at).getTime() - new Date(approval.created_at).getTime();
  return Number.isFinite(elapsed) && elapsed >= 0 ? elapsed : null;
}

function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

function isSameDay(iso: string, reference: Date): boolean {
  const date = new Date(iso);
  return (
    date.getFullYear() === reference.getFullYear() &&
    date.getMonth() === reference.getMonth() &&
    date.getDate() === reference.getDate()
  );
}

export function computeMetrics(
  pending: Approval[],
  history: Approval[],
  now: number = Date.now(),
): ConsoleMetrics {
  const today = new Date(now);
  const waits = pending
    .map((approval) => now - new Date(approval.created_at).getTime())
    .filter((elapsed) => Number.isFinite(elapsed) && elapsed >= 0);
  const oldestWaitMs = waits.length > 0 ? Math.max(...waits) : null;
  const approved = history.filter((approval) => approval.status === "approved");

  return {
    waiting: pending.length,
    oldestWaitMs,
    breaching: oldestWaitMs !== null && oldestWaitMs > SLA_MS,
    decidedToday: history.filter(
      (approval) => approval.decided_at && isSameDay(approval.decided_at, today),
    ).length,
    approvedTotal: approved.length,
    rejectedTotal: history.filter((approval) => approval.status === "rejected").length,
    refundedCents: approved.reduce((total, approval) => total + approval.amount_cents, 0),
    medianDecisionMs: median(
      history.map(decisionMs).filter((value): value is number => value !== null),
    ),
  };
}

const MONEY = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export function formatCents(cents: number): string {
  return MONEY.format(cents / 100);
}

/** Compact duration for dashboard figures: 42s, 6m, 3h, 2d. */
export function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.round(hours / 24)}d`;
}
