"use client";

import { useState } from "react";

import { Pill } from "@/components/ui/pill";
import { policyCopy, timeAgo } from "@/lib/format";
import type { Approval } from "@/lib/types";

interface ApprovalQueueProps {
  pending: Approval[];
  history: Approval[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

function QueueRow({
  approval,
  selected,
  onSelect,
}: {
  approval: Approval;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const decided = approval.status !== "pending";
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(approval.id)}
        aria-current={selected ? "true" : undefined}
        className={`w-full rounded-xl border px-4 py-3 text-left transition-colors ${
          selected
            ? "border-tide-600 bg-white shadow-sm"
            : "border-sand-200 bg-white/70 hover:border-sand-300"
        }`}
      >
        <div className="flex items-baseline justify-between gap-3">
          <span className="font-mono text-base font-semibold text-ink-950">{approval.amount}</span>
          <span className="text-xs text-ink-500">
            {timeAgo(decided ? (approval.decided_at ?? approval.created_at) : approval.created_at)}
          </span>
        </div>
        <p className="mt-1 truncate text-sm text-ink-700">
          {approval.booking_reference} · {approval.customer_email ?? "unknown customer"}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <Pill tone={approval.status === "rejected" ? "rose" : decided ? "moss" : "amber"}>
            {approval.status === "pending" ? "Waiting" : approval.status}
          </Pill>
          <Pill tone="sand">{policyCopy(approval.policy_reason).label}</Pill>
        </div>
      </button>
    </li>
  );
}

export function ApprovalQueue({ pending, history, selectedId, onSelect }: ApprovalQueueProps) {
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
            <span className="ml-1.5 text-xs text-ink-500">
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
          />
        ))}
      </ul>
    </section>
  );
}
