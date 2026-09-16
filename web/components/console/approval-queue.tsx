"use client";

import { useState } from "react";

import { Pill } from "@/components/ui/pill";
import { SLA_MINUTES, formatDuration } from "@/lib/console-metrics";
import { policyCopy, timeAgo } from "@/lib/format";
import type { Approval } from "@/lib/types";

const SLA_MS = SLA_MINUTES * 60_000;

interface ApprovalQueueProps {
  pending: Approval[];
  history: Approval[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  now: number;
}

interface QueueRowProps {
  approval: Approval;
  selected: boolean;
  onSelect: (id: string) => void;
  now: number;
}

/** The accent bar carries urgency at a glance: red once a request is past the target. */
function accentClass(approval: Approval, breaching: boolean): string {
  if (approval.status === "rejected") return "bg-rose-200";
  if (approval.status === "approved") return "bg-moss-200";
  return breaching ? "bg-rose-700" : "bg-amber-700";
}

function QueueRow({ approval, selected, onSelect, now }: QueueRowProps) {
  const decided = approval.status !== "pending";
  const waitMs = decided ? null : Math.max(0, now - new Date(approval.created_at).getTime());
  const breaching = waitMs !== null && waitMs > SLA_MS;

  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(approval.id)}
        aria-current={selected ? "true" : undefined}
        className={`flex w-full gap-3 rounded-xl border py-3 pr-4 pl-3 text-left transition-colors ${
          selected
            ? "border-tide-600 bg-white shadow-sm"
            : "border-sand-200 bg-white/70 hover:border-sand-300"
        }`}
      >
        <span
          aria-hidden
          className={`w-1 shrink-0 self-stretch rounded-full ${accentClass(approval, breaching)}`}
        />
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline justify-between gap-3">
            <span className="font-mono text-base font-semibold text-ink-950 tabular-nums">
              {approval.amount}
            </span>
            <span
              className={`text-xs tabular-nums ${
                breaching ? "font-semibold text-rose-700" : "text-ink-500"
              }`}
            >
              {decided
                ? timeAgo(approval.decided_at ?? approval.created_at)
                : `waiting ${formatDuration(waitMs)}`}
            </span>
          </span>
          <span className="mt-1 block truncate text-sm text-ink-700">
            {approval.booking_reference} · {approval.customer_email ?? "unknown customer"}
          </span>
          <span className="mt-2 flex flex-wrap items-center gap-1.5">
            <Pill tone={approval.status === "rejected" ? "rose" : decided ? "moss" : "amber"}>
              {approval.status === "pending" ? "Waiting" : approval.status}
            </Pill>
            <Pill tone="sand">{policyCopy(approval.policy_reason).label}</Pill>
          </span>
        </span>
      </button>
    </li>
  );
}

export function ApprovalQueue({
  pending,
  history,
  selectedId,
  onSelect,
  now,
}: ApprovalQueueProps) {
  const [tab, setTab] = useState<"pending" | "history">("pending");
  const rows = tab === "pending" ? pending : history;

  return (
    <section aria-label="Refund queue" className="flex min-h-0 flex-col">
      <div className="flex items-center gap-1 rounded-full bg-sand-200/70 p-1 ring-1 ring-inset ring-sand-300">
        {(["pending", "history"] as const).map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => setTab(value)}
            aria-pressed={tab === value}
            className={`flex-1 rounded-full px-3 py-1.5 text-sm capitalize transition-colors ${
              tab === value ? "bg-white text-ink-900 shadow-sm" : "text-ink-700 hover:bg-white/60"
            }`}
          >
            {value}
            <span className="ml-1.5 text-xs tabular-nums text-ink-500">
              {value === "pending" ? pending.length : history.length}
            </span>
          </button>
        ))}
      </div>

      <ul className="mt-3 min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
        {rows.length === 0 && (
          <li className="rounded-xl border border-dashed border-sand-300 p-4 text-sm text-ink-500">
            {tab === "pending"
              ? "Nothing waiting. Ask for a refund on the customer site and it appears here within seconds."
              : "No decisions yet."}
          </li>
        )}
        {rows.map((approval) => (
          <QueueRow
            key={approval.id}
            approval={approval}
            selected={approval.id === selectedId}
            onSelect={onSelect}
            now={now}
          />
        ))}
      </ul>
    </section>
  );
}
